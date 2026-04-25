# ================================================================================
# DATEI: contract.py
# PROJEKT: A2A-SIN-Worker-heyPiggy (OpenSIN AI Agent System)
# ZWECK: 
# WICHTIG FÜR ENTWICKLER: 
#   - Ändere nichts ohne zu verstehen was passiert
#   - Jeder Kommentar erklärt WARUM etwas getan wird, nicht nur WAS
#   - Bei Fragen erst Code lesen, dann ändern
# ================================================================================

"""Bridge contract v1 -- mirror of OpenSIN-Bridge/extension/src/contract/v1."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Final, Literal, Mapping

BRIDGE_CONTRACT_VERSION = "1.0.0"
BRIDGE_CONTRACT_REVISION = 1
CONTRACT_VERSION = BRIDGE_CONTRACT_VERSION
_EXPECTED_MAJOR = CONTRACT_VERSION.split(".", 1)[0]
_log = logging.getLogger(__name__)

RetryHint = Literal["retry", "retry-after-refresh", "retry-after-reauth", "abort"]
RetryCategory = Literal["ok", "transient", "permanent"]


@dataclass(frozen=True)
class BridgeMethod:
    # ========================================================================
    # KLASSE: BridgeMethod
    # ZWECK: 
    # WICHTIG: 
    # METHODEN: 
    # ========================================================================
    
    name: str
    category: str
    idempotent: bool
    mutates: bool
    retry_hint: RetryHint
    description: str


@dataclass(frozen=True, slots=True)
class BridgeContract:
    """Immutable bridge contract metadata."""

    required_methods: frozenset[str]
    required_error_codes: frozenset[str]
    idempotent_methods: frozenset[str] = field(default_factory=frozenset)

    def is_method_supported(self, method: str) -> bool:
        return method in self.required_methods

    def is_error_code_known(self, code: str) -> bool:
        return code in self.required_error_codes


@dataclass(frozen=True, slots=True)
class BridgeRequest:
    """Strict request envelope used by the adapter layer."""

    tool: str
    params: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str = field(default_factory=lambda: uuid.uuid4().hex)
    contract_version: str = CONTRACT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "params": dict(self.params),
            "idempotency_key": self.idempotency_key,
            "contract_version": self.contract_version,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "BridgeRequest":
        tool = payload.get("tool") or payload.get("method")
        if not isinstance(tool, str) or not tool:
            raise ValueError("missing tool")

        params = payload.get("params") or {}
        if not isinstance(params, dict):
            raise ValueError("params must be a dict")

        idempotency_key = payload.get("idempotency_key") or payload.get("idempotencyKey")
        if idempotency_key is not None and not isinstance(idempotency_key, str):
            raise ValueError("idempotency_key must be a string")

        contract_version = payload.get("contract_version") or payload.get("contractVersion")
        if contract_version is not None and not isinstance(contract_version, str):
            raise ValueError("contract_version must be a string")

        return cls(
            tool=tool,
            params=dict(params),
            idempotency_key=idempotency_key or uuid.uuid4().hex,
            contract_version=contract_version or CONTRACT_VERSION,
        )


@dataclass(frozen=True, slots=True)
class BridgeResponse:
    """Strict response envelope used by the adapter layer."""

    ok: bool
    result: Any | None = None
    error: dict[str, Any] | None = None
    retry_hint: RetryHint | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"ok": self.ok}
        if self.result is not None:
            payload["result"] = self.result
        if self.error is not None:
            payload["error"] = dict(self.error)
        if self.retry_hint is not None:
            payload["retry_hint"] = self.retry_hint
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "BridgeResponse":
        ok = payload.get("ok")
        if not isinstance(ok, bool):
            raise ValueError("ok must be a boolean")

        result = payload.get("result")
        error = payload.get("error")
        if error is not None and not isinstance(error, dict):
            raise ValueError("error must be a dict or None")

        retry_hint = payload.get("retry_hint") or payload.get("retryHint")
        if retry_hint is not None and retry_hint not in {"retry", "retry-after-refresh", "retry-after-reauth", "abort"}:
            raise ValueError("invalid retry_hint")

        return cls(ok=ok, result=result, error=error, retry_hint=retry_hint)


METHODS: tuple[BridgeMethod, ...] = (
    # ----- contract meta -----------------------------------------------------
    BridgeMethod("bridge.contract", "meta", True, False, "abort", "Return the active bridge contract"),
    BridgeMethod("bridge.contract.version", "meta", True, False, "abort", "Return contract version + revision"),
    BridgeMethod("bridge.contract.method", "meta", True, False, "abort", "Metadata for a single method"),
    BridgeMethod("bridge.contract.idempotent", "meta", True, False, "abort", "Is the method retry-safe?"),
    BridgeMethod("bridge.contract.translate", "meta", True, False, "abort", "Translate internal error -> public code"),
    # ----- tabs --------------------------------------------------------------
    BridgeMethod("tabs.list", "tabs", True, False, "retry", "List all open tabs"),
    BridgeMethod("tabs.focus", "tabs", True, True, "retry", "Focus a tab"),
    BridgeMethod("tabs.close", "tabs", False, True, "abort", "Close a tab"),
    BridgeMethod("tabs.open", "tabs", False, True, "retry", "Open a new tab"),
    # ----- navigation --------------------------------------------------------
    BridgeMethod("navigation.to", "navigation", False, True, "retry-after-refresh", "Navigate to URL"),
    BridgeMethod("navigation.back", "navigation", False, True, "retry", "Back"),
    BridgeMethod("navigation.forward", "navigation", False, True, "retry", "Forward"),
    BridgeMethod("navigation.reload", "navigation", False, True, "retry", "Reload"),
    # ----- dom ---------------------------------------------------------------
    BridgeMethod("dom.snapshot", "dom", True, False, "retry", "AX snapshot of a tab"),
    BridgeMethod("dom.query", "dom", True, False, "retry", "Query by selector"),
    BridgeMethod("dom.click", "dom", False, True, "retry-after-refresh", "Click by selector or target"),
    BridgeMethod("dom.type", "dom", False, True, "retry-after-refresh", "Type into input"),
    BridgeMethod("dom.scroll", "dom", False, True, "retry", "Scroll element or page"),
    BridgeMethod("dom.evaluate", "dom", False, False, "retry", "Evaluate JS in page"),
    # ----- cookies -----------------------------------------------------------
    BridgeMethod("cookies.get", "cookies", True, False, "retry", "Get cookies by URL"),
    BridgeMethod("cookies.set", "cookies", True, True, "retry", "Set a cookie"),
    BridgeMethod("cookies.remove", "cookies", True, True, "retry", "Remove a cookie"),
    # ----- storage -----------------------------------------------------------
    BridgeMethod("storage.local.get", "storage", True, False, "retry", "Read localStorage"),
    BridgeMethod("storage.local.set", "storage", True, True, "retry", "Write localStorage"),
    BridgeMethod("storage.session.get", "storage", True, False, "retry", "Read sessionStorage"),
    BridgeMethod("storage.session.set", "storage", True, True, "retry", "Write sessionStorage"),
    # ----- network -----------------------------------------------------------
    BridgeMethod("network.lastRequests", "network", True, False, "retry", "Last N network requests"),
    BridgeMethod("network.capture.start", "network", True, True, "retry", "Start capture"),
    BridgeMethod("network.capture.stop", "network", True, True, "retry", "Stop capture"),
    # ----- session lifecycle (issue #71) -------------------------------------
    BridgeMethod("session.manifest", "session", True, True, "retry", "Build or refresh session manifest"),
    BridgeMethod("session.invalidate", "session", True, True, "abort", "Invalidate session"),
    BridgeMethod("session.lastKnownGood", "session", True, False, "retry", "Get last-known-good snapshot"),
    BridgeMethod("session.health", "session", True, False, "retry", "Probe session status"),
    BridgeMethod("session.list", "session", True, False, "retry", "List manifests"),
    BridgeMethod("session.drop", "session", True, True, "abort", "Drop a manifest"),
    BridgeMethod("session.save", "session", False, True, "retry", "Save cookies + storage snapshot"),
    BridgeMethod("session.restore", "session", False, True, "retry-after-refresh", "Restore snapshot"),
    # ----- behavior (issue #70) ---------------------------------------------
    BridgeMethod("behavior.start", "behavior", False, True, "retry", "Start recording"),
    BridgeMethod("behavior.stop", "behavior", False, True, "retry", "Stop recording"),
    BridgeMethod("behavior.status", "behavior", True, False, "retry", "Recording status"),
    BridgeMethod("behavior.timeline", "behavior", True, False, "retry", "Behavior timeline"),
    BridgeMethod("bridge.evidenceBundle", "observability", True, False, "retry", "Assemble evidence bundle"),
    BridgeMethod("bridge.traces", "observability", True, False, "retry", "Recent dispatches"),
    # ----- stealth (issue #74) ----------------------------------------------
    BridgeMethod("stealth.assess", "stealth", True, False, "retry", "Score environment coherence"),
    BridgeMethod("stealth.detectChallenge", "stealth", True, False, "retry", "Detect anti-bot challenge"),
    # ----- vision ------------------------------------------------------------
    BridgeMethod("vision.screenshot", "vision", True, False, "retry", "Screenshot the tab"),
)

_METHODS_BY_NAME = {m.name: m for m in METHODS}


def get_method(name: str) -> BridgeMethod:
    try:
        return _METHODS_BY_NAME[name]
    except KeyError as exc:
        raise BridgeError("METHOD_NOT_FOUND", f"unknown bridge method: {name}", retry_hint="abort") from exc


def is_idempotent(name: str) -> bool:
    return get_method(name).idempotent


def retry_hint_for(name: str) -> RetryHint:
    return get_method(name).retry_hint


def validate_contract_version(remote_version: str) -> None:
    """Validate a remote bridge version against the current major version."""

    version = str(remote_version or "").strip()
    parts = version.split(".")
    if len(parts) < 3 or not parts[0].isdigit():
        raise ContractMismatch(CONTRACT_VERSION, version or "<empty>")

    major = parts[0]
    if major != _EXPECTED_MAJOR:
        raise ContractMismatch(CONTRACT_VERSION, version)

    if version != CONTRACT_VERSION:
        _log.warning("bridge contract version drift accepted: local=%s remote=%s", CONTRACT_VERSION, version)


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def attach_idempotency(
    payload: dict[str, Any],
    *,
    method: str | None = None,
    idempotent: bool | None = None,
) -> dict[str, Any]:
    """Attach a stable idempotency key and bridge contract version.

    Idempotent methods get a deterministic SHA-256 key derived from the method
    name and canonical params. Mutating methods get a random UUID4 key.
    """

    envelope = dict(payload)
    method_name = method or str(envelope.get("tool") or envelope.get("method") or "")
    params = envelope.get("params") or {}
    if not isinstance(params, dict):
        raise ValueError("params must be a dict")

    if idempotent is None:
        idempotent = method_name in DEFAULT_CONTRACT.idempotent_methods

    if "idempotency_key" not in envelope:
        if idempotent:
            digest = hashlib.sha256(
                f"{method_name}:{_canonical_json(params)}".encode("utf-8")
            ).hexdigest()
            envelope["idempotency_key"] = digest
        else:
            envelope["idempotency_key"] = uuid.uuid4().hex

    envelope.setdefault("contract_version", CONTRACT_VERSION)
    if method_name and "tool" not in envelope and "method" not in envelope:
        envelope["tool"] = method_name
    if "params" not in envelope:
        envelope["params"] = dict(params)
    return envelope


# ---------------------------------------------------------------------------
# errors
# ---------------------------------------------------------------------------

ERROR_CODES: tuple[str, ...] = (
    "INVALID_ARGS",
    "METHOD_NOT_FOUND",
    "TAB_NOT_FOUND",
    "TAB_CLOSED",
    "SESSION_INVALID",
    "SESSION_EXPIRED",
    "SESSION_MISSING",
    "TARGET_NOT_FOUND",
    "STALE_TARGET",
    "NAV_TIMEOUT",
    "CHALLENGE_DETECTED",
    "STEALTH_INCOHERENT",
    "RATE_LIMITED",
    "PERMISSION_DENIED",
    "INTERNAL",
    "CONTRACT_MISMATCH",
)

IDEMPOTENT_METHODS: Final[frozenset[str]] = frozenset(m.name for m in METHODS if m.idempotent)
MUTATING_METHODS: Final[frozenset[str]] = frozenset(m.name for m in METHODS if m.mutates)
DEFAULT_CONTRACT: Final[BridgeContract] = BridgeContract(
    required_methods=frozenset(m.name for m in METHODS),
    required_error_codes=frozenset(ERROR_CODES),
    idempotent_methods=IDEMPOTENT_METHODS,
)


_RETRY_TRANSIENT_MARKERS: Final[tuple[str, ...]] = (
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

_RETRY_PERMANENT_MARKERS: Final[tuple[str, ...]] = (
    "unauthorized",
    "forbidden",
    "invalid argument",
    "invalid parameter",
    "not found",
    "no tab with id",
    "no tab with given id",
    "method not found",
)

_RETRY_TRANSIENT_CODES: Final[tuple[str, ...]] = (
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

_RETRY_PERMANENT_CODES: Final[tuple[str, ...]] = (
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


class BridgeError(Exception):
    # ========================================================================
    # KLASSE: BridgeError(Exception)
    # ZWECK: 
    # WICHTIG: 
    # METHODEN: 
    # ========================================================================
    
    """Canonical bridge error. Mirrors the JS ``BridgeError`` class."""

    def __init__(self, code: str, message: str, *, retry_hint: RetryHint = "abort", data: dict | None = None):
        if code not in ERROR_CODES:
            raise ValueError(f"unknown bridge error code: {code}")
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.retry_hint = retry_hint
        self.data = data or {}

    def to_wire(self) -> dict:
        return {"code": self.code, "message": str(self), "retry_hint": self.retry_hint, "data": self.data}


class ContractMismatch(BridgeError):
    # ========================================================================
    # KLASSE: ContractMismatch(BridgeError)
    # ZWECK: 
    # WICHTIG: 
    # METHODEN: 
    # ========================================================================
    
    def __init__(self, expected: str, got: str):
    # -------------------------------------------------------------------------
    # FUNKTION: __init__
    # PARAMETER: self, expected: str, got: str
    # ZWECK: 
    # WAS PASSIERT HIER: 
    # WARUM DIESER WEG: 
    # ACHTUNG: 
    # -------------------------------------------------------------------------
    
        super().__init__(
            "CONTRACT_MISMATCH",
            f"bridge contract major mismatch: expected {expected}, got {got}",
            retry_hint="abort",
            data={"expected": expected, "got": got},
        )


def classify_error(raw: dict | Exception) -> BridgeError:
    """Turn any bridge response or exception into a BridgeError."""
    if isinstance(raw, BridgeError):
        return raw
    if isinstance(raw, Exception):
        return BridgeError("INTERNAL", str(raw), retry_hint="retry")
    code = raw.get("code") if isinstance(raw, dict) else None
    if code and code in ERROR_CODES:
        return BridgeError(
            code,
            raw.get("message") or code,
            retry_hint=raw.get("retry_hint", "abort"),
            data=raw.get("data") or {},
        )
    return BridgeError("INTERNAL", str(raw), retry_hint="retry")


def classify_retry_category(raw: dict | Exception) -> RetryCategory:
    """Classify a raw bridge result using the legacy retry markers."""

    if not isinstance(raw, dict):
        return "ok"

    err = raw.get("error") or raw.get("errorMessage") or raw.get("message")
    if not err and raw.get("ok") is False and raw.get("reason"):
        err = raw.get("reason")
    if not err:
        return "ok"

    if isinstance(err, dict):
        retry_hint = str(err.get("retryHint") or err.get("retry_hint") or "").strip().lower()
        if retry_hint in {"safe_retry", "recover_then_retry"}:
            return "transient"
        if retry_hint == "abort":
            return "permanent"

        code = str(err.get("code") or err.get("errorCode") or "").strip().lower()
        if code in _RETRY_TRANSIENT_CODES:
            return "transient"
        if code in _RETRY_PERMANENT_CODES:
            return "permanent"

    err_low = str(err).lower()
    for marker in _RETRY_TRANSIENT_CODES:
        if marker in err_low:
            return "transient"
    for marker in _RETRY_PERMANENT_CODES:
        if marker in err_low:
            return "permanent"
    for marker in _RETRY_PERMANENT_MARKERS:
        if marker in err_low:
            return "permanent"
    for marker in _RETRY_TRANSIENT_MARKERS:
        if marker in err_low:
            return "transient"
    return "permanent"
