#!/usr/bin/env python3
"""
Öffnet Chrome MIT deinem Profil - dann verbinden wir uns
"""

import asyncio
import subprocess
import sys
import time
import urllib.request
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

    await wait_for_cdp_ready("http://localhost:9222", timeout_seconds=30)

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


async def wait_for_cdp_ready(cdp_url: str, timeout_seconds: int = 30) -> None:
    """Wartet auf den CDP-Endpoint statt blind zu schlafen."""
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{cdp_url}/json/version", timeout=2) as response:
                if response.status == 200:
                    return
        except Exception as error:
            last_error = error
        await asyncio.sleep(0.5)

    raise TimeoutError(
        f"Chrome CDP at {cdp_url} not ready after {timeout_seconds}s: {last_error}"
    )


if __name__ == "__main__":
    asyncio.run(main())
