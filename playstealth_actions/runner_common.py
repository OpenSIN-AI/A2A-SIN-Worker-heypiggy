"""Shared runtime helpers for PlayStealth command modules."""

from __future__ import annotations

import asyncio

from playwright_stealth_worker import wait_for_manual_login

from playstealth_actions.browser_bootstrap import open_browser
from playstealth_actions.click_card import run as click_card
from playstealth_actions.consent_modal import run as consent_modal
from playstealth_actions.inspect_modal import run as inspect_modal
from playstealth_actions.list_cards import print_cards
from playstealth_actions.page_utils import resolve_active_page
from playstealth_actions.question_router import run as question_router
from playstealth_actions.state_store import save_state
from playstealth_actions.survey_state import create_state
from playstealth_actions.wait_question import run as wait_question


async def wait_for_login(page, timeout_seconds: int) -> bool:
    """Wait for the user to finish logging in manually."""
    return await wait_for_manual_login(page, timeout_seconds=timeout_seconds)


async def open_and_bootstrap():
    """Open browser, wait for login, and return browser handles."""
    playwright, context, page = await open_browser()
    return playwright, context, page


async def open_list_flow(timeout_seconds: int) -> int:
    """Open the list and print available surveys."""
    playwright, context, page = await open_and_bootstrap()
    try:
        if await wait_for_login(page, timeout_seconds):
            print("✅ Login erkannt")
        if page.is_closed() and context.pages:
            page = context.pages[0]
        await asyncio.sleep(1)
        await print_cards(page, context)
        return 0
    finally:
        await context.close()
        await playwright.stop()


async def click_survey_flow(timeout_seconds: int, index: int) -> int:
    """Open the list and click one survey card."""
    playwright, context, page = await open_and_bootstrap()
    try:
        if await wait_for_login(page, timeout_seconds):
            print("✅ Login erkannt")
        if page.is_closed() and context.pages:
            page = context.pages[0]
        await asyncio.sleep(1)
        await print_cards(page, context)
        page = await click_card(page, index)
        return 0
    finally:
        await context.close()
        await playwright.stop()


async def inspect_survey_flow(timeout_seconds: int, index: int) -> int:
    """Open a survey and print its modal."""
    playwright, context, page = await open_and_bootstrap()
    try:
        if await wait_for_login(page, timeout_seconds):
            print("✅ Login erkannt")
        if page.is_closed() and context.pages:
            page = context.pages[0]
        await asyncio.sleep(1)
        await print_cards(page, context)
        page = await click_card(page, index)
        if page.is_closed() and context.pages:
            page = context.pages[-1]
        await asyncio.sleep(2)
        await inspect_modal(page)
        return 0
    finally:
        await context.close()
        await playwright.stop()


async def answer_survey_flow(timeout_seconds: int, index: int, option_index: int) -> int:
    """Open a survey and answer one question step."""
    playwright, context, page = await open_and_bootstrap()
    try:
        if await wait_for_login(page, timeout_seconds):
            print("✅ Login erkannt")
        if page.is_closed() and context.pages:
            page = context.pages[0]
        await asyncio.sleep(1)
        await print_cards(page, context)
        page = await click_card(page, index)
        if page.is_closed() and context.pages:
            page = context.pages[-1]
        await asyncio.sleep(2)
        page = await question_router(page, option_index)
        return 0
    finally:
        await context.close()
        await playwright.stop()


async def run_survey_flow(timeout_seconds: int, index: int, max_steps: int) -> int:
    """Open a survey and step through the common layouts."""
    playwright, context, page = await open_and_bootstrap()
    state = create_state(index)
    try:
        if await wait_for_login(page, timeout_seconds):
            print("✅ Login erkannt")
        if page.is_closed() and context.pages:
            page = context.pages[0]
        await asyncio.sleep(1)
        await print_cards(page, context)
        page = await click_card(page, index)
        if page.is_closed() and context.pages:
            page = context.pages[-1]
        state.mode = "opened"
        state.current_url = page.url
        state.tab_count = len(page.context.pages)
        state.record("survey opened")
        save_state(state)
        page = await resolve_active_page(page)
        try:
            page = await consent_modal(page)
            state.record("consent handled")
            save_state(state)
        except Exception as consent_error:
            print(f"⚠️ Consent handling skipped/failed: {consent_error}")

        for step in range(max_steps):
            state.step = step + 1
            state.current_url = page.url
            state.tab_count = len(page.context.pages)
            await asyncio.sleep(1.5)
            modal = page.locator("#survey-modal")
            if not await modal.is_visible():
                print(f"✅ Survey modal closed after {step} steps")
                await wait_question(page, timeout_seconds=10)
                break
            print(f"🔁 Survey step {step + 1}/{max_steps}")
            state.record(f"step_{step + 1}")
            save_state(state)
            await inspect_modal(page)
            page = await question_router(page, 0)
            state.current_url = page.url
            state.tab_count = len(page.context.pages)
            print(f"🧭 State snapshot: {state.snapshot()}")
            save_state(state)
        return 0
    finally:
        print(f"🧭 Final state: {state.snapshot()}")
        save_state(state)
        await context.close()
        await playwright.stop()
