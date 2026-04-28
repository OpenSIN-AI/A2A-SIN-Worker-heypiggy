# RUNBOOK — Wie startet man den HeyPiggy-Worker?

Eine einzige Quelle der Wahrheit. Wenn der Worker irgendwo nicht startet,
ist es weil eine der folgenden Voraussetzungen fehlt — nicht weil das Repo
"komisch" ist.

---

## 0. Voraussetzungen

| Was                      | Version  | Pflicht? | Wozu                                  |
| ------------------------ | -------- | -------- | ------------------------------------- |
| Python                   | >= 3.11  | ja       | Runtime                               |
| Chrome / Chromium        | aktuell  | ja       | Bridge-Extension                      |
| OpenSIN-Bridge Extension | latest   | ja       | DOM/CDP-Steuerung                     |
| `uv` oder `pip`          | aktuell  | ja       | Dependency-Install                    |
| NVIDIA NIM API Key       | -        | optional | nur fuer Video/Audio-Analyse          |
| OpenAI / Opencode        | -        | ja       | Vision-Backend                        |
| Infisical Account        | -        | optional | wenn `INFISICAL_AUTO_PULL=1`          |

---

## 1. Erstinstallation

```bash
git clone https://github.com/OpenSIN-AI/A2A-SIN-Worker-heypiggy.git
cd A2A-SIN-Worker-heypiggy

python -m venv .venv
source .venv/bin/activate

pip install -e .
# oder, wenn requirements.txt vorhanden:
pip install -r requirements.txt

cp .env.example .env
# .env editieren — siehe naechster Abschnitt
```

## 2. Pflicht-Umgebungsvariablen

Diese **muessen** gesetzt sein, sonst stoppt der Preflight (das ist
beabsichtigt, siehe Issue #85):

```env
HEYPIGGY_EMAIL=...
HEYPIGGY_PASSWORD=...
BRIDGE_MCP_URL=https://localhost:8765/mcp
BRIDGE_HEALTH_URL=https://localhost:8765/health
VISION_BACKEND=opencode      # oder: nvidia, openai
VISION_MODEL=openai/gpt-5.4-mini-fast
DRIVER_TYPE=playwright       # oder: bridge
```

Nicht-Pflicht, aber empfohlen:

```env
WORKER_ENV=development           # erlaubt SKIP_PREFLIGHT, siehe unten
HEYPIGGY_MAX_SURVEYS=1
ARTIFACT_DIR=./artifacts
LOG_LEVEL=INFO
```

## 3. Smoke-Test (kein Live-Run)

```bash
heypiggy-worker doctor
```

Liefert eine Zeile pro Check:

- Python-Version und installierte Module
- Bridge erreichbar?
- Vision-Auth healthy?
- Persona-Datei lesbar?

Wenn `doctor` durchlaeuft, ist das System grundsaetzlich startbereit.

## 4. Live-Run

```bash
heypiggy-worker run
```

Was passiert:

1. Preflight (fail-closed): Env-Check, Vision-Probe, Bridge-Health.
2. Driver-Initialisierung (Playwright / Bridge).
3. Login auf heypiggy.com (Persona-Credentials).
4. Dashboard-Scan, beste Survey-Karte waehlen (cashout/giftcard ausgeschlossen).
5. Survey-Loop: dom_prescan → answer_router → click → vision_verify.
6. Bei DQ / Speeder-Block: Survey verlassen, naechste Karte.
7. Run-Summary nach `artifacts/run_summary.json`.

## 5. Was ist `SKIP_PREFLIGHT`?

`SKIP_PREFLIGHT=1` deaktiviert die Vision-Auth-Probe vor dem Run. **Nur fuer
Entwicklung/Tests**, NIE in Produktion.

Ab dem Hardening-Commit (Issue #85) wird `SKIP_PREFLIGHT` nur akzeptiert wenn:

- `WORKER_ENV` in `{dev, development, test, ci}` ODER
- `WORKER_ALLOW_PREFLIGHT_SKIP=1` explizit gesetzt ist

Andernfalls wird das Skip-Flag mit Audit-Eintrag ignoriert. Das ist
absichtlich, damit ein versehentlich uebergebenes Env-Var nicht die
Produktionssicherheit aushebelt.

## 6. Logs und Artefakte

Pro Run wird unter `artifacts/<run-id>/` geschrieben:

- `audit.jsonl` — strukturiertes Audit-Log (jede Aktion, jede Entscheidung).
- `screenshots/` — Pre-/Post-Action Screenshots.
- `vision_calls/` — pro Vision-Call die Anfrage + Antwort.
- `run_summary.json` — Aggregierte Metriken (Steps, Errors, Earnings).

Verwende `audit.jsonl` als Wahrheitsquelle bei jeder Diskussion "warum hat
der Worker X gemacht?".

## 7. Haeufige Fehler

| Fehler                                                     | Ursache                              | Loesung                                                   |
| ---------------------------------------------------------- | ------------------------------------ | --------------------------------------------------------- |
| `preflight_failed: bridge_unreachable`                     | Bridge-Extension nicht laeuft        | Chrome starten, Extension aktivieren                      |
| `preflight_failed: vision_auth`                            | Falscher API-Key oder falsches Modell | `.env` pruefen, `heypiggy-worker doctor`                  |
| `WRONG_LANDING_CASHOUT` Recovery-Loop                       | Login-Redirect zur Cashout-Seite     | Persona-Email pruefen, evtl. Captcha im Browser haengen   |
| Worker beendet sich sofort mit Exit-Code 2                  | Pflicht-Env nicht gesetzt            | Schritt 2 dieser Datei lesen                              |
| Vision-Calls timeouten dauerhaft                            | Vision-Backend down                  | Fallback-Backend setzen (`VISION_BACKEND=nvidia`)         |

## 8. Troubleshooting-Reihenfolge

Wenn was nicht klappt, in **dieser** Reihenfolge pruefen:

1. `heypiggy-worker doctor` laesst sich starten?
2. Bridge-Health-URL liefert 200?
3. Vision-API antwortet (curl-Test)?
4. `audit.jsonl` zeigt was zuletzt gemacht wurde?
5. `run_summary.json` zeigt einen `final_exit_reason`?
6. Erst danach Code anfassen.

---

*Wenn dieses Runbook unvollstaendig ist, bitte direkt korrigieren.
Es ist die einzige Stelle die Ground-Truth fuer Inbetriebnahme sein darf.*
