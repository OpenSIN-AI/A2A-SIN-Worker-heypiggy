"""Inspect-survey PlayStealth action."""

from __future__ import annotations


async def run(timeout_seconds: int, index: int) -> int:
    from playstealth_actions.runner_common import inspect_survey_flow

    return await inspect_survey_flow(timeout_seconds, index)
