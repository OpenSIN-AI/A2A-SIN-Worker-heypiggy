"""AI backend selector.

The worker's vision / reasoning loop should never hard-code a vendor name.
It calls :func:`select_backend` once at boot, gets back an :class:`AIBackend`
implementation, and uses that for every prompt.

Why this exists:

* **Decoupling the loop from the vendor.** Today the monolith calls vendor
  SDKs directly. Phase 1 (see ``docs/PLANS/04-MIGRATION-ROADMAP.md``) moves
  every call behind this seam. After that, switching vendors is a one-liner
  in env config, not a code change.
* **Fail-closed defaults.** If no backend is configured, ``select_backend``
  raises rather than silently no-op'ing. The worker should refuse to start
  in that state.
* **Honest about Puter.** Puter is registered as an *optional fallback* for
  non-vision-critical text tasks only, behind a feature flag, with the
  trade-offs documented in the docstring. It is **not** the primary backend.

Status: Skeleton. ``AIGatewayBackend.call()`` body lands in Phase 1; today
the class exists with the typed surface and a ``NotImplementedError`` so a
half-baked impl can't sneak into production.
"""

from __future__ import annotations

import abc
import enum
import os
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


# --------------------------------------------------------------------------- #
# Errors & result type
# --------------------------------------------------------------------------- #


class AIBackendError(RuntimeError):
    """Any failure produced by a concrete backend.

    We attach ``provider`` + ``model`` so the worker's audit log can attribute
    the failure to a specific vendor and route around it.
    """

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        model: str | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.retryable = retryable


@dataclass(frozen=True)
class AICallResult:
    """One backend call's outcome.

    Includes the bookkeeping the worker's earnings telemetry needs: which
    provider answered, which model was actually used (Gateway can route),
    how long it took, how many tokens it cost.
    """

    text: str
    provider: str
    model: str
    latency_ms: int
    input_tokens: int = 0
    output_tokens: int = 0
    raw: Mapping[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Abstract backend
# --------------------------------------------------------------------------- #


class AICapability(str, enum.Enum):
    """What the worker is asking the backend to do.

    Backends declare which of these they support. The selector refuses to
    route a ``VISION`` call to a backend that hasn't claimed it.
    """

    TEXT = "text"
    VISION = "vision"
    TOOL_CALL = "tool_call"


class AIBackend(abc.ABC):
    """Stable surface the worker's loop talks to.

    Sub-classes must declare :attr:`name` (used in audit logs), the set of
    :class:`AICapability` they support, and implement :meth:`call`.
    """

    name: str = "abstract"
    capabilities: frozenset[AICapability] = frozenset()

    @abc.abstractmethod
    async def call(
        self,
        prompt: str,
        *,
        images: Sequence[str] = (),
        model: str | None = None,
        capability: AICapability = AICapability.TEXT,
        max_tokens: int | None = None,
    ) -> AICallResult:
        """Run one prompt and return a structured result.

        ``images`` are URLs or data: URIs. ``model`` overrides the backend's
        default; if the backend doesn't support that model it must raise
        :class:`AIBackendError` rather than silently substitute another.
        """

    async def health(self) -> bool:
        """Cheap probe used by the selector to skip dead backends.

        Default impl returns True; concrete backends override with a real
        ping. We deliberately do NOT cache this — the cost of a stale True
        is much higher than the cost of one extra ping.
        """
        return True


# --------------------------------------------------------------------------- #
# Concrete backends — typed contracts only, bodies in Phase 1
# --------------------------------------------------------------------------- #


class AIGatewayBackend(AIBackend):
    """Vercel AI Gateway. **Primary** backend for this worker.

    Why primary:
      * single API key, multi-vendor (OpenAI, Anthropic, Google, Bedrock).
      * native to our runtime (Vercel).
      * audit trail per call (provider, model, latency, tokens).
      * vision multimodal via ``openai/gpt-5-mini``,
        ``anthropic/claude-opus-4.6``, ``google/gemini-3-flash``.
    """

    name = "ai_gateway"
    capabilities = frozenset(
        {AICapability.TEXT, AICapability.VISION, AICapability.TOOL_CALL}
    )

    DEFAULT_TEXT_MODEL = "openai/gpt-5-mini"
    DEFAULT_VISION_MODEL = "openai/gpt-5-mini"

    def __init__(self, *, api_key: str | None = None) -> None:
        # We accept None at construction so the selector can build the object
        # before health() is called; health() will be the one that fails
        # closed if no key is configured.
        self._api_key = api_key or os.environ.get("AI_GATEWAY_API_KEY")

    async def health(self) -> bool:
        return bool(self._api_key)

    async def call(
        self,
        prompt: str,
        *,
        images: Sequence[str] = (),
        model: str | None = None,
        capability: AICapability = AICapability.TEXT,
        max_tokens: int | None = None,
    ) -> AICallResult:
        if not self._api_key:
            raise AIBackendError(
                "AI_GATEWAY_API_KEY not set",
                provider=self.name,
                retryable=False,
            )
        if capability not in self.capabilities:
            raise AIBackendError(
                f"capability {capability.value!r} not supported by {self.name}",
                provider=self.name,
                retryable=False,
            )
        # WHY NotImplementedError instead of a half-baked HTTP call: we want
        # the seam visible in code review and CI. Phase 1 PR fills the body.
        raise NotImplementedError(
            "AIGatewayBackend.call() body lands in Phase 1. "
            "See docs/PLANS/04-MIGRATION-ROADMAP.md"
        )


class PuterFallbackBackend(AIBackend):
    """Puter.ai — **optional fallback only**, never primary for this worker.

    Why this exists at all:
      * cost experiment for non-critical text tasks (e.g. trap classification
        in a side-path).
      * future productization layer (web UI for end users) where the
        User-Pays model actually fits — see docs/PLANS/04-MIGRATION-ROADMAP.md
        Phase 4.

    Why this is NOT primary for the headless worker:
      * Puter requires a signed-in Puter account; in headless we'd run on a
        single account whose session is fragile and bannable as abuse.
      * Adds a proxy hop (worker → puter → vendor) — strictly slower, never
        faster, than a direct AI Gateway call.
      * Audit telemetry (vendor / token usage) is harder to recover.
      * Vendor lock-in to Puter's pricing/policy decisions.

    The full reasoning is in ``docs/PLANS/02-AI-BACKEND-STRATEGY.md``.
    """

    name = "puter_fallback"
    capabilities = frozenset({AICapability.TEXT})  # text only by design

    async def health(self) -> bool:
        # Disabled by default. Only wakes up when explicitly enabled.
        flag = os.environ.get("AI_BACKEND_FALLBACK", "").lower()
        return flag == "puter"

    async def call(
        self,
        prompt: str,
        *,
        images: Sequence[str] = (),
        model: str | None = None,
        capability: AICapability = AICapability.TEXT,
        max_tokens: int | None = None,
    ) -> AICallResult:
        if capability is AICapability.VISION:
            raise AIBackendError(
                "Puter fallback intentionally refuses vision calls; "
                "route vision to AI Gateway",
                provider=self.name,
                retryable=False,
            )
        raise NotImplementedError(
            "PuterFallbackBackend lands in Phase 3 (only after AI Gateway "
            "is stable in production). See docs/PLANS/04-MIGRATION-ROADMAP.md"
        )


# --------------------------------------------------------------------------- #
# Selector
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AIBackendSelector:
    """Picks the best healthy backend for a given capability.

    The selector is intentionally trivial: AI Gateway when healthy, Puter
    fallback only when explicitly enabled AND the call is text-only AND
    Gateway is unhealthy. No magic.
    """

    primary: AIBackend
    fallback: AIBackend | None = None

    async def select(self, capability: AICapability) -> AIBackend:
        if await self.primary.health() and capability in self.primary.capabilities:
            return self.primary
        if self.fallback is None:
            raise AIBackendError(
                f"no healthy backend for capability {capability.value!r}",
                provider="selector",
                retryable=True,
            )
        if (
            await self.fallback.health()
            and capability in self.fallback.capabilities
        ):
            return self.fallback
        raise AIBackendError(
            f"primary unhealthy and fallback cannot serve {capability.value!r}",
            provider="selector",
            retryable=True,
        )


def select_backend() -> AIBackendSelector:
    """Module-level convenience used by ``worker.cli``.

    Reads env once and returns a configured selector. Calling this twice
    returns two independent selectors — that's intentional: tests mock the
    selector, production wires it into the loop's context object.
    """
    return AIBackendSelector(
        primary=AIGatewayBackend(),
        fallback=PuterFallbackBackend()
        if os.environ.get("AI_BACKEND_FALLBACK", "").lower() == "puter"
        else None,
    )
