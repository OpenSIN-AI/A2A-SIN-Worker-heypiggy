# BRAIN.md — A2A-SIN-Worker-heypiggy Knowledge Base

> **CEO-Level Erkenntnisse vom 28. April 2026.**
> Diese Datei ist die zentrale Wissensbasis für jeden Agenten, der
> an diesem Repository arbeitet. Lies das VOR jeder Änderung.

---

## 1. Architektur-Regel #1: NIE DIREKT CHROME ÖFFNEN

**Warum:** HeyPiggy erkennt direkte Browser-Launches (CDP, Playwright, Selenium)
und zeigt dann KEINE Umfragen mehr an. Der Bot-Detection-Algorithmus prüft auf
`navigator.webdriver`, CDP-Ports und Headless-Indikatoren.

**Richtiger Weg:** Immer über die **Bridge MCP** (Chrome Extension) arbeiten.
Die Bridge läuft im normalen Chrome-Profil des Nutzers — HeyPiggy sieht einen
echten menschlichen Browser.

```
❌ FALSCH:  python playwright_stealth_worker.py  (direkter Chrome-Launch)
✅ RICHTIG: BRIDGE_MCP_URL=... heypiggy-worker run  (via Bridge Extension)
```

**Bridge URL (Default):** `https://openjerro-opensin-bridge-mcp.hf.space/mcp`

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

# Bridge (Default: HF Spaces)
export BRIDGE_MCP_URL="https://openjerro-opensin-bridge-mcp.hf.space/mcp"
export BRIDGE_HEALTH_URL="https://openjerro-opensin-bridge-mcp.hf.space/health"

# Optional
export HEYPIGGY_MAX_SURVEYS=25
export HEYPIGGY_PERSONA="default"
export HEYPIGGY_COOLDOWN_SEC=4
export BRAIN_URL="http://127.0.0.1:7070"
export OPENSIN_BRIDGE_V2=0  # 0=legacy, 1=opt-in V2
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
