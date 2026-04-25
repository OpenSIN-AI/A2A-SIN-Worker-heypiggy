"""Unit tests for the isolated bridge adapter."""

from __future__ import annotations

import asyncio

import pytest

from opensin_bridge.adapter import BridgeAdapter, configure_adapter
from opensin_bridge.contract import BridgeContract, BridgeError, ContractMismatch


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
async def test_version_mismatch_on_first_call() -> None:
    rpc = FakeRpc(
        {
            "bridge.contract.version": [{"version": "2.0.0"}],
            "dom.snapshot": [{"nodes": []}],
        }
    )
    adapter = configure_adapter(rpc)

    with pytest.raises(ContractMismatch):
        await adapter.call("dom.snapshot", {})

    assert rpc.calls[0][0] == "bridge.contract.version"


@pytest.mark.asyncio
async def test_unknown_method_can_be_rejected_by_contract() -> None:
    contract = BridgeContract(
        required_methods=frozenset({"dom.snapshot"}),
        required_error_codes=frozenset({"timeout"}),
        idempotent_methods=frozenset({"dom.snapshot"}),
    )
    rpc = FakeRpc({})
    adapter = BridgeAdapter(rpc, contract=contract)

    with pytest.raises(BridgeError, match="METHOD_NOT_FOUND"):
        await adapter.call("dom.click", {})

    assert rpc.calls == []


@pytest.mark.asyncio
async def test_idempotent_calls_deduplicate_in_flight(monkeypatch: pytest.MonkeyPatch) -> None:
    started = asyncio.Event()
    proceed = asyncio.Event()
    calls = {"count": 0}

    async def rpc(method: str, params: dict[str, object]) -> object:
        calls["count"] += 1
        if method == "bridge.contract.version":
            return {"version": "1.2.3"}
        if method == "dom.snapshot":
            started.set()
            await proceed.wait()
            return {"nodes": [{"name": "ok"}]}
        raise BridgeError("INTERNAL", f"unexpected method {method}", retry_hint="retry")

    adapter = configure_adapter(rpc, retry_backoff=0)
    await adapter.ensure_contract()

    first = asyncio.create_task(adapter.call("dom.snapshot", {}))
    await started.wait()
    second = asyncio.create_task(adapter.call("dom.snapshot", {}))
    await asyncio.sleep(0)

    assert calls["count"] == 2  # version handshake + one snapshot call

    proceed.set()
    first_result = await first
    second_result = await second

    assert first_result.ok is True
    assert second_result.ok is True
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_non_idempotent_calls_do_not_deduplicate() -> None:
    rpc = FakeRpc(
        {
            "bridge.contract.version": [{"version": "1.2.3"}],
            "dom.click": [
                BridgeError("TARGET_NOT_FOUND", "gone", retry_hint="retry-after-refresh"),
                BridgeError("TARGET_NOT_FOUND", "still gone", retry_hint="retry-after-refresh"),
            ],
        }
    )
    adapter = configure_adapter(rpc, retry_backoff=0)
    await adapter.ensure_contract()

    result = await adapter.call("dom.click", {})

    assert result.ok is False
    assert result.attempts == 1
    assert result.error is not None
