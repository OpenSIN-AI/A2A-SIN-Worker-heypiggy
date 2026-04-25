"""Dependency-free async retry helpers.

The worker uses this for bridge / vision / network calls that may fail
transiently. It intentionally does not depend on ``tenacity`` or any other
third-party retry library.

Strict cancellation safety is built in: ``asyncio.CancelledError``,
``KeyboardInterrupt`` and ``SystemExit`` are never retried, even if the
caller asks to retry ``BaseException``.
"""

from __future__ import annotations

import asyncio
import inspect
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any, Final, TypeVar, cast

from worker.logging import get_logger

_log = get_logger(__name__)

T = TypeVar("T")
AsyncFn = Callable[..., Awaitable[T]]

_ALWAYS_RERAISE: Final[tuple[type[BaseException], ...]] = (
    asyncio.CancelledError,
    KeyboardInterrupt,
    SystemExit,
)

_VALID_LOG_LEVELS: Final[frozenset[str]] = frozenset(
    {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Retry policy description for :func:`retry_async`."""

    max_attempts: int = 3
    base_delay: float = 0.5
    max_delay: float = 10.0
    jitter: float = 0.2
    retry_on: tuple[type[BaseException], ...] = (Exception,)
    log_level: str = "DEBUG"

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.base_delay < 0 or self.max_delay < 0:
            raise ValueError("delays must be non-negative")
        if self.jitter < 0 or self.jitter > 1:
            raise ValueError("jitter must be in [0, 1]")
        normalized_level = self.log_level.upper()
        if normalized_level not in _VALID_LOG_LEVELS:
            raise ValueError(f"log_level must be one of {sorted(_VALID_LOG_LEVELS)}")
        if not self.retry_on:
            raise ValueError("retry_on must not be empty")
        for exc_type in self.retry_on:
            if not isinstance(exc_type, type) or not issubclass(exc_type, BaseException):
                raise TypeError("retry_on entries must be exception classes")
        object.__setattr__(self, "log_level", normalized_level)

    @property
    def attempts(self) -> int:
        """Backward-compatible alias for ``max_attempts``."""
        return self.max_attempts

    def compute_delay(self, attempt: int, *, rng: random.Random | None = None) -> float:
        """Compute the backoff delay for a failed attempt.

        ``attempt`` is 1-indexed and refers to the attempt that just failed.
        The returned delay is the wait time before the *next* retry.
        """
        if attempt < 1:
            raise ValueError("attempt must be >= 1")

        raw_delay = self.base_delay * (2 ** (attempt - 1))
        raw_delay = min(raw_delay, self.max_delay)
        if self.jitter:
            uniform = rng.uniform if rng is not None else random.uniform
            raw_delay *= 1 + uniform(-self.jitter, self.jitter)
        return max(0.0, raw_delay)


def _emit_retry_log(level: str, event: str, **data: Any) -> None:
    method = cast(Callable[..., Any] | None, getattr(_log, level.lower(), None))
    if method is None:
        _log.debug(event, **data)
        return
    method(event, **data)


def retry_async(
    policy: RetryPolicy,
    *,
    on_retry: Callable[[int, BaseException, float], Awaitable[None] | None] | None = None,
) -> Callable[[AsyncFn[T]], AsyncFn[T]]:
    """Decorate an async callable with exponential-backoff retries."""

    def decorator(fn: AsyncFn[T]) -> AsyncFn[T]:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            for attempt in range(1, policy.max_attempts + 1):
                try:
                    return await fn(*args, **kwargs)
                except _ALWAYS_RERAISE:
                    raise
                except policy.retry_on as exc:
                    if attempt >= policy.max_attempts:
                        _log.warning(
                            "retry_exhausted",
                            function=fn.__qualname__,
                            attempts=attempt,
                            exc=exc,
                        )
                        raise

                    delay = policy.compute_delay(attempt)
                    _emit_retry_log(
                        policy.log_level,
                        "retry_attempt",
                        function=fn.__qualname__,
                        attempt=attempt,
                        next_attempt=attempt + 1,
                        delay_seconds=round(delay, 3),
                        exc=exc,
                    )
                    if on_retry is not None:
                        maybe = on_retry(attempt, exc, delay)
                        if inspect.isawaitable(maybe):
                            await maybe
                    await asyncio.sleep(delay)

            raise RuntimeError("unreachable retry loop exit")  # pragma: no cover

        return wrapper

    return decorator


def retry(
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    jitter: float = 0.2,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    log_level: str = "DEBUG",
) -> Callable[[AsyncFn[T]], AsyncFn[T]]:
    """Backward-compatible wrapper around :func:`retry_async`."""
    policy = RetryPolicy(
        max_attempts=attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        jitter=jitter,
        retry_on=retry_on,
        log_level=log_level,
    )
    return retry_async(policy)


__all__ = ["RetryPolicy", "retry", "retry_async"]
