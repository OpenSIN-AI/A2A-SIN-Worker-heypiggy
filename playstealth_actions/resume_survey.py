"""Resume the last saved PlayStealth survey session."""

from __future__ import annotations


async def run(timeout_seconds: int, max_steps: int) -> int:
    from playstealth_actions.runner_common import resume_last_flow

    return await resume_last_flow(timeout_seconds, max_steps)
