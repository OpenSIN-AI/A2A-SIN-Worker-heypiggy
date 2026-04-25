from __future__ import annotations

import asyncio
import random
from typing import Any, Callable, Awaitable


def sanitize_js_for_cdp(js_code: str) -> str:
    """Entfernt Python-Style `#`-Kommentare aus JS-Payloads.

    WHY: CDP/Runtime.evaluate kann `#`-Kommentare nicht zuverlässig verarbeiten.
    CONSEQUENCES: Wir lassen Strings unangetastet, strippen aber offensichtliche
    Kommentarzeilen und Inline-Kommentare ausserhalb von Literalen.
    """
    lines: list[str] = []
    for raw_line in str(js_code or "").splitlines():
        line = _strip_hash_comment(raw_line)
        if line.strip():
            lines.append(line.rstrip())
    return "\n".join(lines)


async def press_keys_with_human_cadence(
    execute_bridge: Callable[[str, dict[str, Any]], Awaitable[Any]],
    keys: list[str],
    *,
    tab_params: dict[str, Any] | None = None,
    selector: str = "",
    min_delay_sec: float = 0.15,
    max_delay_sec: float = 0.4,
) -> list[Any]:
    """Sendet Tastendrücke mit kurzer menschlicher Pause und optionalem Fokus."""
    params = dict(tab_params or {})
    if selector:
        try:
            await execute_bridge("dom.focus", {"selector": selector, **params})
        except Exception:
            pass

    results: list[Any] = []
    for key_name in keys:
        key = str(key_name or "")
        try:
            try:
                result = await execute_bridge("dom.press", {"key": key, **params})
            except Exception:
                result = await execute_bridge("dom.press", {"keys": [key], **params})
            results.append(result)
        finally:
            await asyncio.sleep(min_delay_sec + random.random() * max(0.0, max_delay_sec - min_delay_sec))

    return results


async def type_text_with_human_cadence(
    execute_bridge: Callable[[str, dict[str, Any]], Awaitable[Any]],
    text: str,
    *,
    tab_params: dict[str, Any] | None = None,
    selector: str = "",
    ref: str = "",
    max_inline_chars: int = 400,
) -> dict[str, Any]:
    """Tippt Text zeichenweise mit Jitter oder nutzt den Bridge-Fallback."""
    params = dict(tab_params or {})
    selector = str(selector or "")
    ref = str(ref or "")
    payload = {**params, "selector": selector, "ref": ref, "text": text}

    if ref:
        await execute_bridge("click_ref", {"ref": ref, **params})
        await asyncio.sleep(0.4 + random.random() * 0.3)
    elif selector:
        try:
            await execute_bridge("click", {"selector": selector, **params})
            await asyncio.sleep(0.3 + random.random() * 0.3)
        except Exception:
            pass

    if not text:
        return {"typed": 0, "mode": "empty"}

    if len(text) > max_inline_chars:
        return await execute_bridge("type_text", payload)

    typed = 0
    for ch in text:
        try:
            await execute_bridge("keyboard", {"keys": [ch], **params})
            typed += 1
        except Exception:
            return await execute_bridge("type_text", payload)

        base = 0.04 + random.random() * 0.14
        if ch in ".,!?;:":
            base += 0.12 + random.random() * 0.18
        if ch == " " and random.random() < 0.05:
            base += 0.25 + random.random() * 0.35
        if random.random() < 0.03:
            base += 0.45 + random.random() * 0.6
        await asyncio.sleep(base)

    return {"typed": typed, "mode": "keyboard"}


def _strip_hash_comment(line: str) -> str:
    in_single = False
    in_double = False
    escaped = False
    for idx, ch in enumerate(line):
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            continue
        if ch == "#" and not in_single and not in_double:
            if idx == 0 or line[:idx].rstrip() == "":
                return ""
            return line[:idx].rstrip()
    return line
