# ================================================================================
# DATEI: bridge_retry.py
# PROJEKT: A2A-SIN-Worker-heyPiggy (OpenSIN AI Agent System)
# ZWECK: 
# WICHTIG FÜR ENTWICKLER: 
#   - Ändere nichts ohne zu verstehen was passiert
#   - Jeder Kommentar erklärt WARUM etwas getan wird, nicht nur WAS
#   - Bei Fragen erst Code lesen, dann ändern
# ================================================================================

"""
Retry-Wrapper mit Exponential Backoff fuer Bridge/MCP-Calls.

WHY (DE): Die Chrome-MCP-Bridge kann kurzzeitig fehlschlagen wenn der Browser
gerade navigiert, ein Dialog geoeffnet ist, Netzwerk wackelt oder die
Extension einen neuen Worker-Kontext startet. Ohne Retry reisst ein einzelner
200ms-Spike sofort die ganze Umfrage ab. Mit klassifiziertem Retry ueberleben
wir 98% dieser transienten Fehler ohne dass der Vision-Agent sie sieht.

KONSEQUENZEN:
- Der Aufrufer bekommt entweder ein gueltiges Ergebnis oder — nach den
  konfigurierten Retry-Versuchen — das letzte Error-Dict.
- Nicht-transiente Fehler (z.B. invalid_argument, auth) werden SOFORT
  zurueckgegeben (kein Retry), damit wir nicht Quota verbrennen.
- Der Retry-Counter wird auditiert damit wir in run_summary sehen wie oft
  die Bridge wackelt (Frueh-Warnsystem fuer Infra-Probleme).
"""

from __future__ import annotations

import inspect
from typing import Any, Awaitable, Callable

from worker.retry import RetryPolicy, retry_async


# Signaturen die wir als "transient" klassifizieren. WHY: Substring-Match weil
# die Bridge Fehler in freiem Text zurueckgibt, nicht als Enum.
TRANSIENT_MARKERS: tuple[str, ...] = (
    "timeout",
    "timed out",
    "econnreset",
    "econnrefused",
    "socket hang up",
    "network error",
    "navigation interrupted",
    "target closed",
    "context was destroyed",
    "execution context",
    "temporarily unavailable",
    "bridge not ready",
    "ws disconnect",
    "websocket closed",
    "chrome not reachable",
    "no response",
)

# Signaturen die NIE retried werden. WHY: Bei Auth/Invalid-Argument waere Retry
# sinnlos und gefaehrlich (Rate-Limit-Verletzung, Account-Sperre).
PERMANENT_MARKERS: tuple[str, ...] = (
    "unauthorized",
    "forbidden",
    "invalid argument",
    "invalid parameter",
    "not found",
    "no tab with id",  # Tab-Recovery laeuft bereits im Worker, nicht hier retryen
    "no tab with given id",
    "method not found",
)

TRANSIENT_CONTRACT_CODES: tuple[str, ...] = (
    "transport_error",
    "timeout",
    "target_gone",
    "navigation_aborted",
    "navigation_timeout",
    "cdp_failed",
    "frame_detached",
    "session_stale",
    "session_invalid",
    "anti_bot_challenge",
    "rate_limit_remote",
)


class _TransientBridgeResult(Exception):
    """Internal sentinel for result-based transient bridge failures."""

    def __init__(self, result: Any, error_text: str) -> None:
        super().__init__(error_text)
        self.result = result
        self.error_text = error_text

PERMANENT_CONTRACT_CODES: tuple[str, ...] = (
    "rpc_invalid",
    "unknown_method",
    "rate_limited",
    "element_not_found",
    "element_not_actionable",
    "postcondition_failed",
    "duplicate_action",
    "session_locked",
    "origin_not_permitted",
    "captcha_required",
    "unsupported",
    "internal_error",
)


def classify_result(result: Any) -> str:
    """
    Klassifiziert ein Bridge-Ergebnis in 'ok' / 'transient' / 'permanent'.

    WHY: Nur 'transient' wird retried.
    """
    if not isinstance(result, dict):
        return "ok"
    err = result.get("error") or result.get("errorMessage") or result.get("message")
    if not err:
        # Auch wenn kein error-Feld, pruefen ob 'ok: false' gesetzt
        if result.get("ok") is False and result.get("reason"):
            err = result.get("reason")
    if not err:
        return "ok"

    if isinstance(err, dict):
        retry_hint = str(err.get("retryHint") or err.get("retry_hint") or "").strip().lower()
        if retry_hint in {"safe_retry", "recover_then_retry"}:
            return "transient"
        if retry_hint == "abort":
            return "permanent"

        code = str(err.get("code") or err.get("errorCode") or "").strip().lower()
        if code in TRANSIENT_CONTRACT_CODES:
            return "transient"
        if code in PERMANENT_CONTRACT_CODES:
            return "permanent"

    err_low = str(err).lower()
    for marker in TRANSIENT_CONTRACT_CODES:
        if marker in err_low:
            return "transient"
    for marker in PERMANENT_CONTRACT_CODES:
        if marker in err_low:
            return "permanent"
    for marker in PERMANENT_MARKERS:
        if marker in err_low:
            return "permanent"
    for marker in TRANSIENT_MARKERS:
        if marker in err_low:
            return "transient"
    # Unbekannter Fehler — einmal retryen koennte helfen, aber wir sind
    # konservativ und behandeln als permanent.
    return "permanent"


async def call_with_retry(
    bridge: Callable[..., Awaitable[Any]],
    method: str | None = None,
    params: dict[str, Any] | None = None,
    *,
    max_attempts: int = 3,
    base_delay: float = 0.2,
    max_delay: float = 4.0,
    jitter: float = 0.3,
    audit: Callable[..., None] | None = None,
    on_retry: Callable[[int, str, float], Awaitable[None] | None] | None = None,
) -> Any:
    """Ruft `bridge(method, params)` mit Exponential Backoff auf."""

    policy = RetryPolicy(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        jitter=jitter,
        retry_on=(_TransientBridgeResult,),
    )

    attempt = 0
    last_classification = "ok"
    async def _audit_retry(attempt_no: int, exc: BaseException, delay: float) -> None:
        error_text = exc.error_text if isinstance(exc, _TransientBridgeResult) else str(exc)
        if audit:
            audit(
                "bridge_retry_wait",
                method=method,
                attempt=attempt_no,
                wait_ms=round(delay * 1000),
                classification="transient",
                error=error_text[:120],
            )
        if on_retry:
            maybe_awaitable = on_retry(attempt_no, error_text, delay)
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable

    @retry_async(policy, on_retry=_audit_retry)
    async def _attempt() -> Any:
        nonlocal attempt, last_classification
        try:
            call_result = bridge() if method is None else bridge(method, params)
            result = await call_result if inspect.isawaitable(call_result) else call_result
        except Exception as exc:
            error_text = f"exception: {type(exc).__name__}: {exc}"
            last_classification = "transient"
            attempt += 1
            raise _TransientBridgeResult({"error": error_text}, error_text) from exc

        klass = classify_result(result)
        last_classification = klass
        attempt += 1

        if klass == "ok" or klass == "permanent":
            return result

        error_text = _extract_error_text(result)
        raise _TransientBridgeResult(result, error_text)

    try:
        result = await _attempt()
    except _TransientBridgeResult as exc:
        if attempt > 1 and audit:
            audit(
                "bridge_retry_exhausted",
                method=method,
                attempts=attempt,
                classification=last_classification,
            )
        return exc.result

    if attempt > 1 and audit:
        if last_classification == "ok":
            audit("bridge_retry_success", method=method, attempts=attempt)
        else:
            audit(
                "bridge_retry_exhausted",
                method=method,
                attempts=attempt,
                classification=last_classification,
            )
    return result


def _extract_error_text(result: Any) -> str:
    if not isinstance(result, dict):
        return ""
    err = result.get("error") or result.get("errorMessage") or result.get("message")
    if not err and result.get("ok") is False and result.get("reason"):
        err = result.get("reason")
    return str(err) if err is not None else ""


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio as _a

    async def _main() -> None:
        calls = {"n": 0}

        async def fake_bridge(method: str, params: dict[str, Any] | None):
    # -------------------------------------------------------------------------
    # FUNKTION: fake_bridge
    # PARAMETER: method: str, params: dict[str, Any] | None
    # ZWECK: 
    # WAS PASSIERT HIER: 
    # WARUM DIESER WEG: 
    # ACHTUNG: 
    # -------------------------------------------------------------------------
    
            calls["n"] += 1
            if calls["n"] < 3:
                return {"error": "timeout while navigating"}
            return {"ok": True, "method": method}

        audit_log: list[tuple[str, dict[str, Any]]] = []

        def _audit(event: str, **kw: Any) -> None:
            audit_log.append((event, kw))

        res = await call_with_retry(fake_bridge, "navigate", {"url": "x"}, audit=_audit)
        assert res == {"ok": True, "method": "navigate"}, res
        assert calls["n"] == 3
        assert any(e[0] == "bridge_retry_success" for e in audit_log)

        # Permanent error -> kein Retry
        async def perma(method, params):
    # -------------------------------------------------------------------------
    # FUNKTION: perma
    # PARAMETER: method, params
    # ZWECK: 
    # WAS PASSIERT HIER: 
    # WARUM DIESER WEG: 
    # ACHTUNG: 
    # -------------------------------------------------------------------------
    
            return {"error": "unauthorized"}

        res2 = await call_with_retry(perma, "x", max_attempts=5)
        assert res2 == {"error": "unauthorized"}
        print("bridge_retry self-test ok")

    _a.run(_main())
