"""Run-survey PlayStealth action."""

from __future__ import annotations


async def run(timeout_seconds: int, index: int, max_steps: int) -> int:
    from playstealth_actions.runner_common import run_survey_flow

    return await run_survey_flow(timeout_seconds, index, max_steps)
