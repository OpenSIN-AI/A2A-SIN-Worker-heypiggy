#!/usr/bin/env python3

"""macOS desktop control helpers for the hybrid agent."""

from __future__ import annotations

import asyncio
import io
import sys
from typing import Any

from PIL import Image


_KEY_CODES: dict[str, int] = {
    "enter": 36,
    "return": 36,
    "tab": 48,
    "space": 49,
    "backspace": 51,
    "delete": 51,
    "escape": 53,
    "esc": 53,
    "left": 123,
    "right": 124,
    "down": 125,
    "up": 126,
    "home": 115,
    "end": 119,
    "pageup": 116,
    "pagedown": 121,
}


class MacDesktopController:
    def __init__(self, *, screencapture_bin: str = "screencapture", osascript_bin: str = "osascript") -> None:
        self._screencapture_bin = screencapture_bin
        self._osascript_bin = osascript_bin

    @staticmethod
    def _is_macos() -> bool:
        return sys.platform == "darwin"

    async def capture_screen_png(self) -> tuple[bytes, int, int]:
        if not self._is_macos():
            return b"", 0, 0

        proc = await asyncio.create_subprocess_exec(
            self._screencapture_bin,
            "-x",
            "-t",
            "png",
            "/dev/stdout",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10.0)
        if not stdout:
            return b"", 0, 0

        width = height = 0
        try:
            with Image.open(io.BytesIO(stdout)) as image:
                width, height = image.size
        except Exception:
            pass
        return stdout, width, height

    async def click_coordinates(self, x: float, y: float) -> dict[str, Any]:
        if not self._is_macos():
            return {"success": False, "error": "desktop click only works on macOS"}

        script = """
        on run argv
            set xPos to (item 1 of argv) as integer
            set yPos to (item 2 of argv) as integer
            tell application "System Events"
                click at {xPos, yPos}
            end tell
        end run
        """
        return await self._run_osascript(script, [str(int(round(x))), str(int(round(y)))])

    async def click_button(self, title: str) -> dict[str, Any]:
        if not self._is_macos():
            return {"success": False, "error": "desktop click only works on macOS"}

        script = """
        on run argv
            set buttonTitle to item 1 of argv
            tell application "System Events"
                tell (first application process whose frontmost is true)
                    if exists (button buttonTitle of front window) then
                        click button buttonTitle of front window
                        return "clicked-front"
                    end if
                    repeat with w in windows
                        if exists (button buttonTitle of w) then
                            click button buttonTitle of w
                            return "clicked-window"
                        end if
                    end repeat
                end tell
            end tell
        end run
        """
        return await self._run_osascript(script, [title])

    async def press_key(self, key: str) -> dict[str, Any]:
        if not self._is_macos():
            return {"success": False, "error": "desktop keypress only works on macOS"}

        normalized = str(key or "").strip().lower()
        if len(normalized) == 1 and normalized.isprintable():
            script = """
            on run argv
                set keyText to item 1 of argv
                tell application "System Events"
                    keystroke keyText
                end tell
            end run
            """
            return await self._run_osascript(script, [key])

        if normalized not in _KEY_CODES:
            return {"success": False, "error": f"unsupported key: {key}"}

        script = """
        on run argv
            set keyCodeValue to (item 1 of argv) as integer
            tell application "System Events"
                key code keyCodeValue
            end tell
        end run
        """
        return await self._run_osascript(script, [str(_KEY_CODES[normalized])])

    async def type_text(self, text: str) -> dict[str, Any]:
        if not self._is_macos():
            return {"success": False, "error": "desktop typing only works on macOS"}

        script = """
        on run argv
            set inputText to item 1 of argv
            tell application "System Events"
                keystroke inputText
            end tell
        end run
        """
        return await self._run_osascript(script, [text])

    async def activate_app(self, app_name: str) -> dict[str, Any]:
        if not self._is_macos():
            return {"success": False, "error": "desktop app activation only works on macOS"}

        script = """
        on run argv
            set appName to item 1 of argv
            tell application appName to activate
            return "activated"
        end run
        """
        return await self._run_osascript(script, [app_name])

    async def _run_osascript(self, script: str, argv: list[str]) -> dict[str, Any]:
        try:
            proc = await asyncio.create_subprocess_exec(
                self._osascript_bin,
                "-e",
                script,
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)
            if proc.returncode == 0:
                return {
                    "success": True,
                    "stdout": stdout.decode("utf-8", errors="replace").strip(),
                    "stderr": stderr.decode("utf-8", errors="replace").strip(),
                }
            return {
                "success": False,
                "error": stderr.decode("utf-8", errors="replace").strip() or stdout.decode("utf-8", errors="replace").strip() or f"osascript exited {proc.returncode}",
                "stdout": stdout.decode("utf-8", errors="replace").strip(),
                "stderr": stderr.decode("utf-8", errors="replace").strip(),
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}


__all__ = ["MacDesktopController"]
