from __future__ import annotations

import json
from pathlib import Path

import pytest

from worker.exceptions import SelectorNotFoundError, SitepackValidationError
from worker.sitepack import SitepackLoader


def test_load_valid_sitepack(tmp_path: Path) -> None:
    path = tmp_path / "pack.json"
    path.write_text(
        json.dumps(
            {
                "site": "heypiggy.com",
                "version": "v1",
                "selectors": {"login_email": "input[type='email']"},
                "flows": {"login": ["https://www.heypiggy.com/login"]},
                "page_signatures": {"login": ["email", "password"]},
            }
        ),
        encoding="utf-8",
    )

    loader = SitepackLoader()
    pack = loader.load(path)

    assert pack.site == "heypiggy.com"
    assert loader.get_selector("login_email") == "input[type='email']"
    assert loader.get_flow("login") == ["https://www.heypiggy.com/login"]


def test_invalid_sitepack_raises_validation_error(tmp_path: Path) -> None:
    path = tmp_path / "pack.json"
    path.write_text(json.dumps({"site": "heypiggy.com"}), encoding="utf-8")

    loader = SitepackLoader()
    with pytest.raises(SitepackValidationError):
        loader.load(path)


def test_unknown_selector_raises(tmp_path: Path) -> None:
    path = tmp_path / "pack.json"
    path.write_text(
        json.dumps(
            {
                "site": "heypiggy.com",
                "version": "v1",
                "selectors": {"login_email": "input[type='email']"},
                "flows": {"login": ["https://www.heypiggy.com/login"]},
                "page_signatures": {"login": ["email", "password"]},
            }
        ),
        encoding="utf-8",
    )

    loader = SitepackLoader()
    loader.load(path)
    with pytest.raises(SelectorNotFoundError):
        loader.get_selector("missing")


def test_repo_heypiggy_sitepack_loads() -> None:
    path = Path(__file__).resolve().parents[2] / "sitepacks" / "heypiggy" / "v1" / "pack.json"
    loader = SitepackLoader()
    pack = loader.load(path)

    assert pack.version == "v1"
    assert loader.get_selector("survey_card") == "div.survey-item"
