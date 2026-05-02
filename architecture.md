# architecture.md — A2A-SIN-Worker-heypiggy

## 2026-05-02: Architecture Scan

**Komponenten (15 Module):**

- `./` (37 Python Dateien)
- `.opencode/plugins/` (0 Python Dateien)
- `.venv/lib/python3.14/site-packages/` (9 Python Dateien)
- `.venv/lib/python3.14/site-packages/PIL/` (95 Python Dateien)
- `.venv/lib/python3.14/site-packages/_pytest/` (48 Python Dateien)
- `.venv/lib/python3.14/site-packages/_pytest/_code/` (3 Python Dateien)
- `.venv/lib/python3.14/site-packages/_pytest/_io/` (5 Python Dateien)
- `.venv/lib/python3.14/site-packages/_pytest/_py/` (3 Python Dateien)
- `.venv/lib/python3.14/site-packages/_pytest/assertion/` (4 Python Dateien)
- `.venv/lib/python3.14/site-packages/_pytest/config/` (5 Python Dateien)

**Sprachen:** N/A

**Total Dateien:** 0

## Status: ARCHIVED als Survey-Logik-Referenz

Nicht gelöscht. Alle CDP-Methoden werden durch Stealth Triade ersetzt.
Die Panel-spezifische Logik ist in `sin_survey_core` extrahiert (stealth-runner).

## Original-Architektur (ALT)

```
Global Brain → Bridge (CDP) → Chrome Extension → DOM → HeyPiggy.com
```

## Neue Architektur (Stealth Triade)

```
stealth-runner → playstealth-cli → skylight-cli → unmask-cli → HeyPiggy.com
```

## Wertvolle Module (Referenz)

- panel_overrides.py → PureSpectrum, Dynata, Sapio, Cint, Lucid Detektoren
- heypiggy_vision_worker.py → Reward-Parser, EUR-Extraktion
- session_store.py → Cookie/Storage Persistenz
- survey_orchestrator.py → Queue-Management
