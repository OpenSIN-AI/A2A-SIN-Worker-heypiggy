from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from opensin_runtime import UiFacts, classify_ui_state
from opensin_validation.harness import ValidationReport


@dataclass(frozen=True)
class ReplayFixture:
    name: str
    facts_path: Path
    expected_path: Path


class ReplayHarness:
    """Deterministic replay harness for known worker UI states."""

    def __init__(self, *, fixtures_dir: Path) -> None:
        self._fixtures_dir = fixtures_dir

    def discover(self) -> list[ReplayFixture]:
        fixtures: list[ReplayFixture] = []
        for case_dir in sorted(path for path in self._fixtures_dir.iterdir() if path.is_dir()):
            facts_path = case_dir / "facts.json"
            expected_path = case_dir / "expected.json"
            if facts_path.exists() and expected_path.exists():
                fixtures.append(
                    ReplayFixture(
                        name=case_dir.name,
                        facts_path=facts_path,
                        expected_path=expected_path,
                    )
                )
        return fixtures

    def run(self) -> ValidationReport:
        checks: list[dict[str, object]] = []
        fixtures = self.discover()
        for fixture in fixtures:
            facts_payload = json.loads(fixture.facts_path.read_text())
            expected_payload = json.loads(fixture.expected_path.read_text())

            facts = UiFacts.from_dict(facts_payload)
            assessment = classify_ui_state(facts)

            expected_state = str(expected_payload.get("state", ""))
            checks.append(
                {
                    "name": f"replay.state::{fixture.name}",
                    "ok": assessment.state.value == expected_state,
                    "detail": {
                        "expected": expected_state,
                        "got": assessment.state.value,
                        "reason": assessment.reason,
                    },
                }
            )

            expected_action = str(expected_payload.get("action_type", "") or "")
            if expected_action:
                checks.append(
                    {
                        "name": f"replay.action::{fixture.name}",
                        "ok": (assessment.recommended_action is not None and assessment.recommended_action.type == expected_action),
                        "detail": {
                            "expected": expected_action,
                            "got": assessment.recommended_action.type if assessment.recommended_action else "",
                        },
                    }
                )

            expected_target = str(expected_payload.get("target_contains", "") or "")
            if expected_target:
                checks.append(
                    {
                        "name": f"replay.target::{fixture.name}",
                        "ok": (
                            assessment.recommended_action is not None
                            and expected_target.lower() in assessment.recommended_action.target.lower()
                        ),
                        "detail": {
                            "expected_contains": expected_target,
                            "got": assessment.recommended_action.target if assessment.recommended_action else "",
                        },
                    }
                )

            expected_blockers = tuple(str(item) for item in expected_payload.get("blockers_include", []) or [])
            if expected_blockers:
                checks.append(
                    {
                        "name": f"replay.blockers::{fixture.name}",
                        "ok": all(item in assessment.blockers for item in expected_blockers),
                        "detail": {
                            "expected": list(expected_blockers),
                            "got": list(assessment.blockers),
                        },
                    }
                )

            confidence_min = expected_payload.get("confidence_min")
            if isinstance(confidence_min, (int, float)):
                checks.append(
                    {
                        "name": f"replay.confidence::{fixture.name}",
                        "ok": assessment.confidence >= float(confidence_min),
                        "detail": {
                            "expected_min": float(confidence_min),
                            "got": assessment.confidence,
                        },
                    }
                )

        checks.append(
            {
                "name": "replay.fixture_count",
                "ok": len(fixtures) >= 10,
                "detail": {"count": len(fixtures)},
            }
        )
        return ValidationReport(ok=all(check["ok"] for check in checks), checks=checks)
