# ================================================================================
# DATEI: opensin_bridge_integration.py
# PROJEKT: A2A-SIN-Worker-heyPiggy (OpenSIN AI Agent System)
# ZWECK: 
# WICHTIG FÜR ENTWICKLER: 
#   - Ändere nichts ohne zu verstehen was passiert
#   - Jeder Kommentar erklärt WARUM etwas getan wird, nicht nur WAS
#   - Bei Fragen erst Code lesen, dann ändern
# ================================================================================

"""Legacy <-> new-stack bridge with opt-in contract negotiation.

``heypiggy_vision_worker.py`` keeps working unchanged. New code paths can
import :func:`make_stack` to get a fully wired
``BridgeAdapter + InteractionEngine + StateMachine + TraceRecorder`` tuple,
while the optional V2 flag also negotiates bridge capabilities up front.

This module is the single integration point between the architecture
reset (issues #68-#76) and the in-place worker. Delete once the worker
no longer needs the legacy ``call_with_retry`` signature.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from opensin_bridge.adapter import BridgeAdapter
from opensin_bridge.contract import BridgeContract
from opensin_bridge.observability import TraceRecorder
from opensin_interaction import InteractionEngine
from opensin_runtime import StateMachine


RpcFn = Callable[[str, dict[str, Any]], Awaitable[Any]]

EXPECTED_CONTRACT_MAJOR = "1"


class ContractMismatchError(RuntimeError):
    """Raised when the bridge contract is not compatible with this worker."""


@dataclass(frozen=True)
class BridgeAdapterConfig:
    """Validated bridge contract surface returned after negotiation."""

    version: str
    methods: dict[str, dict[str, Any]]
    idempotent_methods: frozenset[str]
    error_codes: frozenset[str]
    tool_surface_kind: str

    def to_bridge_contract(self) -> BridgeContract:
        return BridgeContract(
            required_methods=frozenset(self.methods),
            required_error_codes=self.error_codes,
            idempotent_methods=self.idempotent_methods,
        )


def _is_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _bridge_mode() -> str:
    """Return which bridge adapter mode should be used.

    WHY: The legacy monolith stays the default. New adapter behavior is only
    enabled when an explicit opt-in flag requests it.
    """
    explicit = os.environ.get("BRIDGE_ADAPTER", "").strip().lower()
    if explicit in {"opensin", "legacy"}:
        return explicit
    if _is_truthy(os.environ.get("OPENSIN_BRIDGE_V2")):
        return "opensin"
    if _is_truthy(os.environ.get("OPENSIN_V2")):
        return "opensin"
    return "legacy"


def _normalize_methods(raw_methods: Any) -> dict[str, dict[str, Any]]:
    if isinstance(raw_methods, dict):
        normalized: dict[str, dict[str, Any]] = {}
        for name, meta in raw_methods.items():
            if not isinstance(name, str) or not name.strip():
                continue
            normalized[name] = dict(meta) if isinstance(meta, dict) else {"value": meta}
        return normalized

    if isinstance(raw_methods, list):
        normalized = {}
        for entry in raw_methods:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if isinstance(name, str) and name.strip():
                normalized[name] = dict(entry)
        return normalized

    raise ContractMismatchError("bridge.contract.methods must be a mapping or list")


def _normalize_error_codes(contract: dict[str, Any]) -> frozenset[str]:
    raw = contract.get("errorCodes") or contract.get("error_codes") or []
    if isinstance(raw, dict):
        raw = raw.keys()
    if not isinstance(raw, (list, tuple, set, frozenset)):
        raise ContractMismatchError("bridge.contract.errorCodes must be a list")
    return frozenset(str(code).strip() for code in raw if str(code).strip())


def _tool_surface_kind(contract: dict[str, Any]) -> str:
    surface = (
        contract.get("surfaceKind")
        or contract.get("surface_kind")
        or contract.get("toolSurfaceKind")
        or contract.get("tool_surface_kind")
        or "unknown"
    )
    return str(surface).strip() or "unknown"


async def configure_adapter(rpc_call: RpcFn) -> BridgeAdapterConfig:
    """Negotiate the bridge contract and extract capability metadata.

    WHY: V2 should fail fast on RPC drift rather than discovering mismatches
    mid-survey. Legacy mode never calls this function.
    """
    result = await rpc_call("bridge.contract", {})
    if not isinstance(result, dict) or not result:
        raise ContractMismatchError("bridge.contract returned invalid or empty payload")

    version = str(result.get("version") or "").strip()
    if not version:
        raise ContractMismatchError("bridge.contract returned invalid or empty payload")

    major = version.split(".", 1)[0]
    if major != EXPECTED_CONTRACT_MAJOR:
        raise ContractMismatchError(
            f"Bridge contract major version mismatch: expected {EXPECTED_CONTRACT_MAJOR}, got {major}"
        )

    methods = _normalize_methods(result.get("methods") or {})
    if not methods:
        raise ContractMismatchError("bridge.contract.methods must not be empty")

    idempotent_methods = frozenset(
        name for name, meta in methods.items() if bool(meta.get("idempotent"))
    )
    error_codes = _normalize_error_codes(result)
    surface_kind = _tool_surface_kind(result)

    return BridgeAdapterConfig(
        version=version,
        methods=methods,
        idempotent_methods=idempotent_methods,
        error_codes=error_codes,
        tool_surface_kind=surface_kind,
    )


@dataclass
class OpenSinStack:
    # ========================================================================
    # KLASSE: OpenSinStack
    # ZWECK: 
    # WICHTIG: 
    # METHODEN: 
    # ========================================================================
    
    bridge: BridgeAdapter
    engine: InteractionEngine
    state: StateMachine
    recorder: TraceRecorder
    adapter_mode: str = "legacy"
    adapter_config: BridgeAdapterConfig | None = None


def wrap_legacy_call_with_retry(call_with_retry) -> RpcFn:
    """Adapt ``bridge_retry.call_with_retry`` to the new ``RpcFn`` shape.

    The legacy signature is roughly::

        async def call_with_retry(mcp_call, tool_name, params, ...) -> dict

    We expose the new ``(method, params) -> value`` contract by binding
    the caller-provided ``mcp_call`` once and translating the legacy
    result envelope to either a value or a raised ``BridgeError``.
    """
    from opensin_bridge.contract import classify_error

    def factory(mcp_call) -> RpcFn:
        async def _call(method: str, params: dict[str, Any]) -> Any:
            result = await call_with_retry(mcp_call, method, params or {})
            if isinstance(result, dict) and result.get("error"):
                raise classify_error(result["error"] if isinstance(result["error"], dict) else {"code": "INTERNAL", "message": str(result["error"])})
            if isinstance(result, dict) and result.get("ok") is False:
                raise classify_error({"code": "INTERNAL", "message": str(result.get("reason") or result)})
            if isinstance(result, dict) and "value" in result and set(result.keys()) <= {"ok", "value"}:
                return result["value"]
            return result

        return _call

    return factory


async def make_stack_async(rpc: RpcFn, *, session_id: str | None = None) -> OpenSinStack:
    recorder = TraceRecorder(session_id=session_id)
    # WHY: The new adapter is opt-in so the legacy integration path remains the
    # safe default until the staged rollout is explicitly enabled.
    adapter_mode = "legacy"
    adapter_config: BridgeAdapterConfig | None = None
    if _bridge_mode() == "opensin":
        adapter_mode = "opensin_v2"
        adapter_config = await configure_adapter(rpc)

    bridge_kwargs: dict[str, Any] = {"trace_sink": recorder.emit}
    if adapter_config is not None:
        bridge_kwargs["contract"] = adapter_config.to_bridge_contract()
        bridge_kwargs["inject_idempotency"] = True
    bridge = BridgeAdapter(rpc, **bridge_kwargs)
    engine = InteractionEngine(bridge)
    state = StateMachine(on_transition=lambda t: recorder.emit({"evt": "state", "src": t.src.value, "dst": t.dst.value, "reason": t.reason}))
    return OpenSinStack(
        bridge=bridge,
        engine=engine,
        state=state,
        recorder=recorder,
        adapter_mode=adapter_mode,
        adapter_config=adapter_config,
    )


def make_stack(rpc: RpcFn, *, session_id: str | None = None) -> OpenSinStack:
    return asyncio.run(make_stack_async(rpc, session_id=session_id))
