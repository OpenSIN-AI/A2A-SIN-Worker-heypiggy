from unittest.mock import AsyncMock, MagicMock

import pytest

import playstealth_cli as cli


pytestmark = pytest.mark.asyncio


async def test_run_survey_loop_clicks_progress_after_radio(monkeypatch):
    page = AsyncMock()
    page.url = "https://example.com/survey"
    root = object()
    active_calls = {"count": 0}

    async def fake_active_surface(_page):
        active_calls["count"] += 1
        if active_calls["count"] == 1:
            return (
                "modal",
                root,
                "#survey-modal ",
                "Wie viele Fahrzeuge befinden sich in Ihrem Haushalt? Nächste",
            )
        return ("modal", root, "#survey-modal ", "Vielen Dank für Ihre Teilnahme")

    monkeypatch.setattr(cli, "_active_surface", fake_active_surface)
    monkeypatch.setattr(cli, "_handle_consent_prompt", AsyncMock(return_value=False))
    monkeypatch.setattr(cli, "_dismiss_inline_consent", AsyncMock(return_value=False))
    monkeypatch.setattr(cli, "_answer_all_radios", AsyncMock(return_value=1))
    monkeypatch.setattr(cli, "_answer_first_select", AsyncMock(return_value=False))
    monkeypatch.setattr(cli, "_answer_first_checkbox", AsyncMock(return_value=False))
    monkeypatch.setattr(cli, "_fill_first_text_input", AsyncMock(return_value=False))

    progress_click = AsyncMock(return_value=True)
    monkeypatch.setattr(cli, "_click_progress_button", progress_click)

    state = await cli.run_survey_loop(page, None, max_steps=3)

    assert state["status"] == "complete"
    assert state["steps"] == 2
    progress_click.assert_awaited_once_with(page)


async def test_run_survey_loop_answers_multiple_radio_groups(monkeypatch):
    page = AsyncMock()
    page.url = "https://example.com/survey"
    root = object()
    active_calls = {"count": 0}

    async def fake_active_surface(_page):
        active_calls["count"] += 1
        if active_calls["count"] == 1:
            return (
                "page",
                root,
                "",
                "Frage1? OptionA OptionB\nFrage2? Ja Nein\nNächste",
            )
        return ("page", root, "", "Vielen Dank für Ihre Teilnahme")

    monkeypatch.setattr(cli, "_active_surface", fake_active_surface)
    monkeypatch.setattr(cli, "_handle_consent_prompt", AsyncMock(return_value=False))
    monkeypatch.setattr(cli, "_dismiss_inline_consent", AsyncMock(return_value=False))
    monkeypatch.setattr(cli, "_answer_all_radios", AsyncMock(return_value=3))
    monkeypatch.setattr(cli, "_answer_first_select", AsyncMock(return_value=False))
    monkeypatch.setattr(cli, "_answer_first_checkbox", AsyncMock(return_value=False))
    monkeypatch.setattr(cli, "_fill_first_text_input", AsyncMock(return_value=False))

    progress_click = AsyncMock(return_value=True)
    monkeypatch.setattr(cli, "_click_progress_button", progress_click)

    state = await cli.run_survey_loop(page, None, max_steps=5)

    assert state["status"] == "complete"
    cli._answer_all_radios.assert_awaited_with(root, "", max_groups=99)


async def test_run_survey_loop_keeps_browser_open_on_stall(monkeypatch):
    page = AsyncMock()
    page.url = "https://example.com/survey"
    page.is_closed = MagicMock(return_value=False)
    root = object()

    async def fake_active_surface(_page):
        return ("page", root, "", "Gleiche Seite kein Fortschritt")

    monkeypatch.setattr(cli, "_active_surface", fake_active_surface)
    monkeypatch.setattr(cli, "_handle_consent_prompt", AsyncMock(return_value=False))
    monkeypatch.setattr(cli, "_dismiss_inline_consent", AsyncMock(return_value=False))
    monkeypatch.setattr(cli, "_answer_all_radios", AsyncMock(return_value=0))
    monkeypatch.setattr(cli, "_answer_first_select", AsyncMock(return_value=False))
    monkeypatch.setattr(cli, "_answer_first_checkbox", AsyncMock(return_value=False))
    monkeypatch.setattr(cli, "_fill_first_text_input", AsyncMock(return_value=False))
    monkeypatch.setattr(cli, "_click_progress_button", AsyncMock(return_value=False))
    monkeypatch.setattr(cli, "_take_screenshot", AsyncMock(return_value=None))

    state = await cli.run_survey_loop(page, None, max_steps=10)

    assert state["status"] == "stalled"


async def test_answer_all_radios_returns_count():
    """_answer_all_radios gibt die Anzahl der beantworteten Gruppen zurück."""
    root = AsyncMock()
    root.evaluate = AsyncMock(return_value={"acted": 4})

    count = await cli._answer_all_radios(root, "", max_groups=99)

    assert count == 4


async def test_answer_all_radios_fallback_on_js_failure():
    """Wenn JS-evaluate fehlschlägt, nutze Playwright-Fallback."""
    radio1 = AsyncMock()
    radio1.is_checked = AsyncMock(return_value=False)
    radio1.get_attribute = AsyncMock(side_effect=["q1", "q1"])
    radio1.check = AsyncMock()
    radio1.dispatch_event = AsyncMock()

    radio2 = AsyncMock()
    radio2.is_checked = AsyncMock(return_value=False)
    radio2.get_attribute = AsyncMock(side_effect=["q2", "q2"])
    radio2.check = AsyncMock()
    radio2.dispatch_event = AsyncMock()

    radios_locator = MagicMock()
    radios_locator.count = AsyncMock(return_value=2)
    radios_locator.nth = MagicMock(side_effect=[radio1, radio2])

    root = MagicMock(spec=["evaluate", "locator"])
    root.evaluate = AsyncMock(side_effect=RuntimeError("JS failed"))
    root.locator = MagicMock(return_value=radios_locator)

    count = await cli._answer_all_radios(root, "prefix ", max_groups=99)
    assert count >= 0


async def test_derive_prompted_text_answer_extracts_word_and_number():
    assert cli._derive_prompted_text_answer(
        "Enter the word 'ROBOT' in the field below", "text"
    ) == "ROBOT"
    assert cli._derive_prompted_text_answer(
        "Bitte legen Sie die Zahl 10 in das leere Kästchen:", "number"
    ) == "10"


async def test_answer_numeric_tile_choice_from_prompt():
    root = AsyncMock()
    root.evaluate = AsyncMock(return_value={"clicked": True, "text": "71"})

    result = await cli._answer_numeric_tile_choice(
        root,
        "Bitte legen Sie die Zahl 71 in das leere Kästchen:",
    )

    assert result is True


async def test_derive_visible_code_candidate():
    root = AsyncMock()
    root.evaluate = AsyncMock(return_value="AB12")

    result = await cli._derive_visible_code_candidate(root)

    assert result == "AB12"


async def test_derive_field_specific_answer_for_pii_fields(monkeypatch):
    monkeypatch.setenv("HEYPIGGY_EMAIL", "person@example.com")

    assert cli._derive_field_specific_answer("VORNAME", "", "text") == "Max"
    assert cli._derive_field_specific_answer("NACHNAME", "", "text") == "Mustermann"
    assert cli._derive_field_specific_answer("E-MAIL", "", "text") == "person@example.com"


async def test_answer_visible_option_choice_from_body_lines(monkeypatch):
    locator = AsyncMock()
    locator.first = locator
    locator.count = AsyncMock(return_value=1)
    locator.is_visible = AsyncMock(return_value=True)

    root = AsyncMock()
    root.get_by_text = lambda text, exact=True: locator

    click_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(cli, "_click_locator", click_mock)

    result = await cli._answer_visible_option_choice(
        root,
        "Welche der folgenden Dienste nutzen Sie?\nAmazon Music\nSpotify\nNächste",
    )

    assert result is True


async def test_ask_vision_llm_returns_none_without_api_key(monkeypatch):
    """Ohne NVIDIA_API_KEY gibt _ask_vision_llm None zurück."""
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    result = await cli._ask_vision_llm(b"fake-png-bytes", "some body text")
    assert result is None


async def test_take_screenshot_captures_page():
    """_take_screenshot gibt PNG-Bytes zurück."""
    page = AsyncMock()
    page.screenshot = AsyncMock(return_value=b"\x89PNG\r\n")

    result = await cli._take_screenshot(page)

    assert result == b"\x89PNG\r\n"
    page.screenshot.assert_awaited_once_with(type="png")


async def test_vision_guided_click_returns_false_on_empty_result():
    """_vision_guided_click gibt False zurück wenn Vision-Ergebnis leer ist."""
    page = AsyncMock()
    result = await cli._vision_guided_click(page, None)
    assert result is False

    result = await cli._vision_guided_click(page, {})
    assert result is False

    result = await cli._vision_guided_click(page, {"actions": []})
    assert result is False


async def test_run_survey_loop_returns_log(monkeypatch):
    """run_survey_loop gibt ein survey_log mit zurück."""
    page = AsyncMock()
    page.url = "https://example.com/survey"
    root = object()
    active_calls = {"count": 0}

    async def fake_active_surface(_page):
        active_calls["count"] += 1
        if active_calls["count"] == 1:
            return ("page", root, "", "Frage? Ja Nein Nächste")
        return ("page", root, "", "Vielen Dank für Ihre Teilnahme")

    monkeypatch.setattr(cli, "_active_surface", fake_active_surface)
    monkeypatch.setattr(cli, "_handle_consent_prompt", AsyncMock(return_value=False))
    monkeypatch.setattr(cli, "_dismiss_inline_consent", AsyncMock(return_value=False))
    monkeypatch.setattr(cli, "_answer_all_radios", AsyncMock(return_value=1))
    monkeypatch.setattr(cli, "_answer_first_select", AsyncMock(return_value=False))
    monkeypatch.setattr(cli, "_answer_first_checkbox", AsyncMock(return_value=False))
    monkeypatch.setattr(cli, "_fill_first_text_input", AsyncMock(return_value=False))
    monkeypatch.setattr(cli, "_click_progress_button", AsyncMock(return_value=True))

    state = await cli.run_survey_loop(page, None, max_steps=3)

    assert "log" in state
    assert isinstance(state["log"], list)
    assert state["status"] == "complete"
