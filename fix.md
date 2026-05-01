# fix.md — 9+ Bugs gefixed, 3 SOTA-Lücken geschlossen (2026-05-01)

## SOTA-Fixes (Mai 2026)

| # | Problem | Lösung | Commit |
|---|---------|--------|--------|
| 10 | Zero Cross-Repo Integration | Unmask/ScreenFollow Drivers + DOM_PRESCAN State | `b1eee1e` |
| 11 | Vision-Kosten > Auszahlung | Vision-free Fast Path via Answer-Router Confidence Gate | `b1eee1e` + `35a76f0` |
| 12 | Stealth-Claims unbewiesen | CreepJS CI Gate bei 80% | `a8865ba` |

## Historische Fixes (April 2026)

| # | Bug | Symptom | Fix | Commit |
|---|-----|---------|-----|--------|
| 1 | cua-driver in runner | Agent nutzt altes Tool | Alle refs entfernt, skylight-cli only | efd363f |
| 2 | open -na Chrome | Kein Stealth-Browser | playstealth-cli launch in StateMachine | efd363f |
| 3 | AXStaticText click | Klick löst nichts aus | Prompt verbietet, nur Button/Link/RadioButton | efd363f |
| 4 | Kein Vision vor Klick | Blindes Raten | VisionClient.get_action() vor execute | efd363f |
| 5 | Kein unmask-cli | Keine Verification | verify_stealth() in VERIFY state | 77581cf |
| 6 | ask_vision() hängt | Keine Koordinaten | ask_vision_text() intern | 0b72d2e |
| 7 | Lesezeichen-Klicks | Chrome-UI geklickt | validate_click_coordinates() | 987e862 |
| 8 | AX-Tree-Kollaps | 0 Elemente | _AXObserverAddNotificationAndCheckRemote | 2ea1ee6 |
| 9 | Canvas UIs | 70-80% Präzision | VNRecognizeTextRequest (OCR) | f7b1f31 |

## 2026-05-01: State Machine läuft mit existierendem Chrome
- Playwright-launch erzeugt kaputte Chrome-Instanz (SingletonLock, on-screen-window)
- Lösung: Chrome separat mit User/Open starten, PID an State Machine übergeben
- `r.pid = CHROME_PID; r.executor.pid = CHROME_PID` setzen
- State Machine läuft dann direkt ab CAPTURE (nicht LAUNCH)
- Die zwei Instanzen via Playwright starben immer mit "No on-screen window"
