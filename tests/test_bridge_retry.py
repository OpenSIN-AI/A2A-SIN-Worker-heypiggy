import asyncio
import importlib

import pytest

import bridge_retry

worker_retry = importlib.import_module("worker.retry")


@pytest.mark.asyncio
async def test_call_with_retry_supports_custom_jitter_and_retry_hook(monkeypatch):
    calls = {"n": 0}
    retry_events: list[tuple[int, str, float]] = []

    async def fake_bridge(method, params):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"error": "timeout while navigating"}
        return {"ok": True, "method": method, "params": params}

    async def on_retry(attempt: int, error_text: str, delay: float) -> None:
        retry_events.append((attempt, error_text, delay))

    async def no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(worker_retry.random, "uniform", lambda a, b: 0.0)
    monkeypatch.setattr(worker_retry.asyncio, "sleep", no_sleep)

    result = await bridge_retry.call_with_retry(
        fake_bridge,
        "navigate",
        {"url": "https://example.com"},
        max_attempts=3,
        base_delay=1.0,
        max_delay=10.0,
        jitter=0.5,
        on_retry=on_retry,
    )

    assert result == {"ok": True, "method": "navigate", "params": {"url": "https://example.com"}}
    assert calls["n"] == 2
    assert retry_events == [(1, "timeout while navigating", 1.0)]


@pytest.mark.asyncio
async def test_call_with_retry_propagates_cancelled_error() -> None:
    calls = 0

    async def fake_bridge(method, params):
        nonlocal calls
        calls += 1
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await bridge_retry.call_with_retry(fake_bridge, "navigate", {})

    assert calls == 1
