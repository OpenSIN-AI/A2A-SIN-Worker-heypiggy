#!/usr/bin/env python3
# ===============================================================================
# DATEI: answer_history.py
# PROJEKT: A2A-SIN-Worker-heyPiggy (OpenSIN AI Agent System)
# ZWECK: Anti-Learn & Learn — persistente Answer-History über Runs hinweg
#
# Was es macht (kurz):
#   Merkt sich: Welche Antwort bei welcher Frage erfolgreich war.
#   Merkt sich: Welche Optionen bei welcher Frage FEHLGESCHLAGEN sind.
#   Verhindert dass der Worker denselben Fehler zweimal macht.
#
# Warum es gebraucht wird:
#   Ohne dieses File: Worker wiederholt blind denselben Fehlklick.
#   Mit diesem File: Worker sieht "Option X hat bei Frage Y schonmal
#   fehlgeschlagen" und wählt eine ANDERE Option.
#
# Design-Prinzipien:
#   - Frage-Signatur = normalisierter Text (Lowercase, Whitespace-stripped).
#   - Erfolg wird IMMER gespeichert (Learn).
#   - Fehlschlag wird IMMER gespeichert (Anti-Learn).
#   - Persistence: JSON-Datei auf Disk, neben session_cache.json.
#   - Keine Duplikate: failed_options Set für jede Frage.
#
# WICHTIG FÜR ENTWICKLER:
#   - Ändere nichts an der Signatur-Logik ohne Tests anzupassen.
#   - Datei-Pfad: ~/.heypiggy/answer_history.json
#   - Bereinigung: Antworten älter als 30 Tage werden bei Save automatisch entfernt.
# ===============================================================================

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Pfad-Override via HEYPIGGY_ANSWER_HISTORY env variable
DEFAULT_HISTORY_PATH: Path = Path(
    os.environ.get(
        "HEYPIGGY_ANSWER_HISTORY",
        str(Path.home() / ".heypiggy" / "answer_history.json"),
    )
)

# Wie lange eine Antwort als "gültig" gilt (30 Tage)
MAX_AGE_SECONDS: int = 30 * 24 * 3600


@dataclass(frozen=True)
class AnswerRecord:
    """
    Ein einzelner Antwort-Eintrag.

    Learned: Welche Antwort war erfolgreich.
    Anti-Learned: Welche Optionen haben fehlgeschlagen.
    """

    question_signature: str
    successful_answer: str | None = None
    failed_options: tuple[str, ...] = ()
    timestamp: float = 0.0
    panel: str | None = None
    question_type: str | None = None


def _normalize_question(text: str) -> str:
    """
    Normalisiert einen Fragetext zur Signatur.

    WHY: "Wie alt sind Sie?" == "wie alt sind sie?" == "  Wie   ALT  sind Sie?  "
    CONSEQUENCES: Gleiche Frage = gleiche Signatur = Learned Answer wird wiederverwendet.
    """
    return " ".join((text or "").strip().lower().split())


def _default_path() -> Path:
    return DEFAULT_HISTORY_PATH


def history_path() -> Path:
    """Öffentlicher Zugriff auf den Standardpfad der Answer-History."""
    return _default_path()


def _load_all(path: Path | None = None) -> dict[str, dict]:
    """
    Lädt die komplette History-Datei.

    WHY: Wir brauchen alle Einträge für Bereinigung + Merge.
    CONSEQUENCES: Bei Parse-Fehler → leeres Dict zurückgeben (kein Crash).
    """
    p = path or _default_path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def load_history(path: Path | None = None) -> dict[str, dict]:
    """Öffentliche Ladefunktion für die vollständige Answer-History."""
    return _load_all(path)


def _save_all(data: dict[str, dict], path: Path | None = None) -> None:
    """
    Schreibt die komplette History-Datei atomar.

    WHY: Bei Crash während des Schreibens soll die Datei nicht korrupt werden.
    CONSEQUENCES: .tmp-Datei → rename (atomar auf POSIX).
    """
    p = path or _default_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(p)
        # chmod 600 wie session_cache.json
        if os.name == "posix":
            import stat
            os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass


def save_history(data: dict[str, dict], path: Path | None = None) -> None:
    """Öffentliche Speicherfunktion für die vollständige Answer-History."""
    _save_all(cleanup_old_entries(data), path)


def cleanup_old_entries(data: dict[str, dict], max_age_seconds: float = MAX_AGE_SECONDS) -> dict[str, dict]:
    """
    Entfernt Einträge älter als max_age_seconds.

    WHY: History-Datei soll nicht unendlich wachsen.
    CONSEQUENCES: 30 Tage Default — genug für eine "Saison" an Umfragen.
    """
    now = time.time()
    cleaned: dict[str, dict] = {}
    for sig, entry in data.items():
        ts = float(entry.get("timestamp", 0)) if isinstance(entry, dict) else 0
        if now - ts <= max_age_seconds:
            cleaned[sig] = entry
    return cleaned


def record_success(
    question_text: str,
    answer: str,
    panel: str | None = None,
    question_type: str | None = None,
    path: Path | None = None,
) -> None:
    """
    Speichert eine ERFOLGREICHE Antwort (Learn).

    WHY: Wenn eine Antwort zum ersten Mal klappt, merken wir sie uns.
    CONSEQUENCES: Beim nächsten Mal → PRIOR_CONSISTENCY liefert diese Antwort.
    """
    sig = _normalize_question(question_text)
    if not sig:
        return
    data = _load_all(path)
    now = time.time()
    existing = data.get(sig, {})
    data[sig] = {
        "successful_answer": str(answer),
        "failed_options": list(existing.get("failed_options", [])),
        "timestamp": now,
        "panel": panel or existing.get("panel"),
        "question_type": question_type or existing.get("question_type"),
    }
    data = cleanup_old_entries(data)
    _save_all(data, path)


def record_failure(
    question_text: str,
    failed_option: str | None = None,
    panel: str | None = None,
    question_type: str | None = None,
    path: Path | None = None,
) -> None:
    """
    Speichert einen FEHLSCHLAG (Anti-Learn).

    WHY: Wenn eine Option fehlgeschlagen ist, darf sie beim nächsten Mal
    NICHT wieder gewählt werden.
    CONSEQUENCES: failed_options wird als Set geführt (keine Duplikate).
    """
    sig = _normalize_question(question_text)
    if not sig:
        return
    data = _load_all(path)
    now = time.time()
    existing = data.get(sig, {})
    failed = set(existing.get("failed_options", []))
    if failed_option:
        failed.add(str(failed_option))
    data[sig] = {
        "successful_answer": existing.get("successful_answer"),
        "failed_options": sorted(failed),
        "timestamp": now,
        "panel": panel or existing.get("panel"),
        "question_type": question_type or existing.get("question_type"),
    }
    data = cleanup_old_entries(data)
    _save_all(data, path)


def get_prior_answer(question_text: str, path: Path | None = None) -> dict[str, Any] | None:
    """
    Holt die gespeicherte Antwort für eine Frage (Learn).

    Returns: {"answer": str, "failed_options": [..], "timestamp": float} oder None
    """
    sig = _normalize_question(question_text)
    if not sig:
        return None
    data = _load_all(path)
    entry = data.get(sig)
    if not isinstance(entry, dict):
        return None
    ts = float(entry.get("timestamp", 0))
    if time.time() - ts > MAX_AGE_SECONDS:
        return None
    return {
        "answer": entry.get("successful_answer"),
        "failed_options": list(entry.get("failed_options", [])),
        "timestamp": ts,
        "panel": entry.get("panel"),
        "question_type": entry.get("question_type"),
    }


def get_failed_options(question_text: str, path: Path | None = None) -> list[str]:
    """
    Holt nur die fehlgeschlagenen Optionen für eine Frage (Anti-Learn).

    Returns: Liste von Option-Strings (leer wenn nichts bekannt).
    """
    prior = get_prior_answer(question_text, path)
    if prior:
        return list(prior.get("failed_options", []))
    return []


def clear_history(path: Path | None = None) -> None:
    """Löscht die komplette History."""
    p = path or history_path()
    try:
        if p.exists():
            p.unlink()
    except Exception:
        pass


def history_summary(path: Path | None = None) -> dict[str, Any]:
    """Liefert eine lesbare Zusammenfassung der History."""
    p = path or history_path()
    data = _load_all(p)
    total = len(data)
    now = time.time()
    fresh = sum(1 for e in data.values() if now - float(e.get("timestamp", 0)) <= MAX_AGE_SECONDS)
    all_failed = sum(len(e.get("failed_options", [])) for e in data.values())
    return {
        "path": str(p),
        "total_questions": total,
        "fresh_entries": fresh,
        "total_failed_options": all_failed,
        "exists": p.exists(),
    }


__all__ = [
    "AnswerRecord",
    "history_path",
    "load_history",
    "save_history",
    "record_success",
    "record_failure",
    "get_prior_answer",
    "get_failed_options",
    "clear_history",
    "history_summary",
    "_normalize_question",
    "_default_path",
]
