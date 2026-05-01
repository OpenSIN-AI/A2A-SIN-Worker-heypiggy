"""Hauptschleife: Survey-Erkennung -> Beantwortung -> Belohnung."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class SurveyState:
    url: str = ""; steps: int = 0; eur_earned: float = 0.0
    surveys_completed: int = 0; current_question: str = ""
    history: list[dict[str, Any]] = field(default_factory=list)

    def record_step(self, action: str, **detail):
        self.steps += 1; self.history.append({"step": self.steps, "action": action, **detail})
    def add_eur(self, amount: float):
        self.eur_earned += amount; self.surveys_completed += 1
