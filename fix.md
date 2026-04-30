# fix.md — Bugs & Fixes

| # | Bug | Symptom | Root Cause | Fix | Commit | Repo |
|---|-----|---------|------------|-----|--------|------|
| 1 | `ask_vision()` hängt | Keine Koordinaten, 26s Timeout | NVIDIA API Format nicht kompatibel | `ask_vision()` nutzt jetzt `ask_vision_text()` intern | `0b72d2e` | A2A-SIN-Worker-heypiggy |
| 2 | Lesezeichen-Klicks | Klick auf Chrome UI (118,93) | Keine UI-Area-Validierung | `validate_click_coordinates()` filtert UI-Bereich | `987e862` | A2A-SIN-Worker-heypiggy |
| 3 | AX-Tree-Kollaps | 0 Elemente bei verdecktem Fenster | Blink pausiert AX-Tree | `_AXObserverAddNotificationAndCheckRemote` private SPI | `2ea1ee6` | skylight-cli |
| 4 | `action["type"]` KeyError | 4 Recoveries, 0 Steps | Vision gibt `"action"` zurück, Code prüft `"type"` | `action.get("action") or action.get("type")` | `8189bea` | stealth-runner |
| 5 | Canvas-Only UIs | 70-80% Präzision ohne AX | Kein OCR-Fallback | Apple Vision `VNRecognizeTextRequest` als dritte Ebene | `f7b1f31` | skylight-cli |
| 6 | Grid-Overlay verwirrt KI | Koordinaten (14,6) = UI | Grid erzeugt visuelles Rauschen | Grid deaktiviert, AX-Tree + OCR priorisiert | `987e862` | A2A-SIN-Worker-heypiggy |
| 7 | `cua_click()` fehlt | NameError in SurveyRunner | Funktion nicht definiert | `cua_click()` manuell hinzugefügt | `987e862` | A2A-SIN-Worker-heypiggy |
| 8 | Falsches Chrome-Fenster | PID 87049 statt Bot-Chrome | `find_bot_window()` findet falsches Fenster | Robuster 4-Stage Fallback mit HeyPiggy-Title-Check | `8189bea` | stealth-runner |

## Status: 8/8 Bugs gefixed ✅
