"""
Tests fuer answer_router.py — schliesst Issue #81.

Diese Tests sind die Regression-Coverage gegen halbherzige Aenderungen.
Wer das Routing kaputt macht, sieht es hier sofort.
"""

from __future__ import annotations

import pytest

from answer_router import (
    AnswerDecision,
    Confidence,
    QuestionType,
    Strategy,
    classify_question,
    route_answer,
)
from panel_overrides import detect_panel


# ---------------------------------------------------------------------------
# classify_question
# ---------------------------------------------------------------------------


class TestClassifyQuestion:
    def test_captcha_iframe_wins_over_everything(self):
        assert (
            classify_question(
                "Wie alt sind Sie?",
                ["18-29"],
                has_radio=True,
                has_captcha_iframe=True,
            )
            is QuestionType.CAPTCHA
        )

    def test_captcha_text_marker(self):
        assert (
            classify_question("Bitte bestaetigen Sie: Ich bin kein Roboter")
            is QuestionType.CAPTCHA
        )

    def test_dq_text(self):
        assert (
            classify_question("Leider passen Sie nicht zu dieser Umfrage.")
            is QuestionType.DQ_PAGE
        )

    def test_attention_check_with_quotes(self):
        assert (
            classify_question('Bitte waehlen Sie "Stimme zu" um aufmerksam zu sein.')
            is QuestionType.ATTENTION_CHECK
        )

    def test_attention_check_english(self):
        assert (
            classify_question("To show you are paying attention, please select 'blue'.")
            is QuestionType.ATTENTION_CHECK
        )

    def test_grid_via_text(self):
        assert (
            classify_question("Bitte bewerten Sie die folgenden Aussagen", ["1", "2", "3"])
            is QuestionType.GRID_LIKERT
        )

    def test_grid_via_dom_hint(self):
        assert (
            classify_question("Bewertung", ["1"], is_grid=True)
            is QuestionType.GRID_LIKERT
        )

    def test_slider(self):
        assert classify_question("NPS Score?", has_range=True) is QuestionType.SLIDER

    def test_textarea(self):
        assert (
            classify_question("Was war Ihre Meinung?", has_textarea=True)
            is QuestionType.FREE_TEXT
        )

    def test_dropdown_long(self):
        opts = [f"Option {i}" for i in range(20)]
        assert (
            classify_question("Bitte waehlen", opts, has_select=True)
            is QuestionType.DROPDOWN
        )

    def test_multi_choice_via_text(self):
        assert (
            classify_question(
                "Welche Marken kennen Sie? (alle zutreffenden)",
                ["A", "B", "C"],
            )
            is QuestionType.MULTI_CHOICE
        )

    def test_multi_choice_via_dom(self):
        assert (
            classify_question("Was trifft zu?", ["A", "B"], has_checkbox=True)
            is QuestionType.MULTI_CHOICE
        )

    def test_demographic_overlay(self):
        # Demografische Single-Choice -> DEMOGRAPHIC, nicht plain SINGLE_CHOICE
        assert (
            classify_question("Wie alt sind Sie?", ["18-29", "30-39", "40-49"])
            is QuestionType.DEMOGRAPHIC
        )

    def test_single_choice_default(self):
        assert (
            classify_question("Lieblingsfarbe?", ["Rot", "Blau", "Gruen"])
            is QuestionType.SINGLE_CHOICE
        )

    def test_numeric(self):
        assert classify_question("Wieviel Personen leben in Ihrem Haushalt?") is QuestionType.NUMERIC

    def test_date(self):
        assert classify_question("Was ist Ihr Geburtsdatum?") is QuestionType.DATE

    def test_unknown_fallback(self):
        assert classify_question("") is QuestionType.UNKNOWN


# ---------------------------------------------------------------------------
# route_answer — Reihenfolge der Regeln
# ---------------------------------------------------------------------------


class TestRouterPriorityOrder:
    def test_captcha_overrides_persona(self):
        d = route_answer(
            question_text="Bestaetigen Sie: ich bin kein Roboter",
            persona_resolution={"confidence": "high", "matched_option": "Ja"},
        )
        assert d.strategy is Strategy.PANEL_RULE
        assert d.question_type is QuestionType.CAPTCHA

    def test_dq_page_aborts(self):
        d = route_answer(
            question_text="Leider passen Sie nicht. Vielen Dank.",
        )
        assert d.strategy is Strategy.ABORT_DQ
        assert d.question_type is QuestionType.DQ_PAGE

    def test_panel_dq_marker_aborts_even_without_text_hint(self):
        # Panel-spezifischer DQ-Marker im Body
        panel = detect_panel(url="https://dynata.com/x")
        d = route_answer(
            question_text="Was ist Ihre Lieblingsfarbe?",
            options=["Rot", "Blau"],
            panel=panel,
            panel_body="we apologize, you do not qualify",
        )
        assert d.strategy is Strategy.ABORT_DQ
        assert d.panel == "Dynata"

    def test_attention_overrides_persona(self):
        d = route_answer(
            question_text='Bitte waehlen Sie "Stimme zu" um aufmerksam zu sein.',
            options=["Stimme zu", "Stimme nicht zu", "Egal"],
            persona_resolution={
                "confidence": "high",
                "matched_option": "Stimme nicht zu",
                "topic": "agreement",
                "raw_value": "no",
            },
        )
        assert d.strategy is Strategy.ATTENTION_LITERAL
        assert d.target_option == "Stimme zu"
        assert d.confidence is Confidence.HIGH

    def test_prior_consistency_overrides_persona_unknown(self):
        d = route_answer(
            question_text="Wie viele Geschwister haben Sie?",
            options=["0", "1", "2", "3 oder mehr"],
            persona_resolution={"confidence": "unknown"},
            prior_answer={"answer": "2", "topic": "siblings"},
        )
        assert d.strategy is Strategy.PRIOR_CONSISTENCY
        assert d.target_option == "2"

    def test_persona_high_confidence_picks_match(self):
        d = route_answer(
            question_text="Wie alt sind Sie?",
            options=["18-29", "30-39", "40-49"],
            persona_resolution={
                "confidence": "high",
                "matched_option": "30-39",
                "topic": "age",
                "raw_value": 34,
            },
        )
        assert d.strategy is Strategy.PERSONA_FACT
        assert d.target_option == "30-39"

    def test_persona_multi_match(self):
        d = route_answer(
            question_text="Welche Hobbies haben Sie?",
            options=["Lesen", "Sport", "Reisen", "Kochen"],
            persona_resolution={
                "confidence": "high",
                "matched_option": ["Lesen", "Reisen"],
                "topic": "hobbies",
                "raw_value": ["lesen", "reisen"],
            },
            dom_hints={"has_checkbox": True},
        )
        assert d.strategy is Strategy.PERSONA_FACT
        assert d.target_options == ("Lesen", "Reisen")

    def test_grid_uses_panel_rule(self):
        d = route_answer(
            question_text="Bitte bewerten Sie",
            options=["1", "2", "3", "4", "5"],
            dom_hints={"is_grid": True},
        )
        assert d.strategy is Strategy.PANEL_RULE
        assert d.question_type is QuestionType.GRID_LIKERT
        assert d.min_pause_seconds >= 2.5

    def test_freetext_panel_rule_with_minimum(self):
        panel = detect_panel(url="https://dynata.com/x")
        d = route_answer(
            question_text="Bitte schreiben Sie Ihre Meinung",
            dom_hints={"has_textarea": True},
            panel=panel,
        )
        assert d.strategy is Strategy.PANEL_RULE
        assert d.question_type is QuestionType.FREE_TEXT
        assert "20" in (d.target_value or "")  # Dynata min_free_text_chars=20
        assert d.panel == "Dynata"

    def test_slider_returns_plausible_value(self):
        d = route_answer(
            question_text="Wie wahrscheinlich wuerden Sie uns weiterempfehlen?",
            dom_hints={"has_range": True},
        )
        assert d.strategy is Strategy.PANEL_RULE
        assert d.question_type is QuestionType.SLIDER
        assert d.target_value == "7"

    def test_unknown_fallback_to_vision(self):
        d = route_answer(
            question_text="Lieblingsfarbe?",
            options=["Rot", "Blau"],
            persona_resolution={"confidence": "unknown"},
        )
        assert d.strategy is Strategy.ASK_VISION
        assert d.confidence is Confidence.LOW


# ---------------------------------------------------------------------------
# Panel-Anti-Speeder
# ---------------------------------------------------------------------------


class TestPanelMinPause:
    def test_dynata_has_strict_speeder_threshold(self):
        panel = detect_panel(url="https://dynata.com/q")
        d = route_answer(
            question_text="Lieblingsfarbe?",
            options=["Rot", "Blau"],
            panel=panel,
            persona_resolution={"confidence": "unknown"},
        )
        # Dynata min_seconds_per_question = 3.5
        assert d.min_pause_seconds >= 3.5

    def test_default_pause_when_no_panel(self):
        d = route_answer(
            question_text="Lieblingsfarbe?",
            options=["Rot", "Blau"],
            persona_resolution={"confidence": "unknown"},
        )
        assert d.min_pause_seconds >= 2.0


# ---------------------------------------------------------------------------
# Prompt-Block Rendering (fuer Worker-Integration)
# ---------------------------------------------------------------------------


class TestPromptBlock:
    def test_persona_decision_renders_target(self):
        d = AnswerDecision(
            strategy=Strategy.PERSONA_FACT,
            question_type=QuestionType.DEMOGRAPHIC,
            confidence=Confidence.HIGH,
            target_option="30-39",
            reason="age=34",
            panel="HeyPiggy",
            min_pause_seconds=2.0,
        )
        text = d.as_prompt_block()
        assert "PERSONA_FACT" in text
        assert "30-39" in text
        assert "HeyPiggy" in text
        assert "2.0" in text

    def test_attention_decision_marks_pflicht(self):
        d = AnswerDecision(
            strategy=Strategy.ATTENTION_LITERAL,
            question_type=QuestionType.ATTENTION_CHECK,
            confidence=Confidence.HIGH,
            target_option="Stimme zu",
            reason="literal",
        )
        text = d.as_prompt_block()
        assert "PFLICHT-OPTION" in text
        assert "Stimme zu" in text


# ---------------------------------------------------------------------------
# Smoke-Test: das Modul importiert ohne den Vision-Worker zu laden
# ---------------------------------------------------------------------------


def test_module_imports_without_worker_globals():
    import answer_router  # noqa: F401

    # Es gibt keine globalen Side-Effects, die Worker-Globals erfordern
    assert hasattr(answer_router, "route_answer")
    assert hasattr(answer_router, "classify_question")
