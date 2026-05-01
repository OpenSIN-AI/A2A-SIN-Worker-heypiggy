"""Mini-State-Machine."""
from __future__ import annotations
from enum import StrEnum, auto
class SurveyPhase(StrEnum):
    INIT = auto(); LOGIN = auto(); DASHBOARD = auto()
    SURVEY_LIST = auto(); SURVEY_ACTIVE = auto(); ATTENTION_CHECK = auto()
    COMPLETION = auto(); ERROR = auto(); DONE = auto()
TRANSITIONS: dict[SurveyPhase, list[SurveyPhase]] = {
    SurveyPhase.INIT: [SurveyPhase.LOGIN, SurveyPhase.DASHBOARD],
    SurveyPhase.LOGIN: [SurveyPhase.DASHBOARD, SurveyPhase.ERROR],
    SurveyPhase.DASHBOARD: [SurveyPhase.SURVEY_LIST, SurveyPhase.ERROR],
    SurveyPhase.SURVEY_LIST: [SurveyPhase.SURVEY_ACTIVE, SurveyPhase.DONE],
    SurveyPhase.SURVEY_ACTIVE: [SurveyPhase.ATTENTION_CHECK, SurveyPhase.COMPLETION, SurveyPhase.ERROR],
    SurveyPhase.ATTENTION_CHECK: [SurveyPhase.SURVEY_ACTIVE, SurveyPhase.ERROR],
    SurveyPhase.COMPLETION: [SurveyPhase.DASHBOARD, SurveyPhase.DONE],
    SurveyPhase.ERROR: [SurveyPhase.DASHBOARD, SurveyPhase.DONE],
    SurveyPhase.DONE: [],
}
