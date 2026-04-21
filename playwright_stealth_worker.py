#!/usr/bin/env python3
# ================================================================================
# DATEI: playwright_stealth_worker.py
# PROJEKT: A2A-SIN-Worker-heyPiggy
# ZWECK: Direkter Playwright+Stealth Worker - NICHT über Bridge!
# ================================================================================
"""
Nuclear Option - Playwright mit Stealth für HeyPiggy!

Dies ist ein eigenständiger Worker der:
1. Playwright mit Stealth nutzt
2. Erst CDP an ein laufendes Chrome versucht
3. Danach auf einen persistenten lokalen Profil-Clone fällt
4. Human-like clicks und keyboard navigation nutzt
5. Im Standard NICHT automatisch ins Login tippt

Usage:
    export HEYPIGGY_EMAIL="..."
    export HEYPIGGY_PASSWORD="..."
    export NVIDIA_API_KEY="..."
    python3 playwright_stealth_worker.py
"""

import asyncio
import os
import random
import shutil
import sys
import time
from pathlib import Path

# Füge Projekt-Pfad hinzu
sys.path.insert(0, str(Path(__file__).parent))

from playwright.async_api import async_playwright
from playwright_stealth.stealth import Stealth


CHROME_USER_DATA_DIR = Path.home() / "Library/Application Support/Google/Chrome"
PLAYWRIGHT_PROFILE_STORE = Path.home() / ".heypiggy" / "playwright_profile_clone"


def detect_chrome_profile_dir() -> str:
    """Pick a Chrome profile dir, preferring the configured default."""
    preferred = os.environ.get("HEYPIGGY_CHROME_PROFILE_DIR", "Default")
    candidates = [preferred, "Default", "Profile 18"]
    for candidate in candidates:
        if (CHROME_USER_DATA_DIR / candidate).exists():
            return candidate
    return preferred


def prepare_playwright_user_data_dir() -> Path:
    """Create a persistent Playwright-safe clone of the active Chrome profile."""
    profile_dir = detect_chrome_profile_dir()
    clone_root = PLAYWRIGHT_PROFILE_STORE
    clone_root.mkdir(parents=True, exist_ok=True)

    dst_profile = clone_root / profile_dir
    if dst_profile.exists() and any(dst_profile.iterdir()):
        print(f"♻️ Wiederverwende persistentes Playwright-Profil: {clone_root}")
        print(f"🧭 Nutze Chrome-Profil: {profile_dir}")
        return clone_root

    for name in ("Local State", "First Run", "Last Version"):
        src = CHROME_USER_DATA_DIR / name
        if src.exists():
            shutil.copy2(src, clone_root / name)

    src_profile = CHROME_USER_DATA_DIR / profile_dir
    shutil.copytree(
        src_profile,
        dst_profile,
        symlinks=True,
        ignore_dangling_symlinks=True,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(
            "SingletonLock",
            "SingletonCookie",
            "SingletonSocket",
            "RunningChromeVersion",
            "Crashpad",
            "GPUCache",
            "GrShaderCache",
            "ShaderCache",
            "Code Cache",
            "DawnCache",
            "Visited Links",
            "chrome_debug.log",
        ),
    )
    print(f"🧷 Playwright user-data clone: {clone_root}")
    print(f"🧭 Nutze Chrome-Profil: {profile_dir}")
    return clone_root


async def human_click(page, selector: str) -> bool:
    """Human-like click mit Mouse Down/Up."""
    try:
        element = await page.query_selector(selector)
        if element:
            box = await element.bounding_box()
            if box:
                # Bewege Maus wie Mensch (nicht instant!)
                await page.mouse.move(
                    box["x"] + box["width"] / 2 + random.randint(-10, 10),
                    box["y"] + box["height"] / 2 + random.randint(-10, 10),
                )
                await asyncio.sleep(random.uniform(0.1, 0.3))
                # Mouse down + up wie echter Mensch
                await page.mouse.down()
                await asyncio.sleep(random.uniform(0.05, 0.15))
                await page.mouse.up()
                return True
    except Exception as e:
        print(f"Click error: {e}")
    return False


async def keyboard_navigate_and_click(page):
    """Keyboard Navigation als Fallback."""
    await page.keyboard.press("Tab")
    await asyncio.sleep(random.uniform(0.2, 0.5))
    await page.keyboard.press("Enter")
    await asyncio.sleep(1)


async def fill_input(page, selector: str, text: str):
    """Füllt Input mit menschlicher Geschwindigkeit."""
    await page.click(selector)
    await asyncio.sleep(random.uniform(0.2, 0.5))
    await page.keyboard.type(text, delay=random.randint(50, 150))


async def wait_for_manual_login(page, timeout_seconds: int = 300) -> bool:
    """Wartet auf manuelles Login, bis die URL nicht mehr Login ist."""
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        current_url = (page.url or "").lower()
        if "login" not in current_url and "signin" not in current_url:
            return True
        await asyncio.sleep(1.5)
    return False


async def main():
    """Haupt-Loop für HeyPiggy mit Playwright+Stealth."""

    print("🚀 Starte Playwright+Stealth Worker...")

    async with async_playwright() as p:
        browser = None
        context = None
        page = None
        connected_via_cdp = False

        try:
            print("🔌 Versuche an laufendes Chrome per CDP anzudocken...")
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            connected_via_cdp = True
            print("✅ CDP-Verbindung zu laufendem Chrome aktiv")

            context = browser.contexts[0] if browser.contexts else None
            if context is None:
                raise RuntimeError("CDP verbunden, aber kein Browser-Context gefunden")
            page = context.pages[0] if context.pages else await context.new_page()
        except Exception as cdp_error:
            print(f"⚠️ CDP fehlgeschlagen: {cdp_error}")
            print("🧩 Fallback: Playwright mit geklontem Profil")

            user_data_dir = prepare_playwright_user_data_dir()
            profile_dir = detect_chrome_profile_dir()
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                channel="chrome",
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    f"--profile-directory={profile_dir}",
                ],
            )
            page = context.pages[0] if context.pages else await context.new_page()

        await page.set_viewport_size({"width": 1920, "height": 1080})

        # Aktiviere Stealth
        stealth = Stealth()
        await stealth.apply_stealth_async(page)
        print("✅ Stealth aktiviert")

        # Gehe zu HeyPiggy Login
        print("🌐 Navigiere zu HeyPiggy...")
        await page.goto("https://www.heypiggy.com/login")
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(2)

        # Check ob Login Seite
        print(f"📄 Aktuelle URL: {page.url}")

        email = os.environ.get("HEYPIGGY_EMAIL", "")
        password = os.environ.get("HEYPIGGY_PASSWORD", "")
        automated_login = (
            os.environ.get("HEYPIGGY_AUTOMATED_LOGIN", "0") == "1"
            and bool(email)
            and bool(password)
        )
        if not automated_login:
            print("🖐️ Manueller Login-Modus aktiv — ich tippe nichts ins Login-Formular.")

        if automated_login:
            # Finde Email Input
            email_selectors = [
                'input[type="email"]',
                'input[name="email"]',
                'input[id="email"]',
                'input[placeholder*="email"]',
                'input[placeholder*="E-Mail"]',
            ]

            email_filled = False
            for sel in email_selectors:
                try:
                    if await page.query_selector(sel):
                        await fill_input(page, sel, email)
                        email_filled = True
                        print(f"✅ Email eingegeben: {email[:5]}...")
                        break
                except:
                    continue

            if not email_filled:
                print("❌ Email Input nicht gefunden!")
                # Screenshot für Debug
                await page.screenshot(path="/tmp/heypiggy_debug.png")
                print(f"📸 Screenshot: /tmp/heypiggy_debug.png")

            # Password
            password_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                'input[id="password"]',
            ]

            for sel in password_selectors:
                try:
                    if await page.query_selector(sel):
                        await fill_input(page, sel, password)
                        print("✅ Password eingegeben")
                        break
                except:
                    continue

            # Login Button
            button_selectors = [
                'button[type="submit"]',
                'button:has-text("Anmelden")',
                'button:has-text("Login")',
                'button:has-text("Sign in")',
                'input[type="submit"]',
            ]

            login_success = False
            for sel in button_selectors:
                try:
                    # Erst keyboard navigation versuchen
                    await page.keyboard.press("Tab")
                    await asyncio.sleep(0.3)
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(1)

                    # Check ob wir eingeloggt sind
                    if "dashboard" in page.url.lower() or "login" not in page.url.lower():
                        login_success = True
                        print("✅ Login erfolgreich!")
                        break

                    # Sonst Button klicken
                    if await human_click(page, sel):
                        await asyncio.sleep(2)
                        if "dashboard" in page.url.lower():
                            login_success = True
                            print("✅ Login Button geklickt - erfolgreich!")
                            break
                except Exception as e:
                    print(f"Button click error: {e}")
                    continue
        else:
            print("🛑 Auto-Login deaktiviert — bitte jetzt manuell im geöffneten Browser anmelden.")
            login_success = await wait_for_manual_login(page, timeout_seconds=300)
            if login_success:
                print("✅ Manuelles Login erkannt!")
            else:
                print("⏳ Login nicht erkannt — fahre trotzdem fort und prüfe Dashboard.")

        # Dashboard
        print(f"📄 URL nach Login: {page.url}")

        # Warte auf Dashboard Inhalt
        await asyncio.sleep(3)

        # Suche nach verfügbaren Umfragen
        survey_selectors = [
            'a[href*="survey"]',
            'a[href*="umfrage"]',
            ".survey-card",
            "[data-survey]",
            'button:has-text("Umfrage starten")',
        ]

        surveys_found = False
        for sel in survey_selectors:
            try:
                elements = await page.query_selector_all(sel)
                if elements:
                    print(f"✅ {len(elements)} Umfragen gefunden mit: {sel}")
                    surveys_found = True

                    # Klicke auf erste Umfrage
                    await elements[0].click()
                    await asyncio.sleep(3)
                    print(f"📄 URL nach Umfrage-Klick: {page.url}")
                    break
            except Exception:
                continue

        if not surveys_found:
            print("⚠️ Keine Umfragen auf Dashboard gefunden")
            await page.screenshot(path="/tmp/heypiggy_dashboard.png")

        # Halte Browser offen für Debug
        print("⏸️ Browser bleibt offen für Debug...")
        print("Drücke Ctrl+C zum Beenden")

        # Warte ewig (für Debug)
        await asyncio.sleep(300)

        if context is not None:
            await context.close()
        if browser is not None and not connected_via_cdp:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
