"""Parity tests for legacy bridge retry vs the new worker stack.

This suite is the Phase 1 gate: it locks classification, backoff behavior,
and cancellation safety before any broader import swaps happen.
"""

from __future__ import annotations

import asyncio
import urllib.error

import pytest

import bridge_retry
from worker.bridge_contract import BridgeRequest, BridgeResponse, call_bridge_with_retry_async
from worker.exceptions import BridgeUnavailableError
from worker.retry import RetryPolicy


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"ok": True}, "ok"),
        ({"error": "timeout while navigating"}, "transient"),
        ({"error": "target closed"}, "transient"),
        ({"error": "unauthorized"}, "permanent"),
        ({"error": {"code": "transport_error"}}, "transient"),
        ({"error": {"code": "rpc_invalid"}}, "permanent"),
        ({"ok": False, "reason": "network error"}, "transient"),
        ({"ok": False, "reason": "invalid parameter"}, "permanent"),
    ],
)
def test_classify_result_parity(payload: object, expected: str) -> None:
    assert bridge_retry.classify_result(payload) == expected


@pytest.mark.asyncio
async def test_transient_retry_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    legacy_calls = 0

    async def legacy_bridge(method: str, params: dict[str, object] | None):
        nonlocal legacy_calls
        legacy_calls += 1
        if legacy_calls < 3:
            return {"error": "timeout while navigating"}
        return {"ok": True, "method": method, "params": params}

    legacy_result = await bridge_retry.call_with_retry(
        legacy_bridge,
        "navigate",
        {"url": "https://example.com"},
        max_attempts=3,
        base_delay=0,
        max_delay=0,
        jitter=0,
    )
    assert legacy_calls == 3
    assert legacy_result["ok"] is True

    new_calls = 0

    def _perform_bridge_request(
        base_url: str,
        request: BridgeRequest,
    ) -> BridgeResponse:
        nonlocal new_calls
        new_calls += 1
        if new_calls < 3:
            raise urllib.error.URLError("temporary")
        return BridgeResponse(ok=True, result={"ok": True}, attempt_count=1)

    monkeypatch.setattr("worker.bridge_contract._perform_bridge_request", _perform_bridge_request)

    new_result = await call_bridge_with_retry_async(
        "https://bridge.example/mcp",
        BridgeRequest(method="tools/call"),
        policy=RetryPolicy(
            max_attempts=3,
            base_delay=0,
            max_delay=0,
            jitter=0,
            retry_on=(urllib.error.URLError,),
        ),
    )
    assert new_calls == 3
    assert new_result.ok is True
    assert new_result.attempt_count == 3


@pytest.mark.asyncio
async def test_permanent_and_cancellation_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    legacy_calls = 0

    async def legacy_permanent(method: str, params: dict[str, object] | None):
        nonlocal legacy_calls
        legacy_calls += 1
        return {"error": "unauthorized"}

    legacy_result = await bridge_retry.call_with_retry(
        legacy_permanent,
        "navigate",
        {},
        max_attempts=5,
        base_delay=0,
        max_delay=0,
        jitter=0,
    )
    assert legacy_calls == 1
    assert bridge_retry.classify_result(legacy_result) == "permanent"

    new_calls = 0

    def _permanent_bridge_request(
        base_url: str,
        request: BridgeRequest,
    ) -> BridgeResponse:
        nonlocal new_calls
        new_calls += 1
        raise BridgeUnavailableError("bridge returned caller error", method=request.method)

    monkeypatch.setattr("worker.bridge_contract._perform_bridge_request", _permanent_bridge_request)

    with pytest.raises(BridgeUnavailableError):
        await call_bridge_with_retry_async(
            "https://bridge.example/mcp",
            BridgeRequest(method="tools/call"),
            policy=RetryPolicy(
                max_attempts=5,
                base_delay=0,
                max_delay=0,
                jitter=0,
                retry_on=(urllib.error.URLError,),
            ),
        )
    assert new_calls == 1

    cancelled_calls = 0

    async def legacy_cancelled(method: str, params: dict[str, object] | None):
        nonlocal cancelled_calls
        cancelled_calls += 1
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await bridge_retry.call_with_retry(
            legacy_cancelled,
            "navigate",
            {},
            max_attempts=5,
            base_delay=0,
            max_delay=0,
            jitter=0,
        )
    assert cancelled_calls == 1

    async def fake_to_thread(func, *args, **kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr("worker.bridge_contract.asyncio.to_thread", fake_to_thread)

    with pytest.raises(asyncio.CancelledError):
        await call_bridge_with_retry_async(
            "https://bridge.example/mcp",
            BridgeRequest(method="tools/call"),
            policy=RetryPolicy(
                max_attempts=5,
                base_delay=0,
                max_delay=0,
                jitter=0,
                retry_on=(urllib.error.URLError,),
            ),
        )
