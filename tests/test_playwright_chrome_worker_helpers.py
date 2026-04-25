from __future__ import annotations

import importlib
import sys
import types

import pytest


def _install_playwright_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    playwright_pkg = types.ModuleType("playwright")
    playwright_pkg.__path__ = []

    async_api = types.ModuleType("playwright.async_api")

    async def async_playwright():
        raise AssertionError("async_playwright should not be called in helper tests")

    async_api.async_playwright = async_playwright
    playwright_pkg.async_api = async_api

    stealth_pkg = types.ModuleType("playwright_stealth")
    stealth_pkg.__path__ = []
    stealth_submodule = types.ModuleType("playwright_stealth.stealth")

    class Stealth:
        async def apply_stealth_async(self, page):
            return None

    stealth_submodule.Stealth = Stealth
    stealth_pkg.stealth = stealth_submodule

    monkeypatch.setitem(sys.modules, "playwright", playwright_pkg)
    monkeypatch.setitem(sys.modules, "playwright.async_api", async_api)
    monkeypatch.setitem(sys.modules, "playwright_stealth", stealth_pkg)
    monkeypatch.setitem(sys.modules, "playwright_stealth.stealth", stealth_submodule)
    monkeypatch.delitem(sys.modules, "playwright_chrome_worker", raising=False)


@pytest.fixture()
def chrome_worker_module(monkeypatch: pytest.MonkeyPatch):
    _install_playwright_stubs(monkeypatch)
    return importlib.import_module("playwright_chrome_worker")


def test_get_debug_hold_seconds_reads_env(chrome_worker_module, monkeypatch):
    monkeypatch.setenv("HEYPIGGY_DEBUG_HOLD_SECONDS", "17")
    assert chrome_worker_module.get_debug_hold_seconds() == 17


def test_get_debug_hold_seconds_defaults_on_invalid_env(chrome_worker_module, monkeypatch):
    monkeypatch.setenv("HEYPIGGY_DEBUG_HOLD_SECONDS", "invalid")
    assert chrome_worker_module.get_debug_hold_seconds() == 300
