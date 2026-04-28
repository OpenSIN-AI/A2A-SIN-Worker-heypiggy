# ================================================================================
# DATEI: answer_router.py
# PROJEKT: A2A-SIN-Worker-heyPiggy (OpenSIN AI Agent System)
# ZWECK: Provider-aware Answer Router (closes Issue #81)
#
# Was es macht (kurz):
#   Nimmt eine Frage + sichtbare Optionen + (optional) erkanntes Panel und
#   liefert eine deterministische Antwort-Strategie zurueck. Vision muss nicht
#   mehr "raten", sondern bekommt einen klaren Plan: welche Option, mit welcher
#   Begruendung, und wie hart die Regel ist (must / should / suggest).
#
# Warum es gebraucht wird:
#   panel_overrides.detect_panel() injiziert nur einen Prompt-Hint. Das ist
#   schwach: Vision sieht den Hint, kann ihn aber ueberschreiben. Der Router
#   hier trifft die Entscheidung VORHER, mit Code, deterministisch und testbar.
#   Vision wird dann nur noch fuer das beauftragt, was Code nicht kann
#   (z.B. visuelle Verifikation der gewaehlten Option).
#
# Design-Prinzipien:
#   - Deterministisch wo moeglich. Vision nur als Fallback.
#   - Persona-Konsistenz vor Panel-Regeln vor Heuristik.
#   - Attention-Checks und Captchas haben absolute Prioritaet (uebersteuern alles).
#   - Output ist eine Decision-Datenklasse, nicht ein freier String.
#
# WICHTIG FUER ENTWICKLER:
#   - Aenderungen an der Reihenfolge der Regeln aendern Antwort-Verhalten.
#     Wer hier was umstellt, MUSS die Tests in tests/test_answer_router.py
#     verstehen und ggf. anpassen.
#   - Niemals Persona-Werte erfinden. Wenn Persona "unknown" liefert, gibt
#     der Router strategy=ASK_VISION zurueck. Code luegt nicht.
# ================================================================================

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import Enum
from typing import Any, Sequence

from panel_overrides import (
    PanelRules,
    detect_panel,
    detect_panel_dq,
    detect_quality_trap,
)


# ---------------------------------------------------------------------------
# ENUMS
# ---------------------------------------------------------------------------


class QuestionType(str, Enum):
    """
    Strukturelle Klassifikation einer Frage.
    Auf Basis von Optionsliste + Fragetext-Mustern, NICHT per LLM.
    """

    SINGLE_CHOICE = "single_choice"  # Radio-Buttons / einzelne Antwort
    MULTI_CHOICE = "multi_choice"  # Checkboxen / "alle zutreffenden"
    GRID_LIKERT = "grid_likert"  # Matrix-Frage mit Skalen
    FREE_TEXT = "free_text"  # Textarea / Input ohne fixe Optionen
    SLIDER = "slider"  # Range-Input (0-10, NPS, etc.)
    DROPDOWN = "dropdown"  # <select> mit vielen Optionen (Land, Beruf)
    NUMERIC = "numeric"  # Zahl-Input (Alter, PLZ, Einkommen)
    DATE = "date"  # Datum-Input (Geburtsdatum, etc.)
    ATTENTION_CHECK = "attention_check"  # "Bitte waehlen Sie X"
    CAPTCHA = "captcha"  # reCAPTCHA / hCaptcha / Klick-Bestaetigung
    DEMOGRAPHIC = "demographic"  # Alter/Geschlecht/Wohnort etc. (subset of single/dropdown)
    DQ_PAGE = "dq_page"  # Disqualifikation / "Sie passen nicht"
    UNKNOWN = "unknown"


class Strategy(str, Enum):
    """
    Wie soll die Antwort umgesetzt werden?
    """

    PERSONA_FACT = "persona_fact"  # Code kennt Antwort aus Persona-Profil. MUSS gewaehlt werden.
    PANEL_RULE = "panel_rule"  # Provider-spezifische harte Regel (z.B. Captcha-Klick).
    ATTENTION_LITERAL = "attention_literal"  # Woertliche Anweisung der Frage befolgen.
    PRIOR_CONSISTENCY = "prior_consistency"  # Frage wurde schon mal beantwortet — gleich bleiben.
    ASK_VISION = "ask_vision"  # Code weiss es nicht, Vision soll entscheiden.
    ABORT_DQ = "abort_dq"  # Disqualifiziert. Zurueck zum Dashboard.
    HUMAN_DELAY = "human_delay"  # Vor Submit Pause — Speeder-Schutz.


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------------------------------------------------------------------
# DATENMODELL
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AnswerDecision:
    """
    Eine deterministische Antwort-Entscheidung.
    Vision bekommt das als JSON-Block in den Prompt UND als Hard-Constraint:
    wenn strategy != ASK_VISION ist die Antwort schon fixiert, Vision verifiziert
    nur noch visuell, dass die richtige Option vorhanden ist.
    """

    strategy: Strategy
    question_type: QuestionType
    confidence: Confidence
    reason: str
    # Falls Code die Antwort bereits kennt:
    target_option: str | None = None
    target_options: tuple[str, ...] = ()  # Multi-select
    target_value: str | None = None  # Slider/Numeric/FreeText
    # Welches Panel diese Entscheidung beeinflusst hat (None = kein Panel):
    panel: str | None = None
    # Empfohlene Mindest-Pause vor Submit (Anti-Speeder, Anti-Bot):
    min_pause_seconds: float = 0.0
    # Roher Audit-Footprint:
    audit_tag: str = "answer_router"

    def as_prompt_block(self) -> str:
        """
        Rendert die Entscheidung als kompakten Prompt-Block fuer Vision.
        Vision soll diesen Block als Hard-Constraint behandeln (s.o.).
        """
        lines = [f"===== ANSWER-ROUTER ({self.strategy.value.upper()}) ====="]
        lines.append(f"Frage-Typ: {self.question_type.value}")
        if self.panel:
            lines.append(f"Erkanntes Panel: {self.panel}")
        if self.target_option:
            lines.append(f"PFLICHT-OPTION: '{self.target_option}'")
        if self.target_options:
            lines.append("PFLICHT-OPTIONEN (Multi): " + ", ".join(f"'{o}'" for o in self.target_options))
        if self.target_value is not None:
            lines.append(f"PFLICHT-WERT: {self.target_value}")
        if self.min_pause_seconds > 0:
            lines.append(f"VORHER MINDESTENS WARTEN: {self.min_pause_seconds:.1f}s (Anti-Speeder)")
        lines.append(f"Begruendung: {self.reason}")
        lines.append(f"Confidence: {self.confidence.value}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# QUESTION-TYPE-DETECTION
# ---------------------------------------------------------------------------

# WHY: Wir klassifizieren strukturell aus dem DOM-Pre-Scan, NICHT per LLM.
# Heuristik: Welche Eingabe-Elemente liegen unter der Frage?
# - radio + viele Labels       -> SINGLE_CHOICE
# - checkbox + viele Labels    -> MULTI_CHOICE
# - <select> mit > 8 Optionen  -> DROPDOWN
# - <input type=range>         -> SLIDER
# - <input type=number/text> mit Zahl-Pattern in der Frage -> NUMERIC
# - <textarea>                 -> FREE_TEXT
# - Tabelle mit radio-Spalten  -> GRID_LIKERT
# - reCAPTCHA-iframe           -> CAPTCHA
# - DQ-Marker im Text          -> DQ_PAGE
# - Persona-Topic erkannt      -> DEMOGRAPHIC (overlay auf SINGLE/DROPDOWN/NUMERIC)


_GRID_HINTS = ("matrix", "rate the following", "wie sehr stimmen sie", "bitte bewerten")
_CAPTCHA_HINTS = (
    "recaptcha",
    "hcaptcha",
    "ich bin kein roboter",
    "i'm not a robot",
    "verifiziere",
    "verify you are human",
)
_DQ_HINTS = (
    "leider passen sie nicht",
    "you do not qualify",
    "we're sorry",
    "quota full",
    "umfrage abgebrochen",
    "screened out",
)
_DEMO_TOPIC_HINTS = (
    "alter",
    "wie alt",
    "geboren",
    "geschlecht",
    "gender",
    "wohnort",
    "postal",
    "plz",
    "haushalt",
    "income",
    "einkommen",
    "beruf",
    "occupation",
    "ausbildung",
    "education",
    "familienstand",
    "marital",
)


def classify_question(
    question_text: str,
    options: Sequence[str] | None = None,
    *,
    has_textarea: bool = False,
    has_range: bool = False,
    has_select: bool = False,
    has_radio: bool = False,
    has_checkbox: bool = False,
    has_captcha_iframe: bool = False,
    is_grid: bool = False,
) -> QuestionType:
    """
    Klassifiziert eine Frage anhand DOM-Hinweisen + Text-Patterns.

    WHY: Strukturelle Klassifikation gehoert in Code, nicht ins Vision-LLM.
    Vision ist teuer und nicht-deterministisch; Code laeuft in Mikrosekunden.
    """
    qtext = (question_text or "").lower().strip()
    options = list(options or [])

    # 1) Harte Vorrang-Regeln (uebersteuern alles)
    if has_captcha_iframe or any(h in qtext for h in _CAPTCHA_HINTS):
        return QuestionType.CAPTCHA
    if any(h in qtext for h in _DQ_HINTS):
        return QuestionType.DQ_PAGE

    # 2) Attention-Check Pattern (siehe heypiggy_vision_worker.py:5675-5683)
    # WHY: deutsche Eingaben kommen mal als 'wählen', mal als ASCII-Transkript
    # 'waehlen'. Beide muessen matchen.
    _waehlen = r"w(?:ae|[aä])hl(?:en|e)"
    attn_patterns = (
        rf"(?:bitte\s+)?(?:{_waehlen}|klicken|markieren)\s+sie\s+(?:bitte\s+)?['\"“„]",
        r"(?:please\s+)?(?:select|choose|click|pick)\s+['\"“„]",
        r"aufmerksam(?:keit)?[^.!?]{0,60}['\"“„]",
        r"attention[^.!?]{0,60}['\"“„]",
        r"to show you are paying attention",
    )
    for p in attn_patterns:
        if re.search(p, qtext, re.IGNORECASE):
            return QuestionType.ATTENTION_CHECK

    # 3) Strukturelle Klassifikation per DOM-Hinweisen
    if is_grid or any(h in qtext for h in _GRID_HINTS):
        return QuestionType.GRID_LIKERT
    if has_range:
        return QuestionType.SLIDER
    if has_textarea:
        return QuestionType.FREE_TEXT
    if has_select and len(options) > 8:
        return QuestionType.DROPDOWN
    if has_checkbox or _is_multi_select_text(qtext):
        return QuestionType.MULTI_CHOICE
    if has_radio or (options and 2 <= len(options) <= 12):
        # Demografische Single-Choice ist eigene Kategorie (siehe unten)
        if any(h in qtext for h in _DEMO_TOPIC_HINTS):
            return QuestionType.DEMOGRAPHIC
        return QuestionType.SINGLE_CHOICE

    # 4) Numerische Eingaben ohne sichtbare Optionen
    if _is_numeric_question(qtext):
        return QuestionType.NUMERIC
    if _is_date_question(qtext):
        return QuestionType.DATE

    return QuestionType.UNKNOWN


def _is_multi_select_text(qtext: str) -> bool:
    """Erkennt typische Multi-Select-Phrasen."""
    return any(
        h in qtext
        for h in (
            "alle zutreffenden",
            "alle die zutreffen",
            "select all that apply",
            "mehrfachnennung",
            "multiple may apply",
        )
    )


def _is_numeric_question(qtext: str) -> bool:
    return any(
        h in qtext
        for h in (
            "wie alt",
            "your age",
            "plz",
            "postal code",
            "zip",
            "einkommen",
            "income",
            "wieviel",
            "how many",
            "anzahl",
            "number of",
        )
    )


def _is_date_question(qtext: str) -> bool:
    return any(h in qtext for h in ("geburtsdatum", "date of birth", "wann wurden"))


# ---------------------------------------------------------------------------
# ROUTER (DIE ZENTRALE ENTSCHEIDUNG)
# ---------------------------------------------------------------------------


def route_answer(
    *,
    question_text: str,
    options: Sequence[str] | None = None,
    persona_resolution: dict[str, Any] | None = None,
    prior_answer: dict[str, Any] | None = None,
    panel: PanelRules | None = None,
    panel_url: str = "",
    panel_body: str = "",
    dom_hints: dict[str, bool] | None = None,
) -> AnswerDecision:
    """
    Trifft die Antwort-Entscheidung fuer eine einzelne Frage.

    Args:
        question_text: Sichtbarer Fragetext aus dom_prescan.
        options: Sichtbare Antwort-Optionen (Label-Strings).
        persona_resolution: Output von persona.resolve_answer(); kann None sein.
        prior_answer: Output von AnswerLog.find_prior_answer(); kann None sein.
        panel: Ergebnis von panel_overrides.detect_panel(); kann None sein.
        panel_url: Aktuelle URL fuer Detection wenn panel=None.
        panel_body: Body-Text fuer Detection wenn panel=None.
        dom_hints: DOM-Klassifikations-Hinweise (has_radio, has_textarea, ...).

    Returns:
        AnswerDecision — siehe Docstring der Klasse.

    Reihenfolge der Regeln (jede zieht hart):
        1) Captcha / DQ-Page          -> Sofort-Aktion, andere Regeln ignorieren
        2) Attention-Check            -> Woertliche Anweisung, Persona ignorieren
        3) Prior-Consistency          -> Wir haben die Frage schon beantwortet
        4) Persona-Fact (high conf)   -> Code kennt die Wahrheit aus dem Profil
        5) Panel-Rule + Heuristik     -> Provider-spezifische Default-Strategie
        6) ASK_VISION                 -> Letzte Instanz, Vision soll entscheiden
    """
    options_list = list(options or [])
    dom_hints = dom_hints or {}

    # Panel ableiten falls nicht uebergeben
    if panel is None and (panel_url or panel_body):
        panel = detect_panel(url=panel_url, body_text=panel_body)
    panel_name = panel.name if panel else None

    # Frage-Typ klassifizieren
    qtype = classify_question(
        question_text,
        options_list,
        has_textarea=bool(dom_hints.get("has_textarea")),
        has_range=bool(dom_hints.get("has_range")),
        has_select=bool(dom_hints.get("has_select")),
        has_radio=bool(dom_hints.get("has_radio")),
        has_checkbox=bool(dom_hints.get("has_checkbox")),
        has_captcha_iframe=bool(dom_hints.get("has_captcha_iframe")),
        is_grid=bool(dom_hints.get("is_grid")),
    )

    # ---- 1) Sofort-Aktionen ----
    if qtype is QuestionType.CAPTCHA:
        return AnswerDecision(
            strategy=Strategy.PANEL_RULE,
            question_type=qtype,
            confidence=Confidence.HIGH,
            reason="Captcha erkannt. Klicke 'Ich bin kein Roboter' / Verify-Button per click_ref.",
            panel=panel_name,
        )
    if qtype is QuestionType.DQ_PAGE or (panel and detect_panel_dq(panel, panel_body)):
        return AnswerDecision(
            strategy=Strategy.ABORT_DQ,
            question_type=QuestionType.DQ_PAGE,
            confidence=Confidence.HIGH,
            reason="Disqualifikations-Marker erkannt — zurueck zum Dashboard.",
            panel=panel_name,
        )

    # ---- 2) Attention-Check (woertliche Anweisung) ----
    if qtype is QuestionType.ATTENTION_CHECK:
        literal = _extract_attention_target(question_text)
        if literal and options_list:
            best = _best_option_match(literal, options_list)
            if best:
                return AnswerDecision(
                    strategy=Strategy.ATTENTION_LITERAL,
                    question_type=qtype,
                    confidence=Confidence.HIGH,
                    target_option=best,
                    reason=f"Attention-Check: woertliche Anweisung '{literal}'. Persona ignorieren.",
                    panel=panel_name,
                    min_pause_seconds=_panel_min_pause(panel),
                )
        # Fallback: Vision soll die Anweisung visuell finden.
        return AnswerDecision(
            strategy=Strategy.ATTENTION_LITERAL,
            question_type=qtype,
            confidence=Confidence.MEDIUM,
            reason=(
                f"Attention-Check erkannt: '{(literal or '?')}' — Vision muss die "
                "passende Option visuell identifizieren. Persona NICHT verwenden."
            ),
            panel=panel_name,
            min_pause_seconds=_panel_min_pause(panel),
        )

    # ---- 3) Prior-Consistency (wenn die Frage schon beantwortet wurde) ----
    if prior_answer and prior_answer.get("answer"):
        prior = str(prior_answer["answer"])
        best = _best_option_match(prior, options_list) if options_list else None
        return AnswerDecision(
            strategy=Strategy.PRIOR_CONSISTENCY,
            question_type=qtype,
            confidence=Confidence.HIGH,
            target_option=best or None,
            target_value=None if best else prior,
            reason=(
                f"Frage bereits beantwortet (topic={prior_answer.get('topic')!r}). "
                "Konsistenz-Trap-Schutz: gleiche Antwort wiederverwenden."
            ),
            panel=panel_name,
            min_pause_seconds=_panel_min_pause(panel),
        )

    # ---- 4) Persona-Fact (wenn high confidence) ----
    if persona_resolution and persona_resolution.get("confidence") == "high":
        matched = persona_resolution.get("matched_option")
        raw_value = persona_resolution.get("raw_value")
        topic = persona_resolution.get("topic")
        if isinstance(matched, list) and matched:
            return AnswerDecision(
                strategy=Strategy.PERSONA_FACT,
                question_type=qtype if qtype is not QuestionType.UNKNOWN else QuestionType.MULTI_CHOICE,
                confidence=Confidence.HIGH,
                target_options=tuple(str(m) for m in matched),
                reason=f"Persona-Fact (multi): {topic}={raw_value}.",
                panel=panel_name,
                min_pause_seconds=_panel_min_pause(panel),
            )
        if matched:
            return AnswerDecision(
                strategy=Strategy.PERSONA_FACT,
                question_type=qtype,
                confidence=Confidence.HIGH,
                target_option=str(matched),
                reason=f"Persona-Fact: {topic}={raw_value}.",
                panel=panel_name,
                min_pause_seconds=_panel_min_pause(panel),
            )
        if raw_value not in (None, "", 0, ()):
            return AnswerDecision(
                strategy=Strategy.PERSONA_FACT,
                question_type=qtype,
                confidence=Confidence.HIGH,
                target_value=str(raw_value),
                reason=f"Persona-Fact (raw): {topic}={raw_value}.",
                panel=panel_name,
                min_pause_seconds=_panel_min_pause(panel),
            )

    # ---- 5) Panel-Rule + Heuristik ----
    if qtype is QuestionType.GRID_LIKERT:
        return AnswerDecision(
            strategy=Strategy.PANEL_RULE,
            question_type=qtype,
            confidence=Confidence.MEDIUM,
            reason=(
                "Grid/Matrix-Frage. Anti-Straight-Lining: variiere die Antworten "
                "je Zeile um +/- 1 Skalenpunkt um Persona-konsistent zu bleiben."
            ),
            panel=panel_name,
            min_pause_seconds=max(2.5, _panel_min_pause(panel)),
        )
    if qtype is QuestionType.FREE_TEXT:
        min_chars = panel.min_free_text_chars if panel else 12
        return AnswerDecision(
            strategy=Strategy.PANEL_RULE,
            question_type=qtype,
            confidence=Confidence.MEDIUM,
            reason=(
                f"Freitext. Mindestlaenge {min_chars} Zeichen. "
                "Persona-plausibel formulieren, keine Wiederholungen, kein Filler."
            ),
            panel=panel_name,
            target_value=f"min_chars={min_chars}",
            min_pause_seconds=_panel_min_pause(panel),
        )
    if qtype is QuestionType.SLIDER:
        # WHY: Bei NPS-Sliders neigen Bots zu Extremwerten. 7-9 ist menschlich-plausibel.
        return AnswerDecision(
            strategy=Strategy.PANEL_RULE,
            question_type=qtype,
            confidence=Confidence.MEDIUM,
            reason="Slider/Range. Wert per JS setzen (click_ref funktioniert hier nicht).",
            panel=panel_name,
            target_value="7",
            min_pause_seconds=_panel_min_pause(panel),
        )

    # ---- 6) Letzte Instanz: Vision entscheidet ----
    return AnswerDecision(
        strategy=Strategy.ASK_VISION,
        question_type=qtype,
        confidence=Confidence.LOW,
        reason=(
            "Code hat keine sichere Antwort. Vision soll Persona-konform aus den "
            "sichtbaren Optionen waehlen."
        ),
        panel=panel_name,
        min_pause_seconds=_panel_min_pause(panel),
    )


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------


def _panel_min_pause(panel: PanelRules | None) -> float:
    """Liefert die Speeder-Threshold in Sekunden, default 2.0."""
    if panel is None:
        return 2.0
    return float(panel.min_seconds_per_question or 2.0)


# WHY: deutsche Verben akzeptieren ASCII-Transkripte ("waehlen") und Umlaut
# ("wählen"). Beide Schreibweisen muessen extrahiert werden.
_W_WAEHLEN = r"w(?:ae|[aä])hl(?:en|e)"
_ATTN_PATTERNS = (
    rf"(?:bitte\s+)?(?:{_W_WAEHLEN}|klicken|markieren|klicke|tippen?)\s+sie\s+(?:bitte\s+)?['\"“„](.+?)['\"”“]",
    r"(?:please\s+)?(?:select|choose|click|pick|mark|tap)\s+['\"“„](.+?)['\"”“]",
    r"aufmerksam(?:keit)?[^.!?]{0,60}['\"“„](.+?)['\"”“]",
    r"attention[^.!?]{0,60}['\"”“„](.+?)['\"”“]",
    rf"{_W_WAEHLEN}\s+sie\s+(?:die\s+)?(?:option|antwort)\s+([A-Za-zÄÖÜäöüß0-9 ]{{2,30}}?)(?:[.,!?]|$)",
    r"(?:please\s+)?(?:select|choose)\s+(?:the\s+)?(?:option|answer)\s+([A-Za-z0-9 ]{2,30}?)(?:[.,!?]|$)",
)


def _extract_attention_target(qtext: str) -> str | None:
    """Holt den explizit verlangten Antwort-Text aus einem Attention-Check."""
    for pat in _ATTN_PATTERNS:
        m = re.search(pat, qtext, re.IGNORECASE)
        if m:
            t = (m.group(1) or "").strip()
            if 2 <= len(t) <= 80:
                return t
    return None


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _best_option_match(value: str, options: Sequence[str]) -> str | None:
    """Fuzzy-Match: bestes Option-Label fuer den Wert."""
    v = _normalize(value)
    if not v:
        return None
    best: tuple[float, str] = (0.0, "")
    for opt in options:
        ratio = SequenceMatcher(None, v, _normalize(opt)).ratio()
        if v in _normalize(opt) or _normalize(opt) in v:
            ratio = max(ratio, 0.9)
        if ratio > best[0]:
            best = (ratio, opt)
    return best[1] if best[0] >= 0.55 else None


# ---------------------------------------------------------------------------
# PROMPT-BLOCK BUILDER (fuer Worker-Integration)
# ---------------------------------------------------------------------------


def build_router_prompt_block(decision: AnswerDecision) -> str:
    """
    Convenience-Wrapper: liefert den Prompt-Block, den dom_prescan in den
    Vision-Prompt injizieren soll. Bewusst kurz gehalten — Vision liest viel.
    """
    return decision.as_prompt_block()


__all__ = [
    "AnswerDecision",
    "Confidence",
    "QuestionType",
    "Strategy",
    "build_router_prompt_block",
    "classify_question",
    "route_answer",
]
