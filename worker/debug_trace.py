"""Local trace buffer and crash-dump helper for the vision worker.

WHY this exists
---------------
When the worker crashes or hits the vision retry cap, the historical
signal we had was "three `dom.click ok` lines in the audit log and no
explanation". The Bridge side now exposes structured traces via the
new `debug.*` tool group (see OpenSIN-Bridge PR #33), but the Bridge
lives in the browser — if the worker process crashes or the Bridge
itself becomes unreachable, those traces are lost.

This module keeps a *local* ring buffer of the last N bridge calls on
the worker process side, and dumps the buffer to disk on critical
failure events. It is intentionally minimal and dependency-free so it
can be imported from anywhere in the worker without creating new
import cycles.

Design constraints
------------------
- Feature-flagged via the ``WORKER_DEBUG_TRACE`` env var. Default off.
  The zero-overhead path when disabled is a single truthiness check.
- Never raise. A tracer that crashes the production worker is worse
  than no tracer at all. Every public method catches `Exception`.
- Never log secrets. `_redact` strips known cookie/bearer/token keys
  before serialising. If in doubt, skip the field.
- Bounded memory. Ring buffer capped at ``MAX_RECORDS`` entries;
  oldest records evicted silently.

Public API
----------
`get_trace()`           -- return the process-wide singleton.
`TraceBuffer.record()`  -- append one bridge call record (method, dur, ok).
`TraceBuffer.dump()`    -- serialise the buffer to a JSON file and
                           return the path. Never raises.
`TraceBuffer.clear()`   -- drop all records.

Integration point
-----------------
`heypiggy_vision_worker.execute_bridge` calls `record()` after every
bridge roundtrip. `dump()` is invoked when the vision loop hits its
retry cap (see `dump_on_vision_cap`).
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, Optional

__all__ = [
    "TRACE_ENABLED",
    "TraceBuffer",
    "TraceRecord",
    "dump_on_vision_cap",
    "get_trace",
]

# --------------------------------------------------------------------------
# Feature flag. Read once at import time.
# --------------------------------------------------------------------------
#
# The flag is truthy when the env var is any of 1/true/yes/on (case
# insensitive). Anything else, including absence, disables tracing.
# We read it here so that the zero-overhead path in hot code is a
# single module-level boolean check.

_FLAG_VALUE = os.environ.get("WORKER_DEBUG_TRACE", "").strip().lower()
TRACE_ENABLED: bool = _FLAG_VALUE in {"1", "true", "yes", "on"}


# --------------------------------------------------------------------------
# Record shape
# --------------------------------------------------------------------------

# Maximum records kept in the ring buffer. Chosen empirically: a HeyPiggy
# survey session averages ~120 bridge calls, so 500 records covers ~4x
# the critical window before a blocker.
MAX_RECORDS: int = 500

# Fields we always strip from params and results before storing. Case
# matters less than substring match: anything containing any of these
# tokens gets the ``"<redacted>"`` placeholder.
_REDACT_KEYS: frozenset[str] = frozenset(
    {
        "cookie",
        "cookies",
        "authorization",
        "auth_token",
        "access_token",
        "refresh_token",
        "bearer",
        "password",
        "passwd",
        "secret",
        "api_key",
        "apikey",
        "session_id",
        "csrf",
    }
)

# Params keys we trim aggressively to a small preview. These are keys
# that frequently contain large blobs (JS source, full DOM HTML, base64
# screenshots) which would blow up the dump file.
_TRIM_KEYS: frozenset[str] = frozenset(
    {"script", "html", "outerHTML", "innerHTML", "dataUrl", "image"}
)
_TRIM_LEN: int = 200


class TraceRecord:
    """One bridge-call record. Plain dict under the hood for JSON."""

    __slots__ = ("data",)

    def __init__(
        self,
        *,
        method: str,
        params: Optional[Dict[str, Any]],
        result: Any,
        duration_ms: float,
        ok: bool,
        ts: Optional[float] = None,
    ) -> None:
        self.data: Dict[str, Any] = {
            "ts": ts if ts is not None else time.time(),
            "method": method,
            "duration_ms": round(duration_ms, 2),
            "ok": bool(ok),
            "params": _redact(params or {}),
            "result_preview": _preview_result(result),
        }

    def as_dict(self) -> Dict[str, Any]:
        return dict(self.data)


# --------------------------------------------------------------------------
# Ring buffer
# --------------------------------------------------------------------------


class TraceBuffer:
    """Thread-safe bounded buffer of ``TraceRecord`` entries.

    The buffer is cheap when tracing is disabled: `record()` checks the
    module-level flag first and returns immediately.
    """

    def __init__(self, max_records: int = MAX_RECORDS) -> None:
        self._records: Deque[TraceRecord] = deque(maxlen=max_records)
        self._lock = threading.Lock()
        self._dropped: int = 0  # count of records evicted by the maxlen cap

    # ---- write path ------------------------------------------------------

    def record(
        self,
        *,
        method: str,
        params: Optional[Dict[str, Any]],
        result: Any,
        duration_ms: float,
        ok: bool,
    ) -> None:
        """Append a bridge-call record. Never raises."""
        if not TRACE_ENABLED:
            return
        try:
            rec = TraceRecord(
                method=method,
                params=params,
                result=result,
                duration_ms=duration_ms,
                ok=ok,
            )
            with self._lock:
                if len(self._records) == self._records.maxlen:
                    self._dropped += 1
                self._records.append(rec)
        except Exception:
            # Tracer must never crash the caller. Swallow.
            return

    # ---- read path -------------------------------------------------------

    def size(self) -> int:
        with self._lock:
            return len(self._records)

    def dropped(self) -> int:
        with self._lock:
            return self._dropped

    def recent(self, n: int = 20) -> Iterable[TraceRecord]:
        """Return the N most-recent records, oldest first."""
        with self._lock:
            if n <= 0:
                return []
            return list(self._records)[-n:]

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
            self._dropped = 0

    # ---- dump ------------------------------------------------------------

    def dump(
        self,
        *,
        reason: str,
        directory: Optional[str] = None,
        last_n: int = 20,
    ) -> Optional[str]:
        """Write the last N records to a JSON file.

        Returns the path as a string on success, ``None`` if tracing is
        disabled or writing fails. Never raises.
        """
        if not TRACE_ENABLED:
            return None
        try:
            target_dir = Path(directory or os.environ.get("WORKER_DEBUG_DUMP_DIR", "./debug-dumps"))
            target_dir.mkdir(parents=True, exist_ok=True)
            filename = (
                f"trace-{int(time.time())}-{_safe_slug(reason)[:40]}.json"
            )
            path = target_dir / filename
            payload = {
                "reason": reason,
                "dumped_at": time.time(),
                "total_in_buffer": self.size(),
                "dropped_since_last_clear": self.dropped(),
                "records": [r.as_dict() for r in self.recent(last_n)],
            }
            path.write_text(json.dumps(payload, indent=2, default=_json_fallback))
            return str(path)
        except Exception:
            return None


# Process-wide singleton ----------------------------------------------------

_singleton_lock = threading.Lock()
_singleton: Optional[TraceBuffer] = None


def get_trace() -> TraceBuffer:
    """Return the process-wide ``TraceBuffer`` singleton."""
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = TraceBuffer()
    return _singleton


# --------------------------------------------------------------------------
# Convenience: crash-dump wrapper for the vision retry cap
# --------------------------------------------------------------------------


def dump_on_vision_cap(*, attempts: int, last_error: Optional[str] = None) -> Optional[str]:
    """Called from the vision loop when the retry cap is hit.

    No-op when tracing is disabled. On a real failure the returned path
    should be surfaced in the audit log so an operator can inspect it.
    """
    if not TRACE_ENABLED:
        return None
    reason = f"vision_retry_cap_attempts={attempts}"
    if last_error:
        reason += f"_err={last_error[:40]}"
    return get_trace().dump(reason=reason)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _redact(value: Any, _depth: int = 0) -> Any:
    """Recursively replace sensitive keys with ``"<redacted>"``.

    Also trims long blob fields so dumps stay human-readable. Recursion
    is bounded at depth 6 to avoid pathological nested structures.
    """
    if _depth > 6:
        return "<max-depth>"
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            key_low = str(k).lower()
            if any(tok in key_low for tok in _REDACT_KEYS):
                out[str(k)] = "<redacted>"
                continue
            if any(tok == key_low for tok in _TRIM_KEYS):
                if isinstance(v, str) and len(v) > _TRIM_LEN:
                    out[str(k)] = v[:_TRIM_LEN] + f"...[+{len(v) - _TRIM_LEN}ch]"
                    continue
            out[str(k)] = _redact(v, _depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        return [_redact(v, _depth + 1) for v in value]
    if isinstance(value, str) and len(value) > 400:
        return value[:400] + f"...[+{len(value) - 400}ch]"
    return value


def _preview_result(result: Any) -> Any:
    """Compact summary of a bridge result payload for the ring buffer."""
    if result is None:
        return None
    if isinstance(result, dict):
        preview: Dict[str, Any] = {
            "keys": sorted(str(k) for k in result.keys())[:20],
        }
        if "error" in result:
            preview["error"] = str(result.get("error"))[:200]
        if "ok" in result:
            preview["ok"] = bool(result.get("ok"))
        if "url" in result:
            preview["url"] = str(result.get("url"))[:200]
        return preview
    if isinstance(result, (list, tuple)):
        return {"type": "list", "len": len(result)}
    if isinstance(result, str):
        return result[:200] + ("..." if len(result) > 200 else "")
    return {"type": type(result).__name__}


def _safe_slug(value: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in value)


def _json_fallback(obj: Any) -> str:
    return f"<non-serialisable:{type(obj).__name__}>"
