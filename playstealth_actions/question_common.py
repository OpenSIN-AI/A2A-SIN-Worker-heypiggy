"""Shared helpers for question-specific PlayStealth modules.

Each question type gets its own tiny module, but the actual mechanics live
here so the CLI stays modular without duplicating DOM logic everywhere.
"""

from __future__ import annotations

import asyncio
from datetime import date

from playstealth_actions.page_utils import resolve_active_page


async def _click_next(page, modal) -> bool:
    """Click the most likely next/submit/start button."""
    selectors = [
        "#submit-button-cpx",
        "#start-survey-button",
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
                await btn.first.click(force=True)
            except Exception:
                continue
        await asyncio.sleep(1.5)
        print(f"➡️ clicked {selector}")
        return True
    return False


async def _visible_modal(page):
    modal = page.locator("#survey-modal")
    if not await modal.is_visible():
        raise RuntimeError("survey-modal not visible")
    print(f"🪟 survey-modal visible: True")
    return modal


async def run_select(page, option_index: int = 0):
    """Handle select/dropdown questions."""
    modal = await _visible_modal(page)
    selects = modal.locator("select")
    if await selects.count() == 0:
        raise RuntimeError("No select element found")
    sel = selects.first
    try:
        await sel.select_option(index=max(0, option_index))
    except Exception:
        await sel.select_option(index=0)
    await asyncio.sleep(0.5)
    if await _click_next(page, modal):
        return await resolve_active_page(page)
    raise RuntimeError("Select question found but next click failed")


async def run_text(page, text: str = "Keine Angabe"):
    """Handle short text questions."""
    modal = await _visible_modal(page)
    fields = modal.locator("input[type='text'], input:not([type]), textarea")
    if await fields.count() == 0:
        raise RuntimeError("No text field found")
    field = fields.first
    await field.fill(text)
    await asyncio.sleep(0.4)
    if await _click_next(page, modal):
        return await resolve_active_page(page)
    raise RuntimeError("Text question found but next click failed")


async def run_textarea(page, text: str = "Keine Angabe"):
    """Handle long free-text questions."""
    return await run_text(page, text)


async def run_matrix(page, option_index: int = 0):
    """Handle matrix/grid questions by choosing the first visible answer."""
    modal = await _visible_modal(page)
    options = modal.locator("input[type='radio'], input[type='checkbox']")
    if await options.count() == 0:
        raise RuntimeError("No matrix options found")
    await options.nth(min(option_index, (await options.count()) - 1)).check(force=True)
    await asyncio.sleep(0.5)
    if await _click_next(page, modal):
        return await resolve_active_page(page)
    raise RuntimeError("Matrix question found but next click failed")


async def run_slider(page):
    """Handle slider questions by nudging to a middle value."""
    modal = await _visible_modal(page)
    sliders = modal.locator("input[type='range']")
    if await sliders.count() == 0:
        raise RuntimeError("No slider found")
    slider = sliders.first
    await slider.evaluate(
        "el => { const min = Number(el.min || 0); const max = Number(el.max || 100); const v = Math.round((min + max) / 2); el.value = String(v); el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }"
    )
    await asyncio.sleep(0.5)
    if await _click_next(page, modal):
        return await resolve_active_page(page)
    raise RuntimeError("Slider question found but next click failed")


async def run_date(page):
    """Handle date questions with today's date."""
    modal = await _visible_modal(page)
    fields = modal.locator("input[type='date']")
    if await fields.count() == 0:
        raise RuntimeError("No date field found")
    await fields.first.fill(date.today().isoformat())
    await asyncio.sleep(0.4)
    if await _click_next(page, modal):
        return await resolve_active_page(page)
    raise RuntimeError("Date question found but next click failed")


async def run_rank_order(page):
    """Handle rank-order by clicking the first plausible option."""
    return await run_matrix(page, 0)


async def run_number(page, value: str = "1"):
    """Handle numeric input questions."""
    modal = await _visible_modal(page)
    fields = modal.locator("input[type='number'], input[inputmode='numeric']")
    if await fields.count() == 0:
        raise RuntimeError("No numeric field found")
    await fields.first.fill(value)
    await asyncio.sleep(0.4)
    if await _click_next(page, modal):
        return await resolve_active_page(page)
    raise RuntimeError("Number question found but next click failed")
