from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class UiSurfaceState(str, Enum):
    UNKNOWN = "UNKNOWN"
    LOGIN = "LOGIN"
    WRONG_LANDING_CASHOUT = "WRONG_LANDING_CASHOUT"
    DASHBOARD_LIST = "DASHBOARD_LIST"
    DASHBOARD_MODAL_SURVEY = "DASHBOARD_MODAL_SURVEY"
    CONSENT_SCREEN = "CONSENT_SCREEN"
    EXTERNAL_SURVEY_QUESTION = "EXTERNAL_SURVEY_QUESTION"
    CAPTCHA = "CAPTCHA"


@dataclass(frozen=True)
class ActionHint:
    type: str
    target: str = ""


@dataclass(frozen=True)
class UiFacts:
    url: str = ""
    title: str = ""
    body_text: str = ""
    question_text: str = ""
    primary_buttons: tuple[str, ...] = ()
    survey_card_count: int = 0
    best_survey_selector: str = ""
    modal_answer_target: str = ""
    modal_next_target: str = ""
    modal_answer_selected: bool = False
    has_modal_overlay: bool = False
    has_captcha_widget: bool = False
    visible_domains: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "UiFacts":
        return cls(
            url=str(payload.get("url", "") or ""),
            title=str(payload.get("title", "") or ""),
            body_text=str(payload.get("body_text", "") or ""),
            question_text=str(payload.get("question_text", "") or ""),
            primary_buttons=tuple(str(item) for item in payload.get("primary_buttons", []) or []),
            survey_card_count=int(payload.get("survey_card_count", 0) or 0),
            best_survey_selector=str(payload.get("best_survey_selector", "") or ""),
            modal_answer_target=str(payload.get("modal_answer_target", "") or ""),
            modal_next_target=str(payload.get("modal_next_target", "") or ""),
            modal_answer_selected=bool(payload.get("modal_answer_selected", False)),
            has_modal_overlay=bool(payload.get("has_modal_overlay", False)),
            has_captcha_widget=bool(payload.get("has_captcha_widget", False)),
            visible_domains=tuple(str(item) for item in payload.get("visible_domains", []) or []),
        )


@dataclass(frozen=True)
class UiAssessment:
    state: UiSurfaceState
    confidence: float
    reason: str
    recommended_action: ActionHint | None = None
    blockers: tuple[str, ...] = field(default_factory=tuple)


_CONSENT_MARKERS = (
    "i want to complete this survey",
    "continue with the other survey",
    "zustimmen und fortfahren",
    "annehmen und beginnen",
    "datenschutzerklärung",
    "consent",
)

_CAPTCHA_MARKERS = (
    "i am not a robot",
    "ich bin kein robot",
    "verify you are human",
    "security check",
    "captcha",
)

_LOGIN_MARKERS = (
    "mit google",
    "continue with google",
    "google",
    "anmelden",
    "sign in",
)

_NEXT_MARKERS = ("nächste", "naechste", "weiter", "next", "continue", "fortfahren")


def classify_ui_state(facts: UiFacts) -> UiAssessment:
    combined_text = " ".join(
        [facts.url, facts.title, facts.body_text, facts.question_text, *facts.primary_buttons]
    ).lower()
    is_heypiggy = "heypiggy.com" in facts.url.lower()
    next_button = next(
        (
            button
            for button in facts.primary_buttons
            if any(marker in button.lower() for marker in _NEXT_MARKERS)
        ),
        "",
    )
    has_next = bool(next_button)
    has_question = bool(facts.question_text.strip())
    consent_button = next(
        (
            button
            for button in facts.primary_buttons
            if any(marker in button.lower() for marker in ("continue", "fortfahren", "zustimmen", "annehmen"))
        ),
        "Continue",
    )
    google_button = next(
        (
            button
            for button in facts.primary_buttons
            if any(marker in button.lower() for marker in ("google", "anmelden", "sign in"))
        ),
        "Continue with Google",
    )

    if facts.has_captcha_widget or any(marker in combined_text for marker in _CAPTCHA_MARKERS):
        return UiAssessment(
            state=UiSurfaceState.CAPTCHA,
            confidence=0.99,
            reason="Captcha widget or captcha marker detected",
            recommended_action=ActionHint("escalate_captcha"),
            blockers=("captcha",),
        )

    if any(marker in combined_text for marker in _CONSENT_MARKERS):
        return UiAssessment(
            state=UiSurfaceState.CONSENT_SCREEN,
            confidence=0.97,
            reason="Consent keywords detected",
            recommended_action=ActionHint("accept_consent", consent_button),
        )

    if is_heypiggy and any(marker in combined_text for marker in ("cashout", "geschenkkarte", "paypal international", "amazon.de", "rossmann")):
        return UiAssessment(
            state=UiSurfaceState.WRONG_LANDING_CASHOUT,
            confidence=0.98,
            reason="Cashout or giftcard landing detected on HeyPiggy",
            recommended_action=ActionHint("navigate_dashboard", "https://www.heypiggy.com/?page=dashboard"),
            blockers=("wrong_landing",),
        )

    if is_heypiggy and facts.has_modal_overlay and has_question:
        action_type = "click_next" if facts.modal_answer_selected and (facts.modal_next_target or has_next) else "answer_question"
        if action_type == "click_next":
            target = facts.modal_next_target or next_button
        else:
            target = facts.modal_answer_target or facts.question_text[:80]
        return UiAssessment(
            state=UiSurfaceState.DASHBOARD_MODAL_SURVEY,
            confidence=0.96,
            reason="Question content is embedded inside a HeyPiggy modal overlay",
            recommended_action=ActionHint(action_type, target),
        )

    if is_heypiggy and facts.survey_card_count > 0:
        return UiAssessment(
            state=UiSurfaceState.DASHBOARD_LIST,
            confidence=0.94,
            reason="Visible HeyPiggy dashboard with survey cards",
            recommended_action=ActionHint("open_best_survey", facts.best_survey_selector),
        )

    if not is_heypiggy and (has_question or has_next or any(domain for domain in facts.visible_domains if domain)):
        return UiAssessment(
            state=UiSurfaceState.EXTERNAL_SURVEY_QUESTION,
            confidence=0.92,
            reason="External survey domain with live question controls",
            recommended_action=ActionHint("answer_question"),
        )

    if any(marker in combined_text for marker in _LOGIN_MARKERS):
        return UiAssessment(
            state=UiSurfaceState.LOGIN,
            confidence=0.85,
            reason="Login markers detected",
            recommended_action=ActionHint("continue_google_login", google_button),
        )

    return UiAssessment(
        state=UiSurfaceState.UNKNOWN,
        confidence=0.2,
        reason="No deterministic UI state matched",
        blockers=("unclassified",),
    )
