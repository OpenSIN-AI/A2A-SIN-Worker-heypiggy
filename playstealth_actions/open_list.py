"""Open-list PlayStealth action."""

from __future__ import annotations


async def run(timeout_seconds: int) -> int:
    from playstealth_actions.runner_common import open_list_flow

    return await open_list_flow(timeout_seconds)
