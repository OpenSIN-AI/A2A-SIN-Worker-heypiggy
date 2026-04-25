#!/usr/bin/env python3
"""
Playwright Worker MIT deinem Chrome-Profil!
Nutzt dein bereits eingeloggtes Chrome-Profil - KEIN Login nötig!
"""

import asyncio
import os
import random
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from playwright.async_api import async_playwright
from playwright_stealth.stealth import Stealth


CHROME_PROFILE_PATH = Path.home() / "Library/Application Support/Google/Chrome/Profile 18"


def get_debug_hold_seconds(default: int = 300) -> int:
    """Liest die Debug-Haltezeit aus der ENV statt hart zu verdrahten."""
    raw = os.environ.get("HEYPIGGY_DEBUG_HOLD_SECONDS", "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


async def _wait_for_page_settle(page, previous_url: str, timeout_seconds: int = 10) -> bool:
    """Wartet auf URL-/DOM-Veränderung statt fixer Sleeps."""
    deadline = time.monotonic() + timeout_seconds
    selectors = (
        'a[href*="survey"]',
        '#start-survey-button',
        'button:has-text("Weiter")',
        'button:has-text("Next")',
        'button:has-text("Fortsetzen")',
        'iframe',
        '[role="dialog"]',
        '.modal',
        '.overlay',
    )

    while time.monotonic() < deadline:
        if page.url != previous_url:
            return True

        for selector in selectors:
            try:
                locator = page.locator(selector)
                if await locator.count() > 0 and await locator.first.is_visible():
                    return True
            except Exception:
                continue

        try:
            await page.wait_for_load_state("domcontentloaded", timeout=250)
        except Exception:
            pass
        await asyncio.sleep(0.25)

    return False


async def main():
    print("🚀 Starte MIT deinem Chrome-Profil...")

    async with async_playwright() as p:
        # Nutze DEIN Chrome-Profil mit Stealth
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(CHROME_PROFILE_PATH),
            headless=False,  # Sichtbar!
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
            ],
        )

        page = await context.new_page()

        # Stealth aktivieren
        stealth = Stealth()
        await stealth.apply_stealth_async(page)
        print("✅ Mit Stealth aktiviert")

        # Gehe direkt zu HeyPiggy Dashboard
        print("🌐 Gehe zu HeyPiggy Dashboard...")
        before_url = page.url
        await page.goto("https://www.heypiggy.com")
        await page.wait_for_load_state("domcontentloaded")
        await _wait_for_page_settle(page, before_url, timeout_seconds=5)

        print(f"📄 URL: {page.url}")
        print(f"📄 Title: {await page.title()}")

        # Screenshot
        await page.screenshot(path="/tmp/heypiggy_chrome.png")
        print("📸 Screenshot: /tmp/heypiggy_chrome.png")

        # Warte auf Umfragen
        await _wait_for_page_settle(page, page.url, timeout_seconds=5)

        # Finde alle Umfragen
        survey_cards = await page.query_selector_all('a[href*="survey"]')
        print(f"📊 Umfragen gefunden: {len(survey_cards)}")

        if survey_cards:
            # Klicke erste Umfrage
            print("🎯 Klicke erste Umfrage...")
            before_click_url = page.url
            await survey_cards[0].click()
            await _wait_for_page_settle(page, before_click_url, timeout_seconds=10)

            print(f"📄 URL: {page.url}")
            await page.screenshot(path="/tmp/heypiggy_survey.png")
            print("📸 Screenshot: /tmp/heypiggy_survey.png")

            # Beantworte Fragen
            print("📝 Beantworte Fragen...")
            await _wait_for_page_settle(page, page.url, timeout_seconds=5)

            # Weiter-Button finden und klicken
            next_btn = await page.query_selector(
                'button:has-text("Weiter"), button:has-text("Next"), button:has-text("Fortsetzen")'
            )
            if next_btn:
                before_next_url = page.url
                await next_btn.click()
                await _wait_for_page_settle(page, before_next_url, timeout_seconds=5)
                print("✅ Weiter-Button geklickt!")

        # Debug: Browser offen lassen
        print("⏸️ Debug - Browser bleibt offen...")
        await asyncio.sleep(get_debug_hold_seconds())

        await context.close()


if __name__ == "__main__":
    asyncio.run(main())
