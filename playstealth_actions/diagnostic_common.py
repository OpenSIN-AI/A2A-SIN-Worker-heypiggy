"""Shared diagnostics for PlayStealth.

These helpers are intentionally boring and explicit: they inspect the current
page/context and return small structured payloads so the CLI can stay thin.
"""

from __future__ import annotations

from playstealth_actions.state_store import load_state, state_path


async def detect_popup(page) -> list[dict[str, object]]:
    """Return visible overlay-like elements."""
    return await page.evaluate(
        """
        () => Array.from(document.querySelectorAll('iframe, [role="dialog"], .modal, .overlay'))
          .map(el => ({
            tag: el.tagName,
            id: el.id || '',
            cls: el.className || '',
            text: (el.innerText || '').trim().slice(0, 160),
            visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length),
          }))
        """
    )


async def detect_new_tab(page) -> dict[str, object]:
    """Summarize tabs in the current browser context."""
    return {
        "tab_count": len(page.context.pages),
        "urls": [candidate.url for candidate in page.context.pages],
    }


async def detect_iframe(page) -> list[dict[str, object]]:
    """Summarize iframes in the current page."""
    return await page.evaluate(
        """
        () => Array.from(document.querySelectorAll('iframe')).map(el => ({
          id: el.id || '',
          name: el.getAttribute('name') || '',
          src: el.getAttribute('src') || '',
          visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length),
          html: el.outerHTML.slice(0, 200),
        }))
        """
    )


async def detect_spinner(page) -> dict[str, object]:
    """Look for loading indicators and busy states."""
    return await page.evaluate(
        """
        () => {
          const text = (document.body && document.body.innerText || '').toLowerCase();
          const spinner = Array.from(document.querySelectorAll('[aria-busy="true"], .spinner, .loading, [class*="spinner"], [class*="loading"]'))
            .some(el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length));
          return {
            busy_text: /loading|lade|warte|bitte warten/.test(text),
            spinner,
          };
        }
        """
    )


async def detect_consent(page) -> dict[str, object]:
    """Detect consent language and matching buttons."""
    body = (await page.locator("body").inner_text(timeout=3000)).lower()
    buttons = [
        "button:has-text('Zustimmen und fortfahren')",
        "button:has-text('Zustimmen')",
        "button:has-text('Fortfahren')",
    ]
    matches: list[str] = []
    for selector in buttons:
        if await page.locator(selector).count() > 0:
            matches.append(selector)
    return {
        "has_consent_text": "einwilligung" in body or "zustimmen" in body,
        "buttons": matches,
    }


async def inspect_page(page) -> dict[str, object]:
    """Return a small summary of the active page."""
    return {
        "url": page.url,
        "title": await page.title(),
        "body": (await page.locator("body").inner_text(timeout=3000))[:1000],
    }


async def inspect_tabs(page) -> list[dict[str, object]]:
    """Return a compact view of all open tabs."""
    return [
        {"index": i, "url": tab.url, "closed": tab.is_closed()}
        for i, tab in enumerate(page.context.pages)
    ]


async def inspect_controls(page) -> list[dict[str, object]]:
    """Return the visible controls on the current page."""
    controls = page.locator("button, input, select, textarea, [role='button']")
    count = await controls.count()
    results: list[dict[str, object]] = []
    for i in range(min(count, 40)):
        ctl = controls.nth(i)
        try:
            if not await ctl.is_visible():
                continue
            results.append(
                await ctl.evaluate(
                    "el => ({tag: el.tagName, id: el.id || '', name: el.getAttribute('name') || '', type: el.getAttribute('type') || '', text: (el.innerText || '').trim().slice(0, 120), html: el.outerHTML.slice(0, 250)})"
                )
            )
        except Exception:
            continue
    return results


async def detect_question_type(page) -> dict[str, object]:
    """Guess the current question type from visible controls."""
    modal = page.locator("#survey-modal")
    text = ""
    try:
        text = (await modal.inner_text(timeout=2000)).lower()
    except Exception:
        pass
    checks = {
        "radio": await modal.locator("input[type='radio']").count(),
        "checkbox": await modal.locator("input[type='checkbox']").count(),
        "select": await modal.locator("select").count(),
        "text": await modal.locator("input[type='text']").count(),
        "textarea": await modal.locator("textarea").count(),
        "slider": await modal.locator("input[type='range']").count(),
        "date": await modal.locator("input[type='date']").count(),
        "number": await modal.locator("input[type='number'], input[inputmode='numeric']").count(),
    }
    if checks["slider"]:
        current = "slider"
    elif checks["date"]:
        current = "date"
    elif checks["number"]:
        current = "number"
    elif checks["select"]:
        current = "select"
    elif checks["textarea"]:
        current = "textarea"
    elif checks["text"]:
        current = "text"
    elif checks["radio"] and checks["checkbox"]:
        current = "matrix-or-multi"
    elif checks["radio"]:
        current = "radio"
    elif checks["checkbox"]:
        current = "checkbox"
    else:
        current = "unknown"
    return {"question_type": current, "checks": checks, "text_snippet": text[:300]}


def dump_state() -> dict[str, object] | None:
    """Return the persisted state snapshot."""
    return {"path": str(state_path()), "state": load_state()}
