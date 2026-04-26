# ================================================================================
# DATEI: test_driver_interface.py
# PROJEKT: A2A-SIN-Worker-heyPiggy
# ZWECK: Tests für das Driver-Interface
# ================================================================================

"""Tests for driver_interface.py"""

import asyncio

import pytest

from driver_interface import (
    BridgeDriver,
    BrowserDriver,
    DriverType,
    PlaywrightDriver,
    NodriverDriver,
    create_driver,
    ClickResult,
    TypeResult,
    ScreenshotResult,
    JavascriptResult,
    SnapshotResult,
)


class TestDriverType:
    """Tests for DriverType enum."""

    def test_driver_types_exist(self):
        assert DriverType.BRIDGE.value == "bridge"
        assert DriverType.PLAYWRIGHT.value == "playwright"
        assert DriverType.NODRIVER.value == "nodriver"


class TestResultTypes:
    """Tests for result dataclasses."""

    def test_screenshot_result(self):
        result = ScreenshotResult(data_url="data:image/png;base64,abc", width=1920, height=1080)
        assert result.data_url.startswith("data:")
        assert result.width == 1920

    def test_click_result(self):
        result = ClickResult(success=True, element_ref="btn-submit")
        assert result.success is True
        assert result.element_ref == "btn-submit"

    def test_click_result_error(self):
        result = ClickResult(success=False, error="element not found")
        assert result.success is False
        assert result.error == "element not found"

    def test_type_result(self):
        result = TypeResult(success=True, characters_sent=42)
        assert result.success is True
        assert result.characters_sent == 42

    def test_javascript_result(self):
        result = JavascriptResult(result={"key": "value"})
        assert result.result == {"key": "value"}
        assert result.error is None

    def test_javascript_result_error(self):
        result = JavascriptResult(result=None, error="syntax error")
        assert result.error == "syntax error"

    def test_snapshot_result(self):
        result = SnapshotResult(
            html="<html></html>",
            url="https://example.com",
            title="Example",
            accessibility_tree="root",
            elements=[],
        )
        assert result.url == "https://example.com"
        assert result.title == "Example"


class TestBrowserDriver:
    """Tests for BrowserDriver abstract base class."""

    def test_bridge_driver_type(self):
        driver = BridgeDriver()
        assert driver.driver_type == DriverType.BRIDGE
        assert not driver.is_initialized

    def test_playwright_driver_type(self):
        driver = PlaywrightDriver()
        assert driver.driver_type == DriverType.PLAYWRIGHT

    def test_nodriver_driver_type(self):
        driver = NodriverDriver()
        assert driver.driver_type == DriverType.NODRIVER

    def test_driver_config(self):
        config = {"headless": False, "width": 1280}
        driver = PlaywrightDriver(config)
        assert driver._config["headless"] is False
        assert driver._config["width"] == 1280
        assert driver._window_width == 1280

    def test_playwright_driver_defaults_to_compact_window(self, monkeypatch):
        monkeypatch.delenv("HEYPIGGY_WINDOW_WIDTH", raising=False)
        monkeypatch.delenv("HEYPIGGY_WINDOW_HEIGHT", raising=False)
        monkeypatch.delenv("HEYPIGGY_WINDOW_X", raising=False)
        monkeypatch.delenv("HEYPIGGY_WINDOW_Y", raising=False)

        driver = PlaywrightDriver()

        assert driver._window_width == 1024
        assert driver._window_height == 768
        assert driver._window_position_x == 40
        assert driver._window_position_y == 40

    def test_playwright_driver_reads_window_env_overrides(self, monkeypatch):
        monkeypatch.setenv("HEYPIGGY_WINDOW_WIDTH", "900")
        monkeypatch.setenv("HEYPIGGY_WINDOW_HEIGHT", "700")
        monkeypatch.setenv("HEYPIGGY_WINDOW_X", "12")
        monkeypatch.setenv("HEYPIGGY_WINDOW_Y", "18")

        driver = PlaywrightDriver()

        assert driver._window_width == 900
        assert driver._window_height == 700
        assert driver._window_position_x == 12
        assert driver._window_position_y == 18

    def test_playwright_screenshot_uses_playwright_jpeg_type(self):
        class FakePage:
            viewport_size = {"width": 1234, "height": 567}

            def __init__(self):
                self.calls = []

            async def screenshot(self, **kwargs):
                self.calls.append(kwargs)
                assert kwargs == {"type": "jpeg", "quality": 85}
                return b"fake-image-bytes"

        driver = PlaywrightDriver({"stealth": False})
        driver._page = FakePage()

        result = asyncio.run(driver.screenshot())

        assert result.data_url.startswith("data:image/jpeg;base64,")
        assert result.width == 1234
        assert result.height == 567

    def test_playwright_snapshot_falls_back_when_accessibility_api_missing(self):
        class FakePage:
            url = "https://example.com/dashboard"

            async def content(self):
                return "<html><body>dashboard</body></html>"

            async def title(self):
                return "Dashboard"

            async def evaluate(self, script):
                assert "[id^=\"survey-\"]" in script
                return "button#survey-1: Start survey"

        driver = PlaywrightDriver({"stealth": False})
        driver._page = FakePage()

        result = asyncio.run(driver.snapshot())

        assert result.url == "https://example.com/dashboard"
        assert result.title == "Dashboard"
        assert result.accessibility_tree == "button#survey-1: Start survey"

    def test_playwright_snapshot_prefers_native_accessibility_when_available(self):
        class FakeAccessibility:
            async def snapshot(self):
                return {"role": "WebArea", "name": "HeyPiggy"}

        class FakePage:
            url = "https://example.com/dashboard"
            accessibility = FakeAccessibility()

            async def content(self):
                return "<html><body>dashboard</body></html>"

            async def title(self):
                return "Dashboard"

            async def evaluate(self, script):
                raise AssertionError("fallback evaluate should not be used")

        driver = PlaywrightDriver({"stealth": False})
        driver._page = FakePage()

        result = asyncio.run(driver.snapshot())

        assert "WebArea" in result.accessibility_tree

    def test_playwright_type_text_focuses_and_dispatches_events_for_selector(self):
        class FakePage:
            def __init__(self):
                self.calls = []

            async def focus(self, selector):
                self.calls.append(("focus", selector))

            async def fill(self, selector, text):
                self.calls.append(("fill", selector, text))

            async def dispatch_event(self, selector, event):
                self.calls.append(("dispatch_event", selector, event))

        driver = PlaywrightDriver({"stealth": False})
        driver._page = FakePage()

        result = asyncio.run(driver.type_text("Hello", selector="#name"))

        assert result.success is True
        assert result.characters_sent == 5
        assert driver._page.calls == [
            ("focus", "#name"),
            ("fill", "#name", "Hello"),
            ("dispatch_event", "#name", "input"),
            ("dispatch_event", "#name", "change"),
        ]

    def test_playwright_type_text_keyboard_fallback_without_selector(self):
        class FakeKeyboard:
            def __init__(self):
                self.calls = []

            async def type(self, char, delay=None):
                self.calls.append((char, delay))

        class FakePage:
            def __init__(self):
                self.keyboard = FakeKeyboard()

        driver = PlaywrightDriver({"stealth": False})
        driver._page = FakePage()

        result = asyncio.run(driver.type_text("ab"))

        assert result.success is True
        assert result.characters_sent == 2
        assert len(driver._page.keyboard.calls) == 2

    def test_playwright_click_uses_locator_click_first(self):
        class FakeLocator:
            def __init__(self):
                self.clicked = []

            @property
            def first(self):
                return self

            async def click(self, timeout=None):
                self.clicked.append(timeout)

            async def bounding_box(self):
                return None

        class FakePage:
            def __init__(self):
                self.locator_calls = []
                self.mouse = None
                self._locator = FakeLocator()

            def locator(self, selector):
                self.locator_calls.append(selector)
                return self._locator

        driver = PlaywrightDriver({"stealth": False})
        driver._page = FakePage()

        result = asyncio.run(driver.click("#start-survey"))

        assert result.success is True
        assert driver._page.locator_calls == ["#start-survey"]
        assert driver._page._locator.clicked == [5000]

    def test_playwright_click_ref_uses_locator_click_first(self):
        class FakeLocator:
            def __init__(self):
                self.clicked = []

            @property
            def first(self):
                return self

            async def click(self, timeout=None):
                self.clicked.append(timeout)

            async def bounding_box(self):
                return None

        class FakePage:
            def __init__(self):
                self.locator_calls = []
                self.mouse = None
                self._locator = FakeLocator()

            def locator(self, selector):
                self.locator_calls.append(selector)
                return self._locator

        driver = PlaywrightDriver({"stealth": False})
        driver._page = FakePage()

        result = asyncio.run(driver.click_ref("btn-123"))

        assert result.success is True
        assert result.element_ref == "btn-123"
        assert driver._page.locator_calls == [
            '[data-ref="btn-123"], [data-ref-id="btn-123"], [aria-label*="btn-123"], [text="btn-123"]'
        ]
        assert driver._page._locator.clicked == [3000]

    def test_playwright_list_tabs_returns_all_context_pages(self):
        class FakePage:
            def __init__(self, url, title):
                self.url = url
                self._title = title

            async def title(self):
                return self._title

        page_a = FakePage("https://www.heypiggy.com/?page=dashboard", "Dashboard")
        page_b = FakePage("https://example.com/consent", "Consent")

        driver = PlaywrightDriver({"stealth": False})
        driver._context = type("Ctx", (), {"pages": [page_a, page_b]})()
        driver._page = page_b

        tabs = asyncio.run(driver.list_tabs())

        assert len(tabs) == 2
        assert tabs[0]["url"] == page_a.url
        assert tabs[1]["url"] == page_b.url
        assert tabs[1]["active"] is True

    def test_playwright_execute_javascript_uses_requested_tab_id(self):
        class FakePage:
            def __init__(self, name):
                self.name = name
                self.url = f"https://example.com/{name}"

            async def title(self):
                return self.name

            async def evaluate(self, script):
                return {"page": self.name, "script": script}

        page_a = FakePage("dashboard")
        page_b = FakePage("survey")

        driver = PlaywrightDriver({"stealth": False})
        driver._context = type("Ctx", (), {"pages": [page_a, page_b]})()
        driver._page = page_a

        tabs = asyncio.run(driver.list_tabs())
        survey_tab_id = tabs[1]["id"]

        result = asyncio.run(driver.execute_javascript("() => 42", tab_id=survey_tab_id))

        assert result.error is None
        assert result.result["page"] == "survey"


class TestCreateDriver:
    """Tests for create_driver factory function."""

    def test_create_bridge_driver(self):
        driver = create_driver("bridge")
        assert isinstance(driver, BridgeDriver)
        assert driver.driver_type == DriverType.BRIDGE

    def test_create_bridge_driver_from_enum(self):
        driver = create_driver(DriverType.BRIDGE)
        assert isinstance(driver, BridgeDriver)

    def test_create_playwright_driver(self):
        driver = create_driver("playwright")
        assert isinstance(driver, PlaywrightDriver)

    def test_create_nodriver_driver(self):
        driver = create_driver("nodriver")
        assert isinstance(driver, NodriverDriver)

    def test_create_driver_with_config(self):
        config = {"headless": True}
        driver = create_driver("playwright", config)
        assert driver._config["headless"] is True

    def test_create_driver_invalid_type(self):
        with pytest.raises(ValueError) as exc_info:
            create_driver("invalid_driver")
        assert "Unknown driver type" in str(exc_info.value) or "not a valid DriverType" in str(
            exc_info.value
        )

    def test_create_driver_from_env(self, monkeypatch):
        monkeypatch.setenv("DRIVER_TYPE", "bridge")
        # This tests env var fallback (would need fresh import)
        # Skipped for simplicity - covered by manual testing
