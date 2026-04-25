from __future__ import annotations

from pathlib import Path

from opensin_validation import ReplayHarness


def test_replay_harness_known_live_regressions_are_green():
    fixtures_dir = Path(__file__).parent / "fixtures"
    report = ReplayHarness(fixtures_dir=fixtures_dir).run()
    failures = [check for check in report.checks if not check["ok"]]
    assert report.ok, failures
    assert len(report.checks) >= 12
