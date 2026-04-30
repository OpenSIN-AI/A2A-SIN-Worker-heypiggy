# fix.md — 9 Bugs gefixed (Production-Ready)

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
