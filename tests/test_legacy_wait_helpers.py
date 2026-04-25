from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

import open_and_connect_chrome
import playstealth_cli
import playwright_chrome_worker


@pytest.mark.asyncio
async def test_wait_for_cdp_ready_polls_until_endpoint_is_available():
    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    calls = [OSError("not ready"), OSError("still not ready"), FakeResponse()]

    def fake_urlopen(*args, **kwargs):
        result = calls.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    with (
        patch.object(open_and_connect_chrome.urllib.request, "urlopen", side_effect=fake_urlopen),
        patch.object(open_and_connect_chrome.asyncio, "sleep", AsyncMock()) as sleep_mock,
    ):
        await open_and_connect_chrome.wait_for_cdp_ready("http://localhost:9222", timeout_seconds=5)

    assert sleep_mock.await_count >= 2


@pytest.mark.asyncio
async def test_playstealth_wait_for_page_settle_detects_url_change():
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
            return "https://example.com/old" if state["stage"] == 0 else "https://example.com/new"

        def locator(self, selector):
            return FakeLocator()

        async def wait_for_load_state(self, state_name, timeout=None):
            state["stage"] = 1

    page = FakePage()

    with patch.object(playstealth_cli.asyncio, "sleep", AsyncMock()):
        settled = await playstealth_cli._wait_for_page_settle(page, "https://example.com/old")

    assert settled is True


@pytest.mark.asyncio
async def test_playwright_wait_for_page_settle_detects_selector_visibility():
    state = {"stage": 0}

    class FakeLocator:
        def __init__(self, selector):
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

    with patch.object(playwright_chrome_worker.asyncio, "sleep", AsyncMock()):
        settled = await playwright_chrome_worker._wait_for_page_settle(
            page,
            "https://example.com/dashboard",
            timeout_seconds=2,
        )

    assert settled is True
