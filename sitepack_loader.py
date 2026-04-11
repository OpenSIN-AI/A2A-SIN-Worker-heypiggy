#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sitepack loader and validator for site-specific selector management.

WHY THIS MODULE EXISTS:
- Hardcoded CSS selectors in the worker break every time the target site
  changes its DOM structure (class names, IDs, element hierarchy).
- A sitepack externalizes ALL selectors into a versioned JSON manifest so the
  worker itself never needs editing when a site updates its layout.
- The worker becomes site-agnostic: swap the sitepack, target a different site.

WHAT THIS MODULE PROVIDES:
- SitepackLoader: loads, validates, and exposes selectors/flows/signatures
- SitepackValidationError: raised when a sitepack JSON fails schema validation
- SelectorNotFoundError: raised when a requested selector name doesn't exist

CONSEQUENCES:
- Zero hardcoded CSS selectors in the worker code
- Selectors can be updated by non-developers (just edit the JSON)
- Schema validation at load time catches errors before the worker starts clicking
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# WHY: jsonschema gives us robust validation against the sitepack schema.
# If not installed, we fall back to manual required-key checks.
try:
    import jsonschema

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


class SitepackValidationError(Exception):
    """Raised when a sitepack JSON file fails schema validation.

    WHY: A domain-specific exception makes schema violations obvious and
    distinguishable from generic JSON parse errors or file-not-found errors.
    """

    pass


class SelectorNotFoundError(KeyError):
    """Raised when a requested selector name does not exist in the loaded sitepack.

    WHY: A domain-specific exception makes missing-selector bugs obvious.
    The error message includes the list of available selectors so the caller
    can quickly see what names are valid.
    """

    pass


class SitepackLoader:
    """Loads, validates, and exposes a versioned sitepack JSON manifest.

    WHY THIS CLASS EXISTS:
    - The worker needs a single, consistent interface to look up any CSS selector,
      flow sequence, or page signature by name — without hardcoding strings.
    - Centralizing lookups here means typos and missing selectors fail loudly
      at the point of use, not silently deep in a click handler.

    USAGE:
        loader = SitepackLoader()
        loader.load("sitepacks/heypiggy/v1/pack.json")
        email_sel = loader.get_selector("login_email")  # "input[type='email']"

    CONSEQUENCES:
    - All selector references go through get_selector() — grep-able, auditable.
    - Schema validation at load() catches structural errors immediately.
    - match_page_type() enables deterministic page identification from DOM state.
    """

    def __init__(self) -> None:
        """Initialize an empty loader. Call load() before using any getters.

        WHY: Separating init from load allows the worker to create the loader
        at module level and defer loading until the sitepack path is known.
        """
        # WHY: _data holds the raw parsed JSON dict after load()
        self._data: Dict[str, Any] = {}
        # WHY: _loaded prevents accidental use before load() is called
        self._loaded: bool = False
        # WHY: _path stored for diagnostics and logging
        self._path: str = ""

    def load(self, path: str) -> None:
        """Load and validate a sitepack JSON file from disk.

        WHY: Validation at load time catches schema errors before the worker
        starts clicking on missing or malformed selectors.

        CONSEQUENCES:
        - Raises FileNotFoundError if path doesn't exist
        - Raises SitepackValidationError if schema validation fails
        - On success, all getters become usable
        """
        # WHY: resolve() gives us an absolute path for clear error messages
        resolved = Path(path).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Sitepack not found: {resolved}")

        # WHY: explicit encoding prevents platform-dependent surprises
        with open(resolved, "r", encoding="utf-8") as f:
            data = json.load(f)

        # WHY: The schema lives at sitepacks/schema.json — three levels up from
        # sitepacks/heypiggy/v1/pack.json. We look for it relative to the pack.
        schema_path = resolved.parent.parent.parent / "schema.json"

        if HAS_JSONSCHEMA and schema_path.exists():
            # WHY: jsonschema gives us detailed, human-readable validation errors
            with open(schema_path, "r", encoding="utf-8") as sf:
                schema = json.load(sf)
            try:
                jsonschema.validate(instance=data, schema=schema)
            except jsonschema.ValidationError as e:
                raise SitepackValidationError(
                    f"Sitepack validation failed: {e.message}"
                ) from e
        else:
            # WHY: Manual fallback ensures validation even without jsonschema installed.
            # We check for the 5 required top-level keys that every sitepack must have.
            for required_key in (
                "site",
                "version",
                "selectors",
                "flows",
                "page_signatures",
            ):
                if required_key not in data:
                    raise SitepackValidationError(
                        f"Sitepack missing required key: '{required_key}'"
                    )

        # WHY: Only set _loaded=True after all validation passes —
        # ensures the loader is never in a half-loaded broken state.
        self._data = data
        self._loaded = True
        self._path = str(resolved)

        # WHY: Startup log helps operators verify the right sitepack was loaded
        print(f"[SITEPACK] Loaded {data['site']} v{data['version']} from {resolved}")

    def get_selector(self, name: str) -> str:
        """Return the CSS selector string for the given logical name.

        WHY: Central lookup prevents typos, makes missing selectors obvious,
        and provides a clear audit trail of which selectors the worker uses.

        CONSEQUENCES:
        - Raises RuntimeError if load() hasn't been called yet
        - Raises SelectorNotFoundError if the name doesn't exist in the sitepack
        """
        if not self._loaded:
            raise RuntimeError("Sitepack not loaded. Call load() first.")

        selectors = self._data.get("selectors", {})
        if name not in selectors:
            raise SelectorNotFoundError(
                f"Selector '{name}' not found in sitepack. "
                f"Available: {sorted(selectors.keys())}"
            )
        return selectors[name]

    def get_flow(self, name: str) -> List[str]:
        """Return the ordered list of step names for the given flow.

        WHY: Flows define the high-level sequence of actions for a task
        (e.g., login flow = navigate → fill email → fill password → submit).
        Externalizing them lets operators adjust sequences without code changes.
        """
        if not self._loaded:
            raise RuntimeError("Sitepack not loaded. Call load() first.")

        flows = self._data.get("flows", {})
        if name not in flows:
            raise KeyError(
                f"Flow '{name}' not found. Available: {sorted(flows.keys())}"
            )
        return flows[name]

    def get_page_signature(self, name: str) -> List[str]:
        """Return the list of CSS selectors that identify a page type.

        WHY: Page signatures let the worker deterministically identify which
        page it's on by checking which selectors exist in the DOM — more
        reliable than free-form vision text for known page types.
        """
        if not self._loaded:
            raise RuntimeError("Sitepack not loaded. Call load() first.")

        sigs = self._data.get("page_signatures", {})
        if name not in sigs:
            raise KeyError(
                f"Page signature '{name}' not found. Available: {sorted(sigs.keys())}"
            )
        return sigs[name]

    def match_page_type(self, visible_selectors: List[str]) -> str:
        """Match visible selectors against page signatures to determine page type.

        WHY: Instead of relying solely on vision model text to identify the
        current page, the worker can check which signature selectors are
        actually present in the DOM for a deterministic page classification.

        ALGORITHM:
        - For each page type, count how many of its signature selectors appear
          in the visible_selectors list
        - Return the page type with the highest overlap
        - Return 'unknown' if no signatures match at all

        CONSEQUENCES:
        - Deterministic: same DOM state always produces the same classification
        - Fast: pure set intersection, no LLM call needed
        - Composable: can be combined with vision verdict for higher confidence
        """
        if not self._loaded:
            raise RuntimeError("Sitepack not loaded. Call load() first.")

        best_match = "unknown"
        best_score = 0
        # WHY: Converting to set for O(1) intersection lookups
        visible_set = set(visible_selectors)

        for page_type, signature_selectors in self._data.get(
            "page_signatures", {}
        ).items():
            # WHY: Count how many signature selectors are present in the DOM
            score = len(visible_set.intersection(set(signature_selectors)))
            if score > best_score:
                best_score = score
                best_match = page_type

        return best_match

    @property
    def site(self) -> str:
        """The domain name of the loaded sitepack (e.g. 'heypiggy.com')."""
        return self._data.get("site", "unknown")

    @property
    def version(self) -> str:
        """The semver version string of the loaded sitepack."""
        return self._data.get("version", "0.0.0")

    @property
    def is_loaded(self) -> bool:
        """Whether a sitepack has been successfully loaded and validated."""
        return self._loaded
