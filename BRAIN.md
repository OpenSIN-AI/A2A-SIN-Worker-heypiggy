# BRAIN.md — A2A-SIN-Worker-heypiggy Knowledge Base

> **CEO-Level Erkenntnisse vom 28. April 2026.**
> Diese Datei ist die zentrale Wissensbasis für jeden Agenten, der
> an diesem Repository arbeitet. Lies das VOR jeder Änderung.

---

## 1. Architektur-Regel #1: NUR ECHTES CHROME DEFAULT-PROFIL

**🚨 KRITISCH — STAND 28. APRIL 2026, 18:15 UHR:**

**BRIDGE MCP IST TOT.**
**PLAYWRIGHT PROFIL-CLONE IST FALSCH.**
**KEINE SKRIPTE, KEINE AGENTEN, KEINE WORKER.**
**NUR SHELL-COMMANDS. EIN COMMAND = EINE AKTION.**

### Die EINZIGE Methode die funktioniert:

```
1. Chrome mit ECHTEM Default-Profil öffnen (manuell)
2. Bei HeyPiggy einloggen (manuell, Session-Cache hält 72h)
3. JEDEN Schritt als EINZELNEN Shell-Command ausführen:
   a. screencapture → Screenshot
   b. Puter AI Free → Bildanalyse (kostenlos, GPT-5.4-nano Vision)
   c. cliclick → Klick an Koordinaten
   d. repeat
4. Jeden erfolgreichen Command als .md in successfull/ speichern
```

### Warum nur Shell-Commands:

```
❌ Python-Skripte (worker, agent, orchestrator) → ALLE kaputt
❌ Bridge MCP → KAPUTT
❌ playwright_stealth_worker.py → KAPUTT (show "automatisierte Testsoftware")
❌ playwright_profile_clone → KAPUTT (erkannt als Bot)
❌ CDP/Playwright-Launch → KAPUTT (webdriver=true)
```

### Was FUNKTIONIERT:

```
✅ Echtes Chrome mit Default-Profil (manuell geöffnet)
✅ screencapture -x → Screenshot
✅ Puter AI Free (puter.ai.chat mit gpt-5.4-nano) → kostenlose Bildanalyse
✅ cliclick c:X,Y → Mausklick an Koordinaten
✅ osascript → Chrome-Fenster steuern (activate, bounds)
✅ KEIN VPN! ProtonVPN blockiert HeyPiggy Surveys
```

### Shell-Command-Toolkit:

```bash
# Screenshot
screencapture -x /tmp/step.png

# Puter AI Free Vision (Node.js one-liner)
cd /tmp && node -e "const p=require('@heyputer/puter.js');(async()=>{const a=await p.ai.chat('Was siehst du?','file:///tmp/step.png',{model:'gpt-5.4-nano'});console.log(a)})()"

# Klick
cliclick c:X,Y

# Chrome steuern
osascript -e 'tell application "Google Chrome" to activate'
osascript -e 'tell application "Google Chrome" to set bounds of front window to {0,0,1024,768}'

# Warten
sleep 3
```

### successfull/ Verzeichnis:

Jeder erfolgreiche Command wird als einzelne .md Datei dokumentiert:
```
successfull/
  01-screenshot.md    → Screenshot-Befehl
  02-vision.md        → Puter AI Vision-Befehl
  03-click-survey.md  → Klick auf Survey
  04-verify.md        → Verifikation nach Klick
  ...
```
MacDesktopController (desktop_control.py)
    ├── screencapture (Screenshots per macOS API)
    ├── osascript (Click/Type/Keystroke per AppleScript)
    ├── Koordinatensteuerung (Pixel-genaue Mausklicks)
    └── Keyboard-Control (native Tastatureingaben)

HybridDriver (driver_interface.py)
    ├── PlaywrightDriver (normales Playwright)
    ├── DesktopDriver (MacDesktopController)
    └── HybridDriver (Playwright + Desktop-Fallback)
```

**Workflow:**
1. **Persistentes Chrome-Profil** (`~/.heypiggy/playwright_profile_clone`) nutzen
2. **Session-Cache** (`~/.heypiggy/session_cache.json`) replayen → kein Login nötig
3. **HybridDriver** startet Playwright, fällt bei Problemen auf Desktop-Control zurück
4. **NIE Bridge MCP verwenden** — sie ist broken und deprecated

**Warum direktes Chrome hier OK ist:**
Der `playwright_stealth_worker.py` nutzt ein GEKLONTES Chrome-Profil
(`prepare_playwright_user_data_dir()`), das von einem echten menschlichen
Chrome-Profil kopiert wurde. Das Profil enthält echte Cookies, Extensions
und Browser-Fingerprints — HeyPiggy sieht einen normalen Nutzer.

```
❌ FALSCH:  BRIDGE_MCP_URL=... heypiggy-worker run  (Bridge ist kaputt!)
✅ RICHTIG: DRIVER_TYPE=hybrid heypiggy-worker run   (Desktop-Control)
✅ RICHTIG: python playwright_stealth_worker.py       (mit Profil-Clone!)
```

---

## 2. Cashout-Misclick Defense (3-Layer)

Der Worker hat am 28. April 2026 eine 3-fache Absicherung gegen
Fehlklicks auf Cashout/Header-Navigation bekommen:

1. **DOM-Prescan Regex-Filter** (heypiggy_vision_worker.py, Block 2):
   `cashout|auszahlen|gift.?card|geschenkkarte|einstellungen|settings|profil|profile|faq|hilfe|help|support|abmelden|logout|sign.?out|referral|empfehl`

2. **Vision-LLM Prompt Verbot** (DASHBOARD-VERBOTE Sektion):
   Explizite Anweisung an das Vision-LLM, NIE auf Cashout/Header zu klicken.

3. **Orchestrator Selector-Verengung** (survey_orchestrator.py):
   `_find_best_dashboard_survey()` nutzt nur Survey-spezifische Selektoren
   (`#survey_list .survey-item, div.survey-item, [id^='survey-']`),
   NIEMALS generische `button, a` Selektoren.

---

## 3. unmask-cli Integration (Pre-Flight Scan)

Seit 28. April 2026 ist `heypiggy_preflight.py` im Worker integriert.
Der `SurveyOrchestrator._preflight_scan()` wird VOR jeder Survey-Interaktion
aufgerufen und analysiert:

- **Panel-Detection**: Welche Survey-Engine? (Dynata, Cint, Lucid, etc.)
- **Trap-Scanning**: Honeypots, Attention-Checks, Consistency-Traps
- **Reward-Estimation**: EUR/Minute, EUR/Stunde
- **Risk-Assessment**: DQ-Wahrscheinlichkeit, Risikofaktoren
- **Question-Classification**: Radio, Matrix, Slider, Open-End, etc.

Fallback: Wenn unmask-cli nicht installiert ist, läuft der Worker normal weiter.

---

## 4. Session-Persistenz (72h TTL)

Der Worker speichert Cookies + LocalStorage + SessionStorage in
`~/.heypiggy/session_cache.json` (chmod 600). Beim nächsten Start
wird der Cache automatisch replatziert — kein erneutes Login nötig.

**Cache löschen für frisches Login:** `rm ~/.heypiggy/session_cache.json`

**Unterstützte Domains:** heypiggy.com, puresurvey.com, dynata.com,
sapiosurveys.com, cint.com, lucidhq.com

---

## 5. PlayStealth-Architektur (Sense + Act)

```
unmask-cli (Sense/Röntgen)         playstealth-cli (Act/Ninja)
├── Panel-Detector (7 Engines)      ├── Stealth Engine (568 Zeilen)
├── Trap-Scanner (Honeypots+AC)     ├── Question Router (10 Typen)
├── Reward-Estimator (EUR/min)      ├── Persona Engine
├── Risk-Assessor (DQ-Probability)  ├── Retry Policy
└── Question-Classifier             └── State Machine
         │                                    │
         └──── heypiggy_preflight.py ─────────┘
                        │
              heypiggy_vision_worker.py
              (Bridge MCP + Vision LLM)
```

**Tier-1 Stealth:** `playstealth run-survey --tier1` nutzt Patchright
(patched Playwright mit CDP-Level-Evasion). Cloudflare PASS, CreepJS ≤5 fails.

**Tier-2 Stealth:** Standard playwright-stealth (JS-Level). Cloudflare FAIL,
CreepJS ~15 fails.

---

## 6. Panel-Overrides (Wann und wo)

Panel-spezifische Logik gehört NUR in `panel_overrides.py`, NIE in den
Haupt-Worker. Aktuell unterstützt:

- **PureSpectrum**: Spezielle Consent-Modal-Behandlung
- **Dynata**: Redirect-Handling, spezielle Button-Selektoren
- **Sapio**: iframe-Erkennung, Tab-Wechsel
- **Cint**: Spezielle Progress-Buttons
- **Lucid**: Multi-Page-Navigation

---

## 7. Test-Statistiken (28. April 2026)

| Repo | Tests | Status |
|------|-------|--------|
| A2A-SIN-Worker-heypiggy | 475 pass / 490 total | 15 pre-existing failures (playstealth_cli.py) |
| playstealth-cli | 174/174 | Alle grün (inkl. CreepJS Benchmark) |
| unmask-cli | 34/34 | Alle grün |

---

## 8. Kritische Environment-Variablen

```bash
# Required (Hard-Fail)
export NVIDIA_API_KEY="nvapi-..."
export HEYPIGGY_EMAIL="..."
export HEYPIGGY_PASSWORD="..."
export PYTHONPATH="."

# Desktop Control (NEUE METHODE — Bridge ist deprecated!)
export DRIVER_TYPE="hybrid"          # playwright + desktop fallback
export HEYPIGGY_PROFILE_CLONE="1"    # nutze persistentes Profil

# ⚠️ NICHT MEHR VERWENDEN:
# export BRIDGE_MCP_URL=...          # Bridge ist kaputt!
# export BRIDGE_ADAPTER=...          # Bridge ist kaputt!
# export OPENSIN_BRIDGE_V2=...       # Bridge ist kaputt!
```

---

## 9. Competitive Landscape (April 2026)

| Tool | Stealth-Level | reCAPTCHA | Cloudflare | Preis |
|------|---------------|-----------|------------|-------|
| **CloakBrowser** | C++ (Tier-0) | 0.9 | PASS | Kommerziell |
| **Camoufox** | C++ Firefox | 0.7-0.9 | PASS | Open-Source |
| **Patchright** ✅ | CDP+Binary (Tier-1) | 0.5-0.7 | PASS | MIT |
| **playwright-stealth** ✅ | JS (Tier-2) | 0.3-0.5 | FAIL | MIT |
| **Browser-Use** | LLM-Agent | 0.1-0.3 | FAIL | $0.07/Step |

**Unser Vorteil:** KEIN Konkurrent hat modulare Frage-Handler (10 Typen) +
Cashout-Defense + Pre-Flight-Analyse + Persona-Engine in EINEM Tool.

---

## 10. DO-NOT-TOUCH Liste

- **NIE** `playwright_stealth_worker.py` für Live-Runs verwenden (direktes Chrome!)
- **NIE** `components/ui/*` — shadcn-Primitives (React-Legacy, ungenutzt)
- **NIE** `user_read_only_context/` — Agent-Scratchpad, read-only
- **NIE** Cashout/Header-Selektoren ohne die 3-Layer-Defense

---

*Letzte Aktualisierung: 28. April 2026 — CEO Deep-Dive Session*
