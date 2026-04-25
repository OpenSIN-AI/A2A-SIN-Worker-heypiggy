from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from worker.resilience_engine import (
    press_keys_with_human_cadence,
    sanitize_js_for_cdp,
    type_text_with_human_cadence,
)


def test_sanitize_js_for_cdp_strips_hash_comments_without_touching_strings():
    script = '''
    # comment line
    const url = "https://example.com/#anchor"; # trailing comment
    const value = '#still-kept';
    '''

    sanitized = sanitize_js_for_cdp(script)

    assert "comment line" not in sanitized
    assert "trailing comment" not in sanitized
    assert "https://example.com/#anchor" in sanitized
    assert "#still-kept" in sanitized


@pytest.mark.asyncio
async def test_press_keys_with_human_cadence_focuses_and_presses(monkeypatch):
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_execute(method: str, params: dict[str, object]):
        calls.append((method, params))
        return {"ok": True, "method": method}

    monkeypatch.setattr("worker.resilience_engine.asyncio.sleep", AsyncMock())
    monkeypatch.setattr("worker.resilience_engine.random.random", lambda: 0.0)

    result = await press_keys_with_human_cadence(
        fake_execute,
        ["Tab", "Enter"],
        tab_params={"tabId": 7},
        selector="#field",
        min_delay_sec=0.0,
        max_delay_sec=0.0,
    )

    assert result == [{"ok": True, "method": "dom.press"}, {"ok": True, "method": "dom.press"}]
    assert [method for method, _ in calls] == ["dom.focus", "dom.press", "dom.press"]


@pytest.mark.asyncio
async def test_type_text_with_human_cadence_uses_keyboard_for_short_text(monkeypatch):
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_execute(method: str, params: dict[str, object]):
        calls.append((method, params))
        return {"ok": True, "method": method}

    monkeypatch.setattr("worker.resilience_engine.asyncio.sleep", AsyncMock())
    monkeypatch.setattr("worker.resilience_engine.random.random", lambda: 0.0)

    result = await type_text_with_human_cadence(
        fake_execute,
        "ab",
        tab_params={"tabId": 7},
        selector="#name",
        ref="",
        max_inline_chars=400,
    )

    assert result["mode"] == "keyboard"
    assert result["typed"] == 2
    assert [method for method, _ in calls][:2] == ["click", "keyboard"]
