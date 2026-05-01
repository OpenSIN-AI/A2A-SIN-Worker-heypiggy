"""EUR-Extraktion aus Abschlussseiten."""
from __future__ import annotations
import re

def extract_eur(text: str) -> float:
    for p in [r"Verdienst[s]?\s*[=:]?\s*(\d+[.,]\d{2})", r"(\d+[.,]\d{2})\s*[€]", r"[€]\s*(\d+[.,]\d{2})", r"EUR\s*[=:]\s*(\d+[.,]\d+)", r"You earned\s+(\d+[.,]\d{2})"]:
        m = re.search(p, text, re.I)
        if m: return float(m.group(1).replace(",", "."))
    return 0.0
