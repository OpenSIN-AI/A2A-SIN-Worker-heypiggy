"""Antwortstrategien pro Persona."""
from __future__ import annotations
import random
from enum import StrEnum
class Persona(StrEnum):
    OPTIMISTIC = "optimistic"; NEUTRAL = "neutral"; CRITICAL = "critical"
DEFAULT_PERSONA = Persona.NEUTRAL
def select_answer(persona: Persona, options: list[str]) -> int:
    if not options: return 0
    if persona == Persona.OPTIMISTIC: return len(options) - 1
    elif persona == Persona.CRITICAL: return 0
    else: return random.randint(0, len(options) - 1)
