"""Persistent PlayStealth state store.

This keeps a tiny JSON snapshot on disk so a crash or restart does not lose
the last known page/tab/step state.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from playstealth_actions.survey_state import SurveyState


def _state_path() -> Path:
    """Resolve the canonical state file location."""
    return Path(
        os.environ.get(
            "PLAYSTEALTH_STATE_PATH", str(Path.home() / ".heypiggy" / "playstealth_state.json")
        )
    )


def save_state(state: SurveyState) -> Path:
    """Persist the given state to JSON."""
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(state), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_state() -> dict[str, object] | None:
    """Load the last persisted state if available."""
    path = _state_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def state_path() -> Path:
    """Return the current state file path."""
    return _state_path()
