#!/usr/bin/env python3
"""
Verbinde mit Chrome über Debug-Port!
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from playwright.async_api import async_playwright


async def main():
    print("🔌 Verbinde mit Chrome über CDP...")

    async with async_playwright() as p:
        # Verbinde mit existierendem Chrome über CDP
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        print("✅ Mit Chrome verbunden!")

        # Alle Tabs
        contexts = browser.contexts
        print(f"📄 Contexts: {len(contexts)}")

        for ctx in contexts:
            pages = ctx.pages
            print(f"📄 Pages in Context: {len(pages)}")
            for page in pages:
                print(f"  - {page.url}")

        # HeyPiggy Tab finden
        for ctx in contexts:
            for page in ctx.pages:
                if "heypiggy" in page.url.lower():
                    print(f"🎯 HeyPiggy Tab gefunden: {page.url}")

                    # Screenshot
                    await page.screenshot(path="/tmp/heypiggy_cdp.png")
                    print("📸 Screenshot: /tmp/heypiggy_cdp.png")

                    # HTML holen
                    html = await page.content()
                    print(f"📄 HTML Length: {len(html)}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
