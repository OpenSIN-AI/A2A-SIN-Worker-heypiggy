"""Unit tests for :mod:`worker.retry`."""

from __future__ import annotations

import asyncio
import random
from unittest.mock import AsyncMock, MagicMock

import pytest

from worker import retry as retry_alias, retry_async as retry_async_alias
from worker.exceptions import BridgeTimeoutError, VisionRateLimitError
from worker.retry import RetryPolicy, retry_async


class TestRetryPolicy:
    def test_monotonic_backoff(self) -> None:
        policy = RetryPolicy(base_delay=1.0, jitter=0)
        delays = [policy.compute_delay(i) for i in range(1, 5)]
        assert delays == [1.0, 2.0, 4.0, 8.0]

    def test_max_delay_cap(self) -> None:
        policy = RetryPolicy(base_delay=1.0, max_delay=5.0, jitter=0)
        assert policy.compute_delay(4) == 5.0

    def test_jitter_within_bounds(self) -> None:
        policy = RetryPolicy(base_delay=1.0, jitter=0.2)
        rng = random.Random(1234)
        for _ in range(100):
            delay = policy.compute_delay(1, rng=rng)
            assert 0.8 <= delay <= 1.2

    def test_defaults_are_explicit(self) -> None:
        policy = RetryPolicy()
        assert policy.max_attempts == 3
        assert policy.retry_on == (Exception,)
        assert policy.log_level == "DEBUG"

    @pytest.mark.parametrize("max_attempts", [0, -1])
    def test_rejects_bad_attempts(self, max_attempts: int) -> None:
        with pytest.raises(ValueError, match="max_attempts"):
            RetryPolicy(max_attempts=max_attempts)

    @pytest.mark.parametrize("jitter", [-0.1, 1.5])
    def test_rejects_bad_jitter(self, jitter: float) -> None:
        with pytest.raises(ValueError, match="jitter"):
            RetryPolicy(jitter=jitter)

    def test_rejects_negative_delay(self) -> None:
        with pytest.raises(ValueError, match="delays"):
            RetryPolicy(base_delay=-1)

    def test_rejects_empty_retry_on(self) -> None:
        with pytest.raises(ValueError, match="retry_on"):
            RetryPolicy(retry_on=())

    def test_rejects_bad_log_level(self) -> None:
        with pytest.raises(ValueError, match="log_level"):
            RetryPolicy(log_level="TRACE")


class TestRetryDecorator:
    async def test_succeeds_first_try(self) -> None:
        calls = 0

        @retry_async(RetryPolicy(max_attempts=3, base_delay=0, jitter=0))
        async def f() -> str:
            nonlocal calls
            calls += 1
            return "ok"

        assert await f() == "ok"
        assert calls == 1

    async def test_retries_on_listed_exception(self) -> None:
        calls = 0

        @retry_async(
            RetryPolicy(
                max_attempts=3,
                base_delay=0,
                jitter=0,
                retry_on=(BridgeTimeoutError,),
            )
        )
        async def flaky() -> str:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise BridgeTimeoutError("timeout", attempt=calls)
            return "ok"

        assert await flaky() == "ok"
        assert calls == 3

    async def test_does_not_retry_other_exceptions(self) -> None:
        calls = 0

        @retry_async(
            RetryPolicy(
                max_attempts=3,
                base_delay=0,
                jitter=0,
                retry_on=(BridgeTimeoutError,),
            )
        )
        async def f() -> str:
            nonlocal calls
            calls += 1
            raise VisionRateLimitError("quota")

        with pytest.raises(VisionRateLimitError):
            await f()
        assert calls == 1

    async def test_exhausts_after_max_attempts(self) -> None:
        calls = 0

        @retry_async(RetryPolicy(max_attempts=2, base_delay=0, jitter=0))
        async def always_fails() -> None:
            nonlocal calls
            calls += 1
            raise RuntimeError("bad")

        with pytest.raises(RuntimeError, match="bad"):
            await always_fails()
        assert calls == 2

    async def test_passes_through_args_kwargs(self) -> None:
        @retry_async(RetryPolicy(max_attempts=1, base_delay=0, jitter=0))
        async def add(a: int, b: int, *, c: int) -> int:
            return a + b + c

        assert await add(1, 2, c=3) == 6

    async def test_actually_sleeps_between_attempts(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)

        @retry_async(RetryPolicy(max_attempts=3, base_delay=0.5, jitter=0))
        async def always_fails() -> None:
            raise RuntimeError("x")

        with pytest.raises(RuntimeError):
            await always_fails()

        assert sleeps == [0.5, 1.0]

    async def test_on_retry_callback_is_invoked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        events: list[tuple[int, str, float]] = []

        async def fake_sleep(seconds: float) -> None:
            return None

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)

        def on_retry(attempt: int, exc: BaseException, delay: float):
            events.append((attempt, type(exc).__name__, delay))

        @retry_async(
            RetryPolicy(max_attempts=2, base_delay=0.5, jitter=0),
            on_retry=on_retry,
        )
        async def always_fails() -> None:
            raise RuntimeError("x")

        with pytest.raises(RuntimeError):
            await always_fails()

        assert events == [(1, "RuntimeError", 0.5)]

    async def test_structured_retry_logging(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = 0
        log = MagicMock()
        retry_module = __import__("worker.retry", fromlist=["_log"])
        monkeypatch.setattr(retry_module, "_log", log)
        monkeypatch.setattr(asyncio, "sleep", AsyncMock())

        @retry_async(
            RetryPolicy(
                max_attempts=2,
                base_delay=0,
                jitter=0,
                retry_on=(BridgeTimeoutError,),
                log_level="debug",
            )
        )
        async def flaky() -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise BridgeTimeoutError("timeout", attempt=calls)
            return "ok"

        assert await flaky() == "ok"
        assert calls == 2
        assert log.debug.call_count == 1
        event_name = log.debug.call_args.args[0]
        assert event_name == "retry_attempt"

    async def test_cancelled_error_is_never_retried(self) -> None:
        calls = 0

        @retry_async(RetryPolicy(max_attempts=5, base_delay=0, jitter=0, retry_on=(Exception,)))
        async def cancelled() -> None:
            nonlocal calls
            calls += 1
            raise asyncio.CancelledError

        with pytest.raises(asyncio.CancelledError):
            await cancelled()
        assert calls == 1, "CancelledError must never be retried"

    async def test_cancelled_error_passes_through_even_with_base_exception(self) -> None:
        calls = 0

        @retry_async(
            RetryPolicy(max_attempts=5, base_delay=0, jitter=0, retry_on=(BaseException,))
        )
        async def cancelled() -> None:
            nonlocal calls
            calls += 1
            raise asyncio.CancelledError

        with pytest.raises(asyncio.CancelledError):
            await cancelled()
        assert calls == 1

    async def test_keyboard_interrupt_is_never_retried(self) -> None:
        calls = 0

        @retry_async(
            RetryPolicy(max_attempts=5, base_delay=0, jitter=0, retry_on=(BaseException,))
        )
        async def interrupted() -> None:
            nonlocal calls
            calls += 1
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            await interrupted()
        assert calls == 1

    async def test_system_exit_is_never_retried(self) -> None:
        calls = 0

        @retry_async(
            RetryPolicy(max_attempts=5, base_delay=0, jitter=0, retry_on=(BaseException,))
        )
        async def exiting() -> None:
            nonlocal calls
            calls += 1
            raise SystemExit(1)

        with pytest.raises(SystemExit):
            await exiting()
        assert calls == 1

    async def test_retry_alias_compatibility(self) -> None:
        calls = 0

        @retry_alias(attempts=2, base_delay=0, jitter=0, retry_on=(BridgeTimeoutError,))
        async def flaky() -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise BridgeTimeoutError("timeout", attempt=calls)
            return "ok"

        assert await flaky() == "ok"
        assert calls == 2

    async def test_retry_async_alias_is_importable(self) -> None:
        assert retry_async_alias is retry_async
