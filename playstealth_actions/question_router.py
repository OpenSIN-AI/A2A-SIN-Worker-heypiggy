"""Survey question router for PlayStealth.

This router inspects the visible modal and dispatches to one of the tiny
question modules. That keeps the CLI thin while preserving per-tool files.
"""

from __future__ import annotations

import asyncio

from playstealth_actions.page_utils import resolve_active_page
from playstealth_actions import (
    date_question,
    matrix_question,
    number_question,
    rank_order_question,
    select_question,
    slider_question,
    text_question,
    textarea_question,
)


async def _click_visible_start(page, modal):
    """Click the visible survey start / next button."""
    selectors = [
        "#start-survey-button",
        "#submit-button-cpx",
        "button:has-text('Nächste')",
        "button:has-text('Next')",
        "button:has-text('Weiter')",
        "button:has-text('Umfrage starten')",
    ]
    for selector in selectors:
        btn = modal.locator(selector)
        if await btn.count() == 0:
            continue
        try:
            await btn.first.evaluate("el => el.click()")
        except Exception:
            try:
                await page.evaluate(
                    "sel => { const el = document.querySelector(sel); if (el) el.click(); }",
                    selector,
                )
            except Exception:
                await page.evaluate("() => { if (typeof openSurvey === 'function') openSurvey(); }")
        await asyncio.sleep(2)
        print(f"➡️ clicked {selector}")
        return True
    return False


async def run(page, option_index: int):
    """Answer one question step and return the current active page."""
    modal = page.locator("#survey-modal")
    visible = await modal.is_visible()
    print(f"🪟 survey-modal visible: {visible}")
    if not visible:
        raise RuntimeError("survey-modal not visible")

    # Inspect the visible inputs once and dispatch by what is actually on screen.
    if await modal.locator("input[type='range']").count() > 0:
        return await slider_question.run(page)
    if await modal.locator("input[type='date']").count() > 0:
        return await date_question.run(page)
    if await modal.locator("input[type='number'], input[inputmode='numeric']").count() > 0:
        return await number_question.run(page)
    if await modal.locator("select").count() > 0:
        return await select_question.run(page, option_index)
    if await modal.locator("textarea").count() > 0:
        return await textarea_question.run(page, "Keine Angabe")
    if await modal.locator("input[type='text']").count() > 0:
        return await text_question.run(page, "Keine Angabe")

    if await modal.locator("table, .matrix, .grid, [data-question-type='matrix']").count() > 0:
        return await matrix_question.run(page, option_index)
    if await modal.locator(".rank-order, [data-question-type='rank-order']").count() > 0:
        return await rank_order_question.run(page)

    # Radios/checkboxes are the most common layout, so we handle them first.
    inputs = modal.locator("input[type='radio'], input[type='checkbox']")
    input_count = await inputs.count()
    print(f"🎚️ modal inputs: {input_count}")

    if input_count > 0:
        target = inputs.nth(min(option_index, input_count - 1))
        input_type = (await target.get_attribute("type") or "").lower()
        if input_type == "checkbox":
            await target.check(force=True)
        else:
            await target.check(force=True)
        await asyncio.sleep(0.5)

        if not await _click_visible_start(page, modal):
            raise RuntimeError("Selectable input found but no Next button matched")
        return await resolve_active_page(page)

    selects = modal.locator("select")
    select_count = await selects.count()
    if select_count > 0:
        sel = selects.first
        try:
            # Pick the first real option (skip the empty placeholder if present).
            await sel.select_option(index=1)
        except Exception:
            await sel.select_option(index=0)
        await asyncio.sleep(0.5)
        if not await _click_visible_start(page, modal):
            raise RuntimeError("Select found but no Next button matched")
        return await resolve_active_page(page)

    textareas = modal.locator("textarea, input[type='text']")
    text_count = await textareas.count()
    if text_count > 0:
        field = textareas.first
        await field.fill("Keine Angabe")
        await asyncio.sleep(0.5)
        if not await _click_visible_start(page, modal):
            raise RuntimeError("Text field found but no Next button matched")
        return await resolve_active_page(page)

    # Fallback: if we only see the consent/start view, click the visible action.
    if await _click_visible_start(page, modal):
        return await resolve_active_page(page)

    raise RuntimeError("Unsupported survey question layout")
