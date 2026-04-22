#!/usr/bin/env python3
"""
Playwright Worker MIT deinem Chrome-Profil!
Nutzt dein bereits eingeloggtes Chrome-Profil - KEIN Login nötig!
"""

import asyncio
import os
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from playwright.async_api import async_playwright
from playwright_stealth.stealth import Stealth


CHROME_PROFILE_PATH = Path.home() / "Library/Application Support/Google/Chrome/Profile 18"


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
        await page.goto("https://www.heypiggy.com")
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(2)

        print(f"📄 URL: {page.url}")
        print(f"📄 Title: {await page.title()}")

        # Screenshot
        await page.screenshot(path="/tmp/heypiggy_chrome.png")
        print("📸 Screenshot: /tmp/heypiggy_chrome.png")

        # Warte auf Umfragen
        await asyncio.sleep(3)

        # Finde alle Umfragen
        survey_cards = await page.query_selector_all('a[href*="survey"]')
        print(f"📊 Umfragen gefunden: {len(survey_cards)}")

        if survey_cards:
            # Klicke erste Umfrage
            print("🎯 Klicke erste Umfrage...")
            await survey_cards[0].click()
            await asyncio.sleep(3)

            print(f"📄 URL: {page.url}")
            await page.screenshot(path="/tmp/heypiggy_survey.png")
            print("📸 Screenshot: /tmp/heypiggy_survey.png")

            # Beantworte Fragen
            print("📝 Beantworte Fragen...")
            await asyncio.sleep(2)

            # Weiter-Button finden und klicken
            next_btn = await page.query_selector(
                'button:has-text("Weiter"), button:has-text("Next"), button:has-text("Fortsetzen")'
            )
            if next_btn:
                await next_btn.click()
                await asyncio.sleep(1)
                print("✅ Weiter-Button geklickt!")

        # Debug: Browser offen lassen
        print("⏸️ Debug - Browser bleibt offen...")
        await asyncio.sleep(300)

        await context.close()


if __name__ == "__main__":
    asyncio.run(main())
