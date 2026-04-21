"""Handle radio/select survey questions in PlayStealth."""

from __future__ import annotations

import asyncio


async def _resolve_active_page(page):
    pages = [candidate for candidate in page.context.pages if not candidate.is_closed()]
    if not pages:
        return page
    for candidate in reversed(pages):
        if candidate.url and candidate.url != "about:blank":
            if candidate != page:
                print(f"🪟 Switching to active page: {candidate.url}")
            return candidate
    return pages[-1]


async def run(page, option_index: int):
    """Answer one modal question and return the active page."""
    modal = page.locator("#survey-modal")
    visible = await modal.is_visible()
    print(f"🪟 survey-modal visible: {visible}")
    if not visible:
        raise RuntimeError("survey-modal not visible")

    radios = modal.locator("input[type='radio'], input[type='checkbox']")
    count = await radios.count()
    print(f"🎚️ modal inputs: {count}")

    if count == 0:
        select_boxes = modal.locator("select")
        if await select_boxes.count() > 0:
            sel = select_boxes.first
            await sel.select_option(index=min(option_index, 0))
            await asyncio.sleep(0.5)
        start_btn = modal.locator("#start-survey-button")
        if await start_btn.count() > 0:
            try:
                await start_btn.first.evaluate("el => el.click()")
            except Exception:
                try:
                    await page.evaluate(
                        "() => { const el = document.getElementById('start-survey-button'); if (el) el.click(); }"
                    )
                except Exception:
                    await page.evaluate(
                        "() => { if (typeof openSurvey === 'function') openSurvey(); }"
                    )
            await asyncio.sleep(2)
            try:
                src = await page.locator("iframe#frameurl").get_attribute("src")
                print(f"🧩 frameurl src after start: {src!r}")
            except Exception:
                pass
            print("➡️ Start clicked")
            return await _resolve_active_page(page)
        raise RuntimeError("No selectable inputs found in survey modal")

    target = radios.nth(min(option_index, count - 1))
    await target.check(force=True)
    await asyncio.sleep(0.5)

    next_btn = modal.locator(
        "button:has-text('Nächste'), button:has-text('Next'), button:has-text('Weiter')"
    )
    if await next_btn.count() > 0:
        await next_btn.first.click(force=True)
        await asyncio.sleep(2)
        print("➡️ Next clicked")
    else:
        print("⚠️ Kein Next-Button gefunden")
    return await _resolve_active_page(page)
