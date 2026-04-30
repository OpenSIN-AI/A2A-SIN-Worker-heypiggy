# architecture.md — A2A-SIN-Worker-heypiggy

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
