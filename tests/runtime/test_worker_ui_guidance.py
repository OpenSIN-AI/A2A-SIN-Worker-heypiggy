from __future__ import annotations

import heypiggy_vision_worker as worker
from opensin_runtime import ActionHint, UiAssessment, UiFacts, UiSurfaceState


def test_ui_guided_decision_opens_best_dashboard_survey():
    assessment = UiAssessment(
        state=UiSurfaceState.DASHBOARD_LIST,
        confidence=0.94,
        reason="Visible dashboard with survey cards",
        recommended_action=ActionHint("open_best_survey", "#survey-65925591"),
    )

    decision = worker._decision_from_ui_assessment(assessment, UiFacts())

    assert decision is not None
    assert decision["next_action"] == "click_element"
    assert decision["next_params"] == {"selector": "#survey-65925591"}


def test_ui_guided_decision_accepts_consent_by_label():
    assessment = UiAssessment(
        state=UiSurfaceState.CONSENT_SCREEN,
        confidence=0.97,
        reason="Consent keywords detected",
        recommended_action=ActionHint("accept_consent", "Zustimmen und fortfahren"),
    )

    decision = worker._decision_from_ui_assessment(assessment, UiFacts())

    assert decision is not None
    assert decision["next_action"] == "vision_click"
    assert decision["next_params"] == {"description": "Zustimmen und fortfahren"}


def test_ui_assessment_merges_dashboard_modal_into_survey_active():
    assessment = UiAssessment(
        state=UiSurfaceState.DASHBOARD_MODAL_SURVEY,
        confidence=0.96,
        reason="Question content is embedded inside a HeyPiggy modal overlay",
        recommended_action=ActionHint("answer_question", "question"),
    )

    merged = worker._merge_ui_assessment_into_decision(
        {
            "verdict": "RETRY",
            "page_state": "dashboard",
            "reason": "Vision unsure",
            "next_action": "none",
            "next_params": {},
            "progress": False,
        },
        assessment,
    )

    assert merged["page_state"] == "survey_active"
    assert "UI classifier" in merged["reason"]


def test_ui_guided_decision_answers_dashboard_modal_before_reclicking_card():
    assessment = UiAssessment(
        state=UiSurfaceState.DASHBOARD_MODAL_SURVEY,
        confidence=0.96,
        reason="Question content is embedded inside a HeyPiggy modal overlay",
        recommended_action=ActionHint("answer_question", "1000 - 1499 Mitarbeiter"),
    )

    decision = worker._decision_from_ui_assessment(assessment, UiFacts())

    assert decision is not None
    assert decision["page_state"] == "survey_active"
    assert decision["next_action"] == "vision_click"
    assert decision["next_params"] == {"description": "1000 - 1499 Mitarbeiter"}


def test_ui_guided_decision_clicks_next_inside_dashboard_modal():
    assessment = UiAssessment(
        state=UiSurfaceState.DASHBOARD_MODAL_SURVEY,
        confidence=0.96,
        reason="Question content is embedded inside a HeyPiggy modal overlay",
        recommended_action=ActionHint("click_next", "Nächste"),
    )

    decision = worker._decision_from_ui_assessment(assessment, UiFacts())

    assert decision is not None
    assert decision["next_action"] == "vision_click"
    assert decision["next_params"] == {"description": "Nächste"}


def test_ui_guided_decision_stops_if_start_modal_falls_back_to_dashboard():
    worker._SURVEY_START_PENDING = True
    try:
        assessment = UiAssessment(
            state=UiSurfaceState.DASHBOARD_LIST,
            confidence=0.94,
            reason="Visible HeyPiggy dashboard with survey cards",
            recommended_action=ActionHint("open_best_survey", "#survey-65925591"),
        )

        decision = worker._decision_from_ui_assessment(assessment, UiFacts())
    finally:
        worker._SURVEY_START_PENDING = False

    assert decision is not None
    assert decision["verdict"] == "STOP"
    assert "fail-closed" in decision["reason"]
