"""worker.integrations — adapter clients for external SIN CLIs.

Status: Skeletons only. Each module here is a *typed contract* that we want
to migrate to in Phase 2 (siehe docs/PLANS/04-MIGRATION-ROADMAP.md). The
concrete network / subprocess wiring is intentionally NOT in main yet — this
package exists so that:

  1. The contract is checked in and reviewable before the migration PRs.
  2. Tests can pin against the public surface today.
  3. Phase 2 PRs only need to fill in the bodies, not redesign the surface.

WHY this matters: re-architecting *and* shipping a behaviour change in the
same PR is the failure mode that produced the branch zoo we just cleaned up.
We are deliberately splitting "agree on the seam" from "plug in the seam".
"""

from worker.integrations.playstealth_client import (
    PlaystealthClient,
    PlaystealthError,
    PlaystealthResult,
)
from worker.integrations.unmask_client import (
    UnmaskClient,
    UnmaskError,
    UnmaskResponse,
)

__all__ = [
    "PlaystealthClient",
    "PlaystealthError",
    "PlaystealthResult",
    "UnmaskClient",
    "UnmaskError",
    "UnmaskResponse",
]
