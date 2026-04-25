from opensin_runtime import UiFacts, UiSurfaceState, classify_ui_state


def test_dashboard_modal_wins_over_plain_dashboard_list():
    assessment = classify_ui_state(
        UiFacts(
            url="https://www.heypiggy.com/?page=dashboard",
            body_text="Für diese Umfrage suchen wir Personen...",
            question_text="Für diese Umfrage suchen wir Personen...",
            primary_buttons=("Nächste",),
            survey_card_count=24,
            modal_answer_selected=True,
            modal_next_target="Nächste",
            has_modal_overlay=True,
        )
    )

    assert assessment.state == UiSurfaceState.DASHBOARD_MODAL_SURVEY
    assert assessment.recommended_action is not None
    assert assessment.recommended_action.type == "click_next"


def test_dashboard_modal_without_answer_forces_answer_question_target():
    assessment = classify_ui_state(
        UiFacts(
            url="https://www.heypiggy.com/?page=dashboard",
            body_text="Für diese Umfrage suchen wir Personen... 1000 - 1499 Mitarbeiter",
            question_text="Für diese Umfrage suchen wir Personen...",
            modal_answer_target="1000 - 1499 Mitarbeiter",
            modal_answer_selected=False,
            has_modal_overlay=True,
        )
    )

    assert assessment.state == UiSurfaceState.DASHBOARD_MODAL_SURVEY
    assert assessment.recommended_action is not None
    assert assessment.recommended_action.type == "answer_question"
    assert "1000 - 1499" in assessment.recommended_action.target


def test_cashout_landing_is_classified_as_wrong_landing():
    assessment = classify_ui_state(
        UiFacts(
            url="https://www.heypiggy.com/login?page=cashout",
            body_text="Wähle eine Geschenkkarte PayPal International Amazon.de Rossmann",
        )
    )

    assert assessment.state == UiSurfaceState.WRONG_LANDING_CASHOUT
    assert assessment.recommended_action is not None
    assert assessment.recommended_action.type == "navigate_dashboard"


def test_external_survey_question_is_not_misclassified_as_dashboard():
    assessment = classify_ui_state(
        UiFacts(
            url="https://survey.vendor.example/start",
            question_text="Which of these company types do you work with?",
            primary_buttons=("Next",),
            visible_domains=("survey.vendor.example",),
        )
    )

    assert assessment.state == UiSurfaceState.EXTERNAL_SURVEY_QUESTION


def test_dashboard_list_carries_best_selector_target():
    assessment = classify_ui_state(
        UiFacts(
            url="https://www.heypiggy.com/?page=dashboard",
            survey_card_count=24,
            best_survey_selector="#survey-65925591",
        )
    )

    assert assessment.state == UiSurfaceState.DASHBOARD_LIST
    assert assessment.recommended_action is not None
    assert assessment.recommended_action.target == "#survey-65925591"
