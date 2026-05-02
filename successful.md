# successful.md — Stealth-Triade Session 30. April 2026

> Jeder Erfolg. Jeder Fehler. Festgehalten.

## 2026-05-02: Doctor Scan Results

**Verfügbare Tools (23):**

- ✅ cloc
- ✅ tokei
- ✅ lizard
- ✅ pydeps
- ✅ pyreverse
- ✅ dependency-cruiser
- ✅ code2flow
- ✅ plantuml
- ✅ sphinx
- ✅ mkdocs

**Scan-Ergebnisse:**

- Code-Statistiken: 0 Dateien in N/A
- Fixes: 0 Muster aktualisiert

## 2026-05-02: Doctor Scan Results

**Verfügbare Tools (23):**

- ✅ cloc
- ✅ tokei
- ✅ lizard
- ✅ pydeps
- ✅ pyreverse
- ✅ dependency-cruiser
- ✅ code2flow
- ✅ plantuml
- ✅ sphinx
- ✅ mkdocs

**Scan-Ergebnisse:**

- Code-Statistiken: 0 Dateien in N/A
- Fixes: 0 Muster aktualisiert

## ✅ Erfolge

### 1. Klick-Mechanismus gefunden: AXPress

**Problem:** 4 Stunden lang KEIN einziger Klick auf Chrome 148 / macOS 26.3.1.  
**Root Cause:** `CGEventPostToPid` und `CGEvent.post(tap: .cghidEventTap)` werden beide von Chrome 148 **komplett ignoriert**.  
**Lösung:** `AXUIElementPerformAction(element, kAXPressAction)` — Accessibility-API-Klick.  
**Beweis:** Screenshot-Hashes vor/nach Klick auf "Weiter"-Button unterschiedlich.

### 2. Chrome Accessibility OHNE Crash: VoiceOver-Trick

**Problem:** `--force-renderer-accessibility` Flag crasht Chrome auf macOS 26 (GPU exit_code=15).  
**Lösung:** VoiceOver 1× starten → `chrome://accessibility` → "Suppress automatic" deaktivieren → VoiceOver stoppen → AX-Tree bleibt.  
**Ergebnis:** 27+ Web-Elemente dauerhaft verfügbar. Kein Crash. Kein Flag.

### 3. Google OAuth-Dialog erfolgreich geöffnet

**Aktion:** `skylight-cli click --element-index 45` auf "Google Login-Symbol"  
**Ergebnis:** Seite wechselte von 47 auf 67 Web-Elemente. Login-Felder erschienen.

### 4. `type` Command gebaut

**Vorher:** Kein Type-Command in skylight-cli. Workaround: `osascript keystroke`.  
**Code:** `AXUIElementSetAttributeValue(element, kAXValueAttribute, text)`  
**Beweis:** `skylight-cli type --element-index 50 --text "demo@email.com"` → `"typed": true`, Feld zeigt "demo@email.com".

### 5. safe_click.py — kein Apple-Menü mehr

**Problem:** Agent klickte auf (0,0) = Apple-Menü, weil er Koordinaten riet.  
**Lösung:** `runner/safe_click.py` — Primer → Element-Tabelle → Web-Button finden → `--element-index` klicken. Nie `--x`/`--y`.

### 6. Dokumentation: 129 MD-Dateien gesäubert

- Alle CGEventPostToPid-Lügen aus aktiven Docs entfernt
- 11 Dateien direkt korrigiert (brain, README, SOTA, AGENTS, CONTRIBUTING, banned)
- 7 historische Docs mit ⚠️-Header markiert
- VoiceOver-Trick in allen aktiven brain.md + AGENTS.md dokumentiert

### 7. workspace.yaml in allen 5 Repos

Jedes Repo kennt jetzt alle anderen + Rolle in der Triade + Verbot-Liste.

### 8. `/doctor` Skill (SOTA v2)

Universal. 7 Lenses. P0/P1/P2. Quick + Deep. Funktioniert in jedem Repo.
Infra-opencode-stack deployed.

### 9. `/doc` → `/docx` umbenannt

Keine Verwechslung mit `/doctor` mehr.

---

## ❌ Fehler

### 1. Google-Login: Falsches Feld getippt 🔴

**Was passiert ist:**

- Google Login-Button korrekt geklickt → OAuth-Popup öffnete sich ✅
- `type` Command aufgerufen mit `--element-index 50`
- **ABER:** Element 50 war das E-Mail-Feld der HeyPiggy-Login-Seite, NICHT das Google-OAuth-Popup-Feld

**Warum:**

- Nach dem Google-Login-Klick änderte sich die Seite (Popup erschien)
- Meine Element-Suche (`list-elements`) fand das ERSTE AXTextField mit "E-Mail"
- Das erste Feld war das HeyPiggy-eigene Login-Formular, nicht das Google-Popup
- Hätte warten müssen, bis das Popup vollständig geladen ist, dann E-Mail-Feld IM Popup suchen

**Lösung für nächstes Mal:**

1. Nach Popup-Klick `wait-for-selector` oder sleep(3) abwarten
2. `list-elements` NACH Popup-Ladung
3. E-Mail-Feld mit Pfad-Filter suchen: Pfad muss den neuen Popup-Container enthalten

---

## 📊 Stand Ende Session

| Was                         | Status                    |
| --------------------------- | ------------------------- |
| Klick (AXPress)             | ✅ Funktioniert           |
| Chrome Accessibility        | ✅ VoiceOver-Trick        |
| Text eingeben (type)        | ✅ Funktioniert           |
| Google OAuth öffnen         | ✅ Popup erscheint        |
| E-Mail IM POPUP eintippen   | ❌ Falsches Feld erwischt |
| Passwort IM POPUP eintippen | ❌ Noch nicht             |
| Login abschließen           | ❌ Noch nicht             |
| Dashboard nach Login        | ❌ Noch nicht             |
| Umfrage finden              | ❌ Noch nicht             |
| EUR verdienen               | ❌ Noch nicht             |

## 2026-05-01: ERSTES ERFOLGREICHES STATE-MACHINE-RUN MIT EXISTIERENDEM CHROME

Die State Machine hat 30+ Screenshots via skylight-cli gemacht, DOM prescan lief (confidence 0.70),
Vision-FREE-Path aktiviert (kein teurer Vision-Call!), und Klicks wurden ausgeführt.
Der einzige Grund warum keine EUR verdient wurden: immer dasselbe Element [1] geklickt.
SEOFS
git add -A && git commit -m "docs: fix.md + successful.md updated — State Machine läuft mit existierendem Chrome" && git push origin HEAD:main && echo "✅ docs updated"
