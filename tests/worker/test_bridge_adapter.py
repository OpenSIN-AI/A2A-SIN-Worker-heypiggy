"""Parity tests for the OpenSIN bridge adapter.

These tests lock the adapter boundary without touching the monolith.
"""

from __future__ import annotations

import asyncio

import pytest

from opensin_bridge.adapter import BridgeAdapter
from opensin_bridge.contract import BridgeError, ContractMismatch


class FakeRpc:
    def __init__(self, answers: dict[str, list[object]]) -> None:
        self.answers = answers
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def __call__(self, method: str, params: dict[str, object]) -> object:
        self.calls.append((method, params))
        answer = self.answers.get(method, [])
        if not answer:
            raise BridgeError("INTERNAL", "no answer configured", retry_hint="retry")
        head = answer.pop(0)
        if isinstance(head, BaseException):
            raise head
        return head


@pytest.mark.asyncio
async def test_ensure_contract_caches_version() -> None:
    rpc = FakeRpc({"bridge.contract.version": [{"version": "1.2.3"}]})
    adapter = BridgeAdapter(rpc)

    await adapter.ensure_contract()
    await adapter.ensure_contract()

    assert len(rpc.calls) == 1


@pytest.mark.asyncio
async def test_ensure_contract_rejects_major_mismatch() -> None:
    rpc = FakeRpc({"bridge.contract.version": [{"version": "2.0.0"}]})
    adapter = BridgeAdapter(rpc)

    with pytest.raises(ContractMismatch):
        await adapter.ensure_contract()


@pytest.mark.asyncio
async def test_idempotent_calls_retry_then_succeed() -> None:
    rpc = FakeRpc(
        {
            "dom.snapshot": [
                BridgeError("RATE_LIMITED", "throttle", retry_hint="retry"),
                {"nodes": [{"name": "ok"}]},
            ]
        }
    )
    adapter = BridgeAdapter(rpc, retry_backoff=0)

    result = await adapter.call("dom.snapshot", {})

    assert result.ok is True
    assert result.attempts == 2


@pytest.mark.asyncio
async def test_non_idempotent_calls_do_not_retry() -> None:
    rpc = FakeRpc(
        {
            "dom.click": [
                BridgeError("RATE_LIMITED", "throttle", retry_hint="retry"),
                {"ok": True},
            ]
        }
    )
    adapter = BridgeAdapter(rpc, retry_backoff=0)

    result = await adapter.call("dom.click", {})

    assert result.ok is False
    assert result.attempts == 1
    assert result.error is not None
    assert result.error.code == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_cancelled_error_propagates_immediately() -> None:
    rpc = FakeRpc({"dom.snapshot": [asyncio.CancelledError()]})
    adapter = BridgeAdapter(rpc, retry_backoff=0)

    with pytest.raises(asyncio.CancelledError):
        await adapter.call("dom.snapshot", {})

    assert len(rpc.calls) == 1
