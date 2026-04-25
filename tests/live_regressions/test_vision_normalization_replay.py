from __future__ import annotations

import json
from pathlib import Path

import heypiggy_vision_worker as worker


def test_vision_normalization_replay_cases_are_green():
    fixtures_dir = Path(__file__).parent / "vision_fixtures"
    failures: list[dict[str, object]] = []

    for case_dir in sorted(path for path in fixtures_dir.iterdir() if path.is_dir()):
        payload = json.loads((case_dir / "input.json").read_text())
        expected = json.loads((case_dir / "expected.json").read_text())

        raw_output = str(payload.get("raw_output", ""))
        action_desc = str(payload.get("action_desc", "live regression"))
        parsed = worker._extract_vision_json(raw_output)
        normalized = worker._normalize_vision_decision(parsed or {}, action_desc)

        for key, value in expected.items():
            if normalized.get(key) != value:
                failures.append(
                    {
                        "case": case_dir.name,
                        "key": key,
                        "expected": value,
                        "got": normalized.get(key),
                    }
                )

    assert not failures, failures
