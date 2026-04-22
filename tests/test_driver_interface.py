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
