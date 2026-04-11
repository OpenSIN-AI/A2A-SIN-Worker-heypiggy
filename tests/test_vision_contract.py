"""Pytest coverage for the Vision Gate V2 response contract.

WHY:
- The new perception layer depends on strict schema parsing and deterministic
  worker policy enforcement.
- These tests lock the contract before the worker executes real browser actions.

CONSEQUENCES:
- Regressions in JSON parsing, fallback parsing, or confidence/blocker policy
  are caught with a fast targeted pytest run.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from vision_contract import VisionVerdict, parse_vision_response


# Import the worker module by path so the test remains stable even though the
# repository is currently a flat script-based layout rather than an installed
# package.
MODULE_PATH = Path(__file__).resolve().parents[1] / "heypiggy_vision_worker.py"
SPEC = importlib.util.spec_from_file_location("heypiggy_vision_worker", MODULE_PATH)
worker = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(worker)


def test_parse_vision_response_accepts_valid_json_contract():
    """A fully valid JSON payload should map directly into the strict model."""

    raw_text = """
    {
      "verdict": "PROCEED",
      "confidence": 0.91,
      "page_type": "survey_question",
      "blocker": null,
      "next_action": {
        "type": "click",
        "target": "selector:#survey-65076903",
        "value": ""
      },
      "dom_hash": "abc123def456",
      "reasoning": "The survey question is visible and ready for one click."
    }
    """

    response = parse_vision_response(raw_text)

    assert response.verdict is VisionVerdict.PROCEED
    assert response.confidence == 0.91
    assert response.page_type == "survey_question"
    assert response.blocker is None
    assert response.next_action.type == "click"
    assert response.next_action.target == "selector:#survey-65076903"
    assert response.dom_hash == "abc123def456"


def test_parse_vision_response_falls_back_to_regex_for_malformed_json():
    """Malformed JSON should still salvage a safe structured response."""

    raw_text = (
        'verdict: RETRY confidence: 0.73 page_type: survey_list '
        'reasoning: Modal still covers the survey list next_action: wait target: modal value: loading '
        'blocker_type: modal blocker_detail: consent banner auto_resolvable: true'
    )

    response = parse_vision_response(raw_text)

    assert response.verdict is VisionVerdict.RETRY
    assert response.confidence == 0.73
    assert response.page_type == "survey_list"
    assert response.blocker is not None
    assert response.blocker.type == "modal"
    assert response.blocker.auto_resolvable is True
    assert response.next_action.type == "wait"


def test_parse_vision_response_returns_retry_for_total_garbage():
    """Completely unusable model text must degrade into a safe RETRY response."""

    response = parse_vision_response("totally unusable output without any contract fields")

    assert response.verdict is VisionVerdict.RETRY
    assert response.page_type == "unknown"
    assert response.next_action.type == "none"


def test_low_confidence_policy_forces_retry_even_for_valid_json():
    """Valid JSON must still fail closed when the model is not confident enough."""

    response = parse_vision_response(
        """
        {
          "verdict": "PROCEED",
          "confidence": 0.42,
          "page_type": "survey_question",
          "blocker": null,
          "next_action": {"type": "click", "target": "selector:#go", "value": ""},
          "dom_hash": "hash-low-confidence",
          "reasoning": "I think the button is probably correct."
        }
        """
    )

    guarded = worker._apply_vision_response_policy(response)

    assert guarded.verdict is VisionVerdict.RETRY
    assert guarded.next_action.type == "none"
    assert "Low-confidence" in guarded.reasoning


def test_blocker_policy_distinguishes_auto_resolvable_from_escalation():
    """Worker policy should preserve auto-resolvable blockers and escalate the rest."""

    auto_response = parse_vision_response(
        """
        {
          "verdict": "PROCEED",
          "confidence": 0.88,
          "page_type": "survey_list",
          "blocker": {"type": "modal", "detail": "Cookie banner", "auto_resolvable": true},
          "next_action": {"type": "click", "target": "selector:#accept-cookies", "value": ""},
          "dom_hash": "modal-hash",
          "reasoning": "A dismissible modal blocks the list."
        }
        """
    )
    manual_response = parse_vision_response(
        """
        {
          "verdict": "PROCEED",
          "confidence": 0.88,
          "page_type": "captcha",
          "blocker": {"type": "captcha", "detail": "Challenge page", "auto_resolvable": false},
          "next_action": {"type": "none", "target": "", "value": ""},
          "dom_hash": "captcha-hash",
          "reasoning": "A captcha blocks progress."
        }
        """
    )

    guarded_auto = worker._apply_vision_response_policy(auto_response)
    guarded_manual = worker._apply_vision_response_policy(manual_response)

    assert guarded_auto.verdict is VisionVerdict.PROCEED
    assert guarded_auto.blocker is not None
    assert guarded_auto.blocker.auto_resolvable is True
    assert guarded_manual.verdict is VisionVerdict.ESCALATE
    assert guarded_manual.blocker is not None
    assert guarded_manual.blocker.auto_resolvable is False
