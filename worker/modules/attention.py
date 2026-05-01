"""attention.py – Attention-Check detection (extracted from monolith)."""
from __future__ import annotations

ATTENTION_PATTERNS: tuple[str, ...] = (
    "attention check", "aufmerksamkeitstest",
    "please select", "waehlen sie bitte",
    "if you are reading this", "to show you are paying attention",
    "red herring", "trap question", "consistency check",
)

def is_attention_check(text: str) -> bool:
    return any(p in text.lower() for p in ATTENTION_PATTERNS)
