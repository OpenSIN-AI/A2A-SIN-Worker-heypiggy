# Northstar — A2A-SIN-Worker-heypiggy

> **Status:** strategischer Reset, 2026-04-28.
> **Aussteller:** v0 audit pass (act as CEO).

## 1. Was bauen wir wirklich?

Ein **headless Survey-Earnings-Agent** der auf [heypiggy.com](https://heypiggy.com)
und den dahinterliegenden Panels (Cint / Lucid / Dynata / PureSpectrum / Sapio)
**reproduzierbar Punkte und Cent** verdient — ohne dass ein Mensch im Loop sitzt
und ohne dass der Account gesperrt wird.

Alles andere (Vision-Pipeline, Bridge, Persona, Trap-Detection, …) ist Mittel
zum Zweck. Wenn am Monatsende kein Cent ankommt, ist der Code wertlos. Punkt.

## 2. Was ist heute kaputt?

Drei harte Wahrheiten aus dem Audit:

1. **Der Worker ist 17 KLOC schwer und re-implementiert das was es bereits in
   `SIN-CLIs/playstealth-cli` und `SIN-CLIs/unmask-cli` als saubere, kleine,
   getestete CLIs gibt.** Das ist Verschwendung und macht jeden Refactor teurer.
2. **Es gibt keinen einzigen verifizierten End-to-End-Earnings-Run.** Der Worker
   kann starten, klicken, Survey-Tabs verfolgen — aber dass am Ende reale Punkte
   gutgeschrieben werden, ist unbewiesen.
3. **Die AI-Backend-Wahl ist unkoordiniert.** OpenAI, Anthropic, Gemini, Vercel
   AI Gateway, lokale Modelle, jüngst auch noch "Puter.ai" — jeder Pfad ist
   teilweise verkabelt, keiner ist sauber dokumentiert. Latenz-/Kosten-Vergleich
   fehlt komplett.

## 3. Northstar-Architektur (Ziel-Bild)

```
                      heypiggy.com Account
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  A2A-SIN-Worker-heypiggy  (THIS REPO — orchestrator only)        │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  worker/loop.py — sequential session manager               │  │
│  │  worker/cli.py  — entrypoint + run-id + audit              │  │
│  └────────────────────────────────────────────────────────────┘  │
│        │              │                   │                      │
│        ▼              ▼                   ▼                      │
│  ┌──────────┐   ┌───────────────┐   ┌────────────────────┐       │
│  │ AI Layer │   │ Sees-the-Page │   │ Hides-the-Tab      │       │
│  │ backend  │   │   = unmask    │   │   = playstealth    │       │
│  │ selector │   │     (TS RPC)  │   │      (Python CLI)  │       │
│  └──────────┘   └───────────────┘   └────────────────────┘       │
│        │              │                   │                      │
└────────┼──────────────┼───────────────────┼──────────────────────┘
         │              │                   │
         ▼              ▼                   ▼
   AI Gateway     unmask-cli         playstealth-cli
   (primary)      JSON-RPC 2.0       subprocess CLI
   + Puter        (stdio / HTTP+WS)  + tool registry
   (fallback)     replay bundles     human behaviour
```

### Verantwortlichkeiten

| Schicht | Repo | Aufgabe |
|---|---|---|
| **Orchestrator** | `A2A-SIN-Worker-heypiggy` (dieses Repo) | Session-Loop, Persona, Answer-Routing, Audit-Trail, Earnings-Tracking, Webhook-Out, Recovery. **Keine eigene Browser-Logik.** |
| **Sees-the-Page** | `SIN-CLIs/unmask-cli` | DOM/Network/Console-Capture, semantic element scan, selfHeal Locator, `act/extract/observe` LLM-API, Replay-Bundles. Wird per JSON-RPC angesprochen. |
| **Hides-the-Tab** | `SIN-CLIs/playstealth-cli` | Stealth-Browser, Persona-Bindung, human-input rhythms, `open-list` / `click-survey` / `answer-survey`. Wird per CLI-Subprocess angesprochen. |
| **AI** | Vercel AI Gateway (primary) + Puter (optional fallback) | Vision/Reasoning auf strukturierten Page-Snapshots. Single API-Key, multi-vendor. |

## 4. Was muss aus diesem Repo VERSCHWINDEN

Diese Module re-implementieren `unmask` und/oder `playstealth` und gehören
**ersatzlos gelöscht**, sobald die Integration steht (siehe
[`04-MIGRATION-ROADMAP.md`](./04-MIGRATION-ROADMAP.md)):

- Eigene Playwright-/CDP-Wiring (alles was `unmask-network`/`unmask-dom` bereits
  liefert).
- Eigene "click-by-coords" / "human-mouse" Helfer (playstealth `human_behavior`).
- Eigene DOM-Selector-Heuristiken (unmask selfHeal multi-strategy resolver).
- Eigene "stealth bench" / Anti-Detect-Blobs (playstealth stealth_enhancer).

`heypiggy_vision_worker.py` ~9 KLOC schrumpft damit auf ~2-3 KLOC reine
Orchestrierung. Das ist das Ziel.

## 5. Was BLEIBT in diesem Repo

- `worker/` Package — sequential loop, audit, retry, checkpoints, exceptions.
- `survey_orchestrator.py` — heypiggy-spezifische Survey-Auswahl + Earnings-Tracking.
- `persona.py` — heypiggy-spezifische Persona-Definitionen.
- `panel_overrides.py` + **`answer_router.py`** (neu, Issue #81) — heypiggy-
  spezifische Antwort-Strategien pro Panel.
- `session_store.py` — heypiggy-spezifischer Run-State.
- `worker/integrations/unmask_client.py` (neu) — JSON-RPC Client.
- `worker/integrations/playstealth_client.py` (neu) — Subprocess-Client.
- `worker/ai/backend.py` (neu) — AI-Backend-Selektor.

Alles andere ist Migrations-Kandidat.

## 6. Erfolgs-Metriken (KEINE Marketing-Zahlen, sondern Messpunkte)

| Metrik | Zielwert | Wie wird gemessen |
|---|---|---|
| **Cents pro 24h** | > 0 in Phase 1, > 100 in Phase 3 | Audit-Log + Account-Balance-Diff |
| **Surveys completed / day** | > 1 in Phase 1 | Audit-Log `survey_completed` Events |
| **Disqualification rate** | < 30% | `disq` / `started` aus Telemetry |
| **Account-Bans / Monat** | 0 | Manuelles Check + Bridge-401-Errors |
| **Vision-Calls / Survey** | sinkend mit Optimierung | Telemetry per Run |
| **EUR pro Vision-Call** | > 0 sobald > 0 verdient wird | Cents/24h ÷ Vision-Calls/24h |

## 7. Wer entscheidet wann was?

- **Phasen-Gate** ist hart: keine Phase startet bevor die Vorphase ihre
  Akzeptanz-Kriterien erfüllt. Siehe Migrations-Roadmap.
- **Earnings-Smoke-Test** ist non-negotiable Phase 1 DoD. Ohne ihn ist der
  ganze Stack Theater.

## 8. Was dieses Dokument NICHT ist

Dies ist **kein** Marketing-Pitch. Wenn ein Punkt unangenehm ist, steht er
trotzdem drin. "Der Worker ist nicht profitabel" ist ein Fakt, kein Vorwurf.
"Puter ist NICHT die richtige Primary-Backend für einen headless Earnings-
Worker" ist ebenfalls ein Fakt — Begründung in
[`02-AI-BACKEND-STRATEGY.md`](./02-AI-BACKEND-STRATEGY.md).
