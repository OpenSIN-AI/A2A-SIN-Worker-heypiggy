"""Erkennt ob wir auf der HeyPiggy-Dashboard-Seite sind."""
from __future__ import annotations
import re

def is_login_page(text: str) -> bool:
    for p in ("einloggen", "anmelden", "sign in", "log in", "email", "passwort"):
        if p in text.lower(): return True
    return False

def is_dashboard(text: str) -> bool:
    for p in ("deine verfügbaren erhebungen", "your available surveys", "verdiene geld", "earn money", "dashboard"):
        if p in text.lower(): return True
    return False

def extract_survey_count(text: str) -> int:
    m = re.search(r"(\d+)\s*(?:verfügbare|available|Umfragen|surveys|Erhebungen)", text, re.I)
    return int(m.group(1)) if m else 0
