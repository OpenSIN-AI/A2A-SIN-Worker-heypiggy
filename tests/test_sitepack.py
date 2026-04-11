#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the SitepackLoader — validates loading, lookup, and error handling.

WHY THESE TESTS EXIST:
- The sitepack loader is the single point of truth for ALL CSS selectors used
  by the browser automation worker.
- If the loader breaks, the entire worker breaks — no selector can be resolved.
- These tests cover: valid loading, correct lookup, missing selector errors,
  schema validation errors, and deterministic page type matching.

CONSEQUENCES:
- Any regression in the loader is caught before deployment.
- New sitepack fields or validation rules must be accompanied by new tests.
"""

import json
import os
import sys

import pytest

# WHY: Ensure the project root is importable regardless of how pytest is invoked
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sitepack_loader import (
    SelectorNotFoundError,
    SitepackLoader,
    SitepackValidationError,
)

# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

# WHY: A complete valid sitepack dict that matches the schema.
# Used as the baseline for all positive tests.
VALID_SITEPACK = {
    "site": "heypiggy.com",
    "version": "1.0.0",
    "selectors": {
        "login_email": "input[type='email']",
        "login_password": "input[type='password']",
        "login_submit": "button[type='submit']",
        "consent_next": "#submit-button-cpx",
    },
    "flows": {
        "login": ["navigate_to_login", "fill_email", "fill_password", "click_submit"],
    },
    "page_signatures": {
        "login": ["input[type='email']", "input[type='password']"],
        "survey_complete": [".thank-you", ".completion"],
    },
}


def _write_sitepack(data: dict, tmpdir: str) -> str:
    """Helper: write a sitepack dict to a temporary JSON file.

    WHY: Each test needs an isolated sitepack file on disk so load() can
    read it. Using tmp_path ensures no cross-test pollution.
    """
    path = os.path.join(tmpdir, "pack.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return path


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------


class TestSitepackLoader:
    """Test suite for SitepackLoader — covers loading, lookup, and error paths."""

    def test_valid_sitepack_loads_without_error(self, tmp_path):
        """A valid sitepack JSON should load successfully and expose metadata.

        WHY: This is the happy-path baseline. If this fails, nothing else works.
        """
        path = _write_sitepack(VALID_SITEPACK, str(tmp_path))
        loader = SitepackLoader()
        loader.load(path)

        # WHY: Verify the loader extracted site and version correctly
        assert loader.site == "heypiggy.com"
        assert loader.version == "1.0.0"
        assert loader.is_loaded is True

    def test_get_selector_returns_correct_value(self, tmp_path):
        """get_selector() should return the exact CSS selector string for a given name.

        WHY: This is the core contract — the worker calls get_selector('login_email')
        and must receive exactly "input[type='email']", not something else.
        """
        path = _write_sitepack(VALID_SITEPACK, str(tmp_path))
        loader = SitepackLoader()
        loader.load(path)

        # WHY: Test multiple selectors to ensure no key confusion
        assert loader.get_selector("login_email") == "input[type='email']"
        assert loader.get_selector("consent_next") == "#submit-button-cpx"
        assert loader.get_selector("login_submit") == "button[type='submit']"

    def test_get_selector_raises_on_unknown_key(self, tmp_path):
        """Requesting a non-existent selector must raise SelectorNotFoundError.

        WHY: Failing loudly on unknown selectors prevents the worker from
        silently passing None/empty to a bridge click command.
        """
        path = _write_sitepack(VALID_SITEPACK, str(tmp_path))
        loader = SitepackLoader()
        loader.load(path)

        with pytest.raises(SelectorNotFoundError):
            loader.get_selector("nonexistent_selector_that_does_not_exist")

    def test_invalid_sitepack_missing_required_field(self, tmp_path):
        """A sitepack missing required fields should raise SitepackValidationError.

        WHY: Schema validation at load time prevents the worker from starting
        with an incomplete sitepack and then crashing mid-survey when a
        required selector lookup fails.
        """
        # WHY: This sitepack is missing 'selectors', 'flows', and 'page_signatures'
        invalid = {"site": "test.com", "version": "0.1.0"}
        path = _write_sitepack(invalid, str(tmp_path))
        loader = SitepackLoader()

        with pytest.raises(SitepackValidationError):
            loader.load(path)

    def test_match_page_type_identifies_correct_page(self, tmp_path):
        """match_page_type() should identify the page with the most matching selectors.

        WHY: Deterministic page identification from DOM state is more reliable
        than parsing free-form vision model text. This test verifies the
        set-intersection algorithm works correctly for all cases.
        """
        path = _write_sitepack(VALID_SITEPACK, str(tmp_path))
        loader = SitepackLoader()
        loader.load(path)

        # WHY: Both login selectors present → should match 'login'
        result = loader.match_page_type(
            ["input[type='email']", "input[type='password']"]
        )
        assert result == "login"

        # WHY: One completion selector present → should match 'survey_complete'
        result = loader.match_page_type([".thank-you"])
        assert result == "survey_complete"

        # WHY: No matching selectors → should return 'unknown'
        result = loader.match_page_type([".random-unrelated-class"])
        assert result == "unknown"

        # WHY: Empty list → should return 'unknown' (no DOM info available)
        result = loader.match_page_type([])
        assert result == "unknown"
