"""Click-survey PlayStealth action."""

from __future__ import annotations


async def run(timeout_seconds: int, index: int) -> int:
    from playstealth_actions.runner_common import click_survey_flow

    return await click_survey_flow(timeout_seconds, index)
