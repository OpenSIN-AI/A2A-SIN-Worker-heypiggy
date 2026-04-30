# fix.md — Bugs & Fixes

| # | Bug | Symptom | Root Cause | Fix | Commit |
|---|-----|---------|------------|-----|--------|
| 1 | cua-driver in runner | Agent nutzt altes Tool | Kein reines skylight-cli | Alle cua-driver refs entfernt | efd363f |
| 2 | open -na Chrome | Kein Stealth-Browser | playstealth-cli nicht genutzt | playstealth-cli launch in StateMachine | efd363f |
| 3 | AXStaticText click | Klick löst nichts aus | Falsches Element-Target | Prompt verbietet AXStaticText, nur Button/Link/RadioButton | efd363f |
| 4 | Kein Vision vor Klick | Blindes Raten | Vision-LLM übersprungen | VisionClient.get_action() vor jedem execute | efd363f |
| 5 | Kein unmask-cli | Keine Stealth-Verifikation | unmask-cli ignoriert | verify_stealth() in VERIFY state | 77581cf |
| 6 | ask_vision() hängt | Keine Koordinaten | NVIDIA API Format | ask_vision_text() intern | 0b72d2e |
| 7 | Lesezeichen-Klicks | Chrome-UI geklickt | Keine UI-Validierung | validate_click_coordinates() | 987e862 |
| 8 | AX-Tree-Kollaps | 0 Elemente | Blink pausiert AX | _AXObserverAddNotificationAndCheckRemote | 2ea1ee6 |
| 9 | Canvas UIs | 70-80% Präzision | Kein OCR-Fallback | VNRecognizeTextRequest | f7b1f31 |

## Status: 9/9 Bugs gefixed ✅
