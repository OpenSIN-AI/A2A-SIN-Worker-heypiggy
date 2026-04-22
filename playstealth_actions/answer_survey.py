"""Answer-survey PlayStealth action."""

from __future__ import annotations


async def run(timeout_seconds: int, index: int, option_index: int) -> int:
    from playstealth_actions.runner_common import answer_survey_flow

    return await answer_survey_flow(timeout_seconds, index, option_index)
