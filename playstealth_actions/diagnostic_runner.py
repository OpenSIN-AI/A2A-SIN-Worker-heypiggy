"""Browser-backed runner for diagnostics tools."""

from __future__ import annotations

from playstealth_actions.browser_bootstrap import open_browser
from playstealth_actions.diagnostic_common import (
    detect_consent,
    detect_iframe,
    detect_new_tab,
    detect_popup,
    detect_question_type,
    detect_spinner,
    dump_state,
    inspect_controls,
    inspect_page,
    inspect_tabs,
)


async def run(tool: str, timeout_seconds: int = 300) -> int:
    """Open the browser and run a diagnostics tool."""
    if tool == "dump-state":
        print(dump_state())
        return 0

    playwright, context, page = await open_browser()
    try:
        if tool == "detect-popup":
            print(await detect_popup(page))
        elif tool == "detect-new-tab":
            print(await detect_new_tab(page))
        elif tool == "detect-iframe":
            print(await detect_iframe(page))
        elif tool == "detect-spinner":
            print(await detect_spinner(page))
        elif tool == "detect-consent":
            print(await detect_consent(page))
        elif tool == "inspect-page":
            print(await inspect_page(page))
        elif tool == "inspect-tabs":
            print(await inspect_tabs(page))
        elif tool == "inspect-controls":
            print(await inspect_controls(page))
        elif tool == "detect-question-type":
            print(await detect_question_type(page))
        else:
            raise ValueError(f"Unsupported diagnostic tool: {tool}")
        return 0
    finally:
        await context.close()
        await playwright.stop()
