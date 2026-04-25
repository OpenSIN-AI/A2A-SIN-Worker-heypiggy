# ================================================================================
# DATEI: adapter.py
# PROJEKT: A2A-SIN-Worker-heyPiggy (OpenSIN AI Agent System)
# ZWECK: 
# WICHTIG FÜR ENTWICKLER: 
#   - Ändere nichts ohne zu verstehen was passiert
#   - Jeder Kommentar erklärt WARUM etwas getan wird, nicht nur WAS
#   - Bei Fragen erst Code lesen, dann ändern
# ================================================================================

"""Bridge adapter -- contract-aware, idempotency-aware RPC client.

Sits between the worker and the raw JSON-RPC transport (whatever
``bridge_retry.call_bridge`` is). Adds:

* Method validation against the v1 contract.
* Error normalisation to :class:`BridgeError`.
* Retry policy derived from the method's ``retry_hint``.
* Trace emission through ``observability``.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from opensin_bridge.contract import (
    DEFAULT_CONTRACT,
    BridgeContract,
    BridgeError,
    attach_idempotency,
    classify_error,
    get_method,
    retry_hint_for,
    validate_contract_version,
)

RpcCall = Callable[[str, dict[str, Any]], Awaitable[Any]]
TraceSink = Callable[[dict[str, Any]], None]


@dataclass
class BridgeCallResult:
    # ========================================================================
    # KLASSE: BridgeCallResult
    # ZWECK: 
    # WICHTIG: 
    # METHODEN: 
    # ========================================================================
    
    method: str
    ok: bool
    value: Any = None
    error: BridgeError | None = None
    attempts: int = 1
    duration_ms: float = 0.0
    trace_id: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


class BridgeAdapter:
    # ========================================================================
    # KLASSE: BridgeAdapter
    # ZWECK: 
    # WICHTIG: 
    # METHODEN: 
    # ========================================================================
    
    """Stateful bridge client. Instantiate one per worker session."""

    _EXPECTED_MAJOR = "1"

    def __init__(
        self,
        rpc: RpcCall,
        *,
        contract: BridgeContract | None = None,
        trace_sink: TraceSink | None = None,
        max_retries: int = 2,
        retry_backoff: float = 0.35,
        inject_idempotency: bool = False,
        ensure_contract_on_call: bool = False,
    ) -> None:
        self._rpc = rpc
        self._trace_sink = trace_sink or (lambda _evt: None)
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._contract = contract or DEFAULT_CONTRACT
        self._inject_idempotency = inject_idempotency
        self._ensure_contract_on_call = ensure_contract_on_call
        self._contract_checked = False
        self._inflight: dict[str, asyncio.Future[BridgeCallResult]] = {}
        self._inflight_lock = asyncio.Lock()

    async def ensure_contract(self) -> None:
        if self._contract_checked:
            return
        try:
            info = await self._rpc("bridge.contract.version", {})
        except Exception as exc:
            raise classify_error(exc) from exc
        got = (info or {}).get("version", "0.0.0")
        validate_contract_version(got)
        self._contract_checked = True

    async def call(self, method: str, params: dict[str, Any] | None = None) -> BridgeCallResult:
        if self._ensure_contract_on_call and not self._contract_checked:
            await self.ensure_contract()

        if not self._contract.is_method_supported(method):
            raise BridgeError("METHOD_NOT_FOUND", f"unknown bridge method: {method}", retry_hint="abort")

        spec = get_method(method)  # raises METHOD_NOT_FOUND if unknown
        params = dict(params or {})
        trace_id = f"wrk-{uuid.uuid4().hex[:12]}"
        started = time.perf_counter()
        hint = retry_hint_for(method)
        max_attempts = 1 if hint == "abort" or not spec.idempotent else self._max_retries + 1

        idempotency_key: str | None = None
        inflight_future: asyncio.Future[BridgeCallResult] | None = None
        await_existing: asyncio.Future[BridgeCallResult] | None = None
        if self._inject_idempotency:
            envelope = attach_idempotency({"tool": method, "params": params}, method=method, idempotent=spec.idempotent)
            idempotency_key = str(envelope["idempotency_key"])
            if spec.idempotent:
                loop = asyncio.get_running_loop()
                async with self._inflight_lock:
                    inflight_future = self._inflight.get(idempotency_key)
                    if inflight_future is None:
                        inflight_future = loop.create_future()
                        self._inflight[idempotency_key] = inflight_future
                    else:
                        await_existing = inflight_future

        if await_existing is not None:
            return await await_existing

        last_error: BridgeError | None = None
        attempt = 0
        result: BridgeCallResult | None = None
        try:
            for attempt in range(1, max_attempts + 1):
                self._trace_sink(
                    {
                        "evt": "bridge.call.start",
                        "trace_id": trace_id,
                        "method": method,
                        "attempt": attempt,
                        "idempotent": spec.idempotent,
                    }
                )
                try:
                    value = await self._rpc(method, params)
                    duration = (time.perf_counter() - started) * 1000.0
                    self._trace_sink(
                        {
                            "evt": "bridge.call.ok",
                            "trace_id": trace_id,
                            "method": method,
                            "attempt": attempt,
                            "duration_ms": duration,
                        }
                    )
                    result = BridgeCallResult(
                        method=method,
                        ok=True,
                        value=value,
                        attempts=attempt,
                        duration_ms=duration,
                        trace_id=trace_id,
                        meta={"idempotency_key": idempotency_key} if idempotency_key else {},
                    )
                    break
                except Exception as raw:
                    err = classify_error(raw)
                    last_error = err
                    self._trace_sink(
                        {
                            "evt": "bridge.call.err",
                            "trace_id": trace_id,
                            "method": method,
                            "attempt": attempt,
                            "code": err.code,
                            "retry_hint": err.retry_hint,
                        }
                    )
                    if err.retry_hint == "abort" or attempt >= max_attempts:
                        result = BridgeCallResult(
                            method=method,
                            ok=False,
                            error=last_error,
                            attempts=attempt,
                            duration_ms=(time.perf_counter() - started) * 1000.0,
                            trace_id=trace_id,
                            meta={"idempotency_key": idempotency_key} if idempotency_key else {},
                        )
                        break
                    await asyncio.sleep(self._retry_backoff * attempt)

            assert result is not None
            return result
        finally:
            if inflight_future is not None and idempotency_key is not None:
                if not inflight_future.done() and result is not None:
                    inflight_future.set_result(result)
                elif not inflight_future.done():
                    inflight_future.cancel()
                async with self._inflight_lock:
                    self._inflight.pop(idempotency_key, None)

    async def __call__(self, method: str, **params: Any) -> Any:
        """Convenience: call and unwrap, raising BridgeError on failure."""
        res = await self.call(method, params)
        if res.ok:
            return res.value
        assert res.error is not None
        raise res.error


def configure_adapter(
    rpc: RpcCall,
    *,
    contract: BridgeContract | None = None,
    trace_sink: TraceSink | None = None,
    max_retries: int = 2,
    retry_backoff: float = 0.35,
    inject_idempotency: bool = True,
    ensure_contract_on_call: bool = True,
) -> BridgeAdapter:
    """Factory for a contract-aware adapter with opt-in idempotency."""

    return BridgeAdapter(
        rpc,
        contract=contract,
        trace_sink=trace_sink,
        max_retries=max_retries,
        retry_backoff=retry_backoff,
        inject_idempotency=inject_idempotency,
        ensure_contract_on_call=ensure_contract_on_call,
    )
