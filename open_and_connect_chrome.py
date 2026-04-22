#!/usr/bin/env python3
"""
Öffnet Chrome MIT deinem Profil - dann verbinden wir uns
"""

import asyncio
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from playwright.async_api import async_playwright
from playwright_stealth.stealth import Stealth


async def main():
    # Öffne Chrome mit deinem Profil im Hintergrund
    profile_path = Path.home() / "Library/Application Support/Google/Chrome/Profile 18"

    print("🚀 Öffne Chrome mit deinem Profil...")

    # Starte Chrome mit Debug-Port
    proc = subprocess.Popen(
        [
            "open",
            "-a",
            "Google Chrome",
            "--args",
            f"--user-data-dir={profile_path}",
            "--remote-debugging-port=9222",
        ]
    )

    await asyncio.sleep(8)

    async with async_playwright() as p:
        try:
            # Verbinde mit Chrome
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            print("✅ Mit Chrome verbunden!")

            # Stealth auf alle Pages
            for ctx in browser.contexts:
                for page in ctx.pages:
                    stealth = Stealth()
                    await stealth.apply_stealth_async(page)

            print("✅ Stealth aktiviert!")

            # Gehe zu HeyPiggy
            for ctx in browser.contexts:
                for page in ctx.pages:
                    await page.goto("https://www.heypiggy.com")
                    await page.wait_for_load_state("domcontentloaded")
                    print(f"📄 URL: {page.url}")

                    await page.screenshot(path="/tmp/heypiggy.png")
                    print("📸 Screenshot: /tmp/heypiggy.png")

            await browser.close()

        except Exception as e:
            print(f"❌ Fehler: {e}")

    proc.terminate()


if __name__ == "__main__":
    asyncio.run(main())
