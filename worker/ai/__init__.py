"""worker.ai — AI backend abstraction.

Single entry point: ``select_backend()``. Concrete backends live in this
package and are NEVER imported directly by the loop — the loop only knows
about the abstract :class:`AIBackend` interface.

See ``docs/PLANS/02-AI-BACKEND-STRATEGY.md`` for the rationale, in
particular why Puter is **not** the primary backend for a headless worker.
"""

from worker.ai.backend import (
    AIBackend,
    AIBackendError,
    AICallResult,
    AIBackendSelector,
    select_backend,
)

__all__ = [
    "AIBackend",
    "AIBackendError",
    "AICallResult",
    "AIBackendSelector",
    "select_backend",
]
