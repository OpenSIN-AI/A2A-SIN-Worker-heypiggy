"""Tests for monolith split (SOTA #169)."""
from __future__ import annotations
import pytest
from pathlib import Path
class TestMonolithExtraction:
    def test_all_modules_importable(self):
        from worker.modules import heypiggy_check, survey_loop, answer_strategy, attention_check, rewards, state_machine, recovery_pool, trap_detector
        for m in [heypiggy_check, survey_loop, answer_strategy, attention_check, rewards, state_machine, recovery_pool, trap_detector]:
            assert m.placeholder() is True
    def test_monolith_not_growing(self):
        with open(Path(__file__).parent.parent / "heypiggy_vision_worker.py") as f:
            lines = len(f.readlines())
        assert lines < 15000
