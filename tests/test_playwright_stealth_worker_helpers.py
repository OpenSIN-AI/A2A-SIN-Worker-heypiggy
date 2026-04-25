from __future__ import annotations

import asyncio
import importlib
import sys
import types
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest


def _install_playwright_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    playwright_pkg = types.ModuleType("playwright")
    playwright_pkg.__path__ = []

    async_api = types.ModuleType("playwright.async_api")

    async def async_playwright():
        raise AssertionError("async_playwright should not be called in helper tests")

    async_api.async_playwright = async_playwright
    playwright_pkg_any: Any = playwright_pkg
    playwright_pkg_any.async_api = async_api

    stealth_pkg = types.ModuleType("playwright_stealth")
    stealth_pkg.__path__ = []
    stealth_submodule = types.ModuleType("playwright_stealth.stealth")

    class Stealth:
        async def apply_stealth_async(self, page):
            return None

    stealth_submodule_any: Any = stealth_submodule
    stealth_submodule_any.Stealth = Stealth
    stealth_pkg_any: Any = stealth_pkg
    stealth_pkg_any.stealth = stealth_submodule

    monkeypatch.setitem(sys.modules, "playwright", playwright_pkg)
    monkeypatch.setitem(sys.modules, "playwright.async_api", async_api)
    monkeypatch.setitem(sys.modules, "playwright_stealth", stealth_pkg)
    monkeypatch.setitem(sys.modules, "playwright_stealth.stealth", stealth_submodule)
    monkeypatch.delitem(sys.modules, "playwright_stealth_worker", raising=False)


@pytest.fixture()
def worker_module(monkeypatch: pytest.MonkeyPatch):
    _install_playwright_stubs(monkeypatch)
    return importlib.import_module("playwright_stealth_worker")


def test_is_consent_prompt_text_matches_known_prompts(worker_module):
    assert worker_module._is_consent_prompt_text("Already another survey open")
    assert worker_module._is_consent_prompt_text("Bitte Datenschutzerklärung lesen")
    assert worker_module._is_consent_prompt_text("Zustimmen und fortfahren")
    assert worker_module._is_consent_prompt_text(
        "Please continue", url="https://example.com/consent/step-1"
    )
    assert not worker_module._is_consent_prompt_text("Normal survey question")


def test_select_active_page_prefers_consent_tab(worker_module, monkeypatch):
    class FakePage:
        def __init__(self, name: str, url: str, body_text: str, closed: bool = False):
            self.name = name
            self.url = url
            self.body_text = body_text
            self._closed = closed

        def is_closed(self) -> bool:
            return self._closed

    dashboard = FakePage(
        "dashboard",
        "https://www.heypiggy.com/login?page=dashboard",
        "Survey list",
    )
    survey = FakePage("survey", "https://example.com/survey", "Question page")
    consent = FakePage(
        "consent",
        "https://rx.samplicio.us/consent/start",
        "Already another survey open",
    )

    async def fake_visible_input_count(page):
        return {"dashboard": 0, "survey": 1, "consent": 0}[page.name]

    async def fake_page_body_text(page, timeout: int = 3000):
        return page.body_text

    monkeypatch.setattr(worker_module, "_visible_input_count", fake_visible_input_count)
    monkeypatch.setattr(worker_module, "_page_body_text", fake_page_body_text)

    context = types.SimpleNamespace(pages=[dashboard, survey, consent])
    selected = asyncio.run(worker_module._select_active_page(context, dashboard))

    assert selected is consent


def test_handle_consent_prompt_clicks_expected_controls(worker_module, monkeypatch):
    page = types.SimpleNamespace(
        url="https://rx.samplicio.us/consent/start",
        body_text="Already another survey open",
    )
    calls: list[tuple[str, str | None]] = []

    async def fake_page_body_text(page_obj, timeout: int = 3000):
        return page_obj.body_text

    def fake_is_consent_prompt_text(body_text: str, url: str = "") -> bool:
        return True

    async def fake_click_text_or_role(page_obj, label: str, role: str | None = None) -> bool:
        calls.append((label, role))
        return label == "Continue"

    async def fake_click_visible_checkbox(page_obj) -> bool:
        calls.append(("checkbox", None))
        return False

    monkeypatch.setattr(worker_module, "_page_body_text", fake_page_body_text)
    monkeypatch.setattr(worker_module, "_is_consent_prompt_text", fake_is_consent_prompt_text)
    monkeypatch.setattr(worker_module, "_click_text_or_role", fake_click_text_or_role)
    monkeypatch.setattr(worker_module, "_click_visible_checkbox", fake_click_visible_checkbox)

    result = asyncio.run(worker_module._handle_consent_prompt(page))

    assert result is True
    assert calls == [
        ("I want to complete this survey", "radio"),
        ("I want to continue with the other survey", "radio"),
        ("Continue", "button"),
    ]


def test_handle_consent_prompt_handles_german_checkbox_flow(worker_module, monkeypatch):
    page = types.SimpleNamespace(
        url="https://enter.ipsosinteractive.com/consent",
        body_text="Datenschutzerklärung – Zustimmen und fortfahren",
    )
    calls: list[tuple[str, str | None]] = []

    async def fake_page_body_text(page_obj, timeout: int = 3000):
        return page_obj.body_text

    def fake_is_consent_prompt_text(body_text: str, url: str = "") -> bool:
        return True

    async def fake_click_text_or_role(page_obj, label: str, role: str | None = None) -> bool:
        calls.append((label, role))
        return label in {"Zustimmen und fortfahren", "Continue"}

    async def fake_click_visible_checkbox(page_obj) -> bool:
        calls.append(("checkbox", None))
        return True

    monkeypatch.setattr(worker_module, "_page_body_text", fake_page_body_text)
    monkeypatch.setattr(worker_module, "_is_consent_prompt_text", fake_is_consent_prompt_text)
    monkeypatch.setattr(worker_module, "_click_text_or_role", fake_click_text_or_role)
    monkeypatch.setattr(worker_module, "_click_visible_checkbox", fake_click_visible_checkbox)

    result = asyncio.run(worker_module._handle_consent_prompt(page))

    assert result is True
    assert calls == [
        ("checkbox", None),
        ("Zustimmen und fortfahren", "button"),
        ("Annehmen und beginnen", "button"),
        ("Continue", "button"),
    ]


def test_wait_for_page_settle_returns_on_url_change(worker_module, monkeypatch):
    state = {"stage": 0}

    class FakeLocator:
        @property
        def first(self):
            return self

        async def count(self):
            return 0

        async def is_visible(self):
            return False

    class FakePage:
        @property
        def url(self):
            return "https://example.com/login" if state["stage"] == 0 else "https://example.com/dashboard"

        def locator(self, selector):
            return FakeLocator()

        async def wait_for_load_state(self, state_name, timeout=None):
            state["stage"] = 1

    page = FakePage()

    monkeypatch.setattr(worker_module.asyncio, "sleep", AsyncMock())

    settled = asyncio.run(
        worker_module._wait_for_page_settle(
            page,
            "https://example.com/login",
            timeout_seconds=2,
        )
    )

    assert settled is True


def test_wait_for_page_settle_returns_on_visible_selector(worker_module, monkeypatch):
    state = {"stage": 0}

    class FakeLocator:
        def __init__(self, selector: str):
            self.selector = selector

        @property
        def first(self):
            return self

        async def count(self):
            return 1 if state["stage"] >= 1 and "survey" in self.selector else 0

        async def is_visible(self):
            return state["stage"] >= 1 and "survey" in self.selector

    class FakePage:
        @property
        def url(self):
            return "https://example.com/dashboard"

        def locator(self, selector):
            return FakeLocator(selector)

        async def wait_for_load_state(self, state_name, timeout=None):
            state["stage"] = 1

    page = FakePage()

    monkeypatch.setattr(worker_module.asyncio, "sleep", AsyncMock())

    settled = asyncio.run(
        worker_module._wait_for_page_settle(
            page,
            "https://example.com/dashboard",
            timeout_seconds=2,
            selectors=("#survey_list .survey-item",),
        )
    )

    assert settled is True


def test_get_debug_hold_seconds_reads_env(worker_module, monkeypatch):
    monkeypatch.setenv("HEYPIGGY_DEBUG_HOLD_SECONDS", "42")
    assert worker_module.get_debug_hold_seconds() == 42


def test_get_debug_hold_seconds_falls_back_on_invalid_env(worker_module, monkeypatch):
    monkeypatch.setenv("HEYPIGGY_DEBUG_HOLD_SECONDS", "not-a-number")
    assert worker_module.get_debug_hold_seconds() == 300
