# Integration Plan — unmask-cli + playstealth-cli

> Verbindlich gegen `SIN-CLIs/unmask-cli@main` und
> `SIN-CLIs/playstealth-cli@main`, Stand 2026-04-28.

## 1. Wer macht was

| Frage | Wer antwortet |
|---|---|
| "Was ist auf der Seite?" | **unmask-cli** via JSON-RPC: DOM scan, network, console, selfHeal Selektoren, optional `act/extract/observe`. |
| "Wie klicke ich, ohne dass das Panel mich erkennt?" | **playstealth-cli** als Python-Subprocess: `click-survey`, `answer-survey`, human-input Rhythmen, Persona-Bindung, Anti-Detect. |
| "Welche Antwort gebe ich?" | **dieser Worker** über `answer_router.py` + `panel_overrides.py` + `persona.py`. |
| "Habe ich verdient? Wann auszahlen?" | **dieser Worker** via `survey_orchestrator.py` + heypiggy-API. |

Der Worker macht NIE selbst einen Playwright-Aufruf. Wenn er es heute tut, ist
das Migrations-Schuld und gehört auf einen der zwei CLIs umgeleitet.

## 2. Schnittstellen (verbindlich)

### 2.1 unmask-cli — JSON-RPC

unmask exponiert eine JSON-RPC 2.0-Surface, die wir bevorzugt über `stdio`
ansprechen (kein offener TCP-Port nötig):

```bash
unmask serve            # stdio default
# Methoden (Auszug, siehe src/ipc/dispatch.ts in unmask-cli):
#   unmask.inspect          { url, opts? }      -> UnmaskResponse
#   unmask.network.attach   { sessionId }       -> ok
#   unmask.dom.scan         { sessionId }       -> Element[]
#   unmask.console.tail     { sessionId }       -> ConsoleEvent[]
#   unmask.selfHeal         { sessionId, hint } -> Locator
#   llm.act                 { sessionId, instr }-> ActResult
#   llm.extract             { sessionId, schema}-> object
#   llm.observe             { sessionId, query }-> Candidate[]
#   queue.add / queue.run / queue.list / queue.blacklist
```

Schreiblücken (TODO an unmask):
- klare semver-Versionierung der RPC-Surface (siehe Issue-Vorlage **U-1**).
- ein RPC-Methoden-Dump per `--dump-rpc-schema` (Issue **U-2**) damit unser
  Python-Client typed gegen ein JSON-Schema-File bauen kann.

### 2.2 playstealth-cli — Subprocess

playstealth ist eine Python-CLI mit Tool-Registry. Wir rufen sie als
Subprocess auf und konsumieren den **Manifest- und State-Output**:

```bash
playstealth open-list
playstealth click-survey --index 0
playstealth inspect-survey --index 0
playstealth answer-survey --index 0 --option-index 0
playstealth run-survey   --index 0 --max-steps 5
playstealth resume-survey --max-steps 5
playstealth manifest                # JSON tool manifest
playstealth state                   # current persistent state
playstealth diagnose inspect-page
```

Stdout: kompakter Status. Artefakte: per `PLAYSTEALTH_ARTIFACTS_DIR`. State:
per `PLAYSTEALTH_STATE_PATH` als atomic JSON.

Schreiblücken (TODO an playstealth):
- ein einheitliches `--json` Flag pro Befehl (Issue **P-1**) damit der Worker
  nicht stdout parsen muss.
- Exit-Code-Konvention: 0 = ok, 64 = soft-fail (resumable), 65 = hard-fail
  (manual intervention) (Issue **P-2**).
- ein `playstealth events --follow` Streaming-Endpunkt (NDJSON) für
  Real-time Telemetry (Issue **P-3**).

## 3. Worker-Side Integration Skeleton

Wir bauen heute nur **Skeleton-Clients** und schreiben den Wechsel auf
unmask/playstealth in der Roadmap fest. Big-Bang-Migration ist explizit nicht
das Ziel.

```
worker/
├── integrations/
│   ├── __init__.py
│   ├── unmask_client.py        # Async JSON-RPC client (NEU, Skeleton)
│   └── playstealth_client.py   # Subprocess client (NEU, Skeleton)
└── ai/
    ├── __init__.py
    └── backend.py              # AI-Backend selector (NEU, Skeleton)
```

Die Skeleton-Module sind so geschnitten, dass ein klarer Phase-2-PR sie gegen
den heute live laufenden Bridge-Stack tauschen kann, ohne den Loop anzufassen.

## 4. Daten-Fluss (Single Survey Run, Ziel-Zustand)

```
worker.loop.run_once()
  │
  ├─► playstealth.open_list()                      (subprocess)
  │     └─► returns survey-list snapshot
  ├─► survey_orchestrator.pick_next(snapshot)      (worker)
  ├─► playstealth.click_survey(idx)                (subprocess)
  │     └─► opens new tab, returns tab-id + state
  ├─► unmask.inspect(tab-url)                      (JSON-RPC)
  │     └─► returns DOM + network + console snapshot
  ├─► panel_overrides.detect_panel(snapshot)       (worker)
  ├─► answer_router.route_answer(question, panel)  (worker)
  ├─► ai.backend.call(prompt + snapshot)           (AI Gateway)
  │     └─► returns answer decision
  ├─► playstealth.answer_survey(idx, decision)     (subprocess)
  ├─► loop until terminal state                    (worker)
  └─► survey_orchestrator.record_outcome()         (worker)
```

Jede dieser Stufen ist heute im Monolithen `heypiggy_vision_worker.py`
verklebt. Phase 2 zerschneidet sie an genau diesen Stellen.

## 5. Risiken und wie wir sie absichern

| Risiko | Gegenmaßnahme |
|---|---|
| unmask RPC-Surface ändert sich silently | Wir pinnen unmask auf eine Version (`requirements.txt` oder `package.json` für die JS-Brücke) und haben einen Smoke-Test der bei jedem CI-Run `unmask doctor` + `unmask serve --dump-rpc-schema` ausführt und gegen ein eingecheckes Schema diff't. |
| playstealth CLI-Output bricht | `--json`-Flag erzwingen (Issue **P-1**) sobald playstealth es anbietet. Bis dahin: schmaler stdout-Parser mit Snapshot-Tests gegen festgelegte Output-Versionen. |
| Zwei Browser-Instanzen (unmask startet seinen, playstealth seinen) | **Bewusste Trennung in Phase 2.** Phase 3 fusioniert auf einen geteilten CDP-Endpoint. Bis dahin nehmen wir den Overhead in Kauf — Korrektheit > Performance. |
| Versionsdrift zwischen den drei Repos | Ein gemeinsames `compatibility.json` in diesem Repo das die getesteten Versionen pinnt. CI cached `unmask --version` und `playstealth --version` und failt bei Drift. |

## 6. Definition of Done für die Integration

- [ ] `worker/integrations/unmask_client.py` ist live (nicht Skeleton) und alle
      DOM/Network-Reads im Loop gehen über ihn.
- [ ] `worker/integrations/playstealth_client.py` ist live und alle Klicks
      gehen über ihn.
- [ ] `heypiggy_vision_worker.py` enthält keine direkten Playwright-Calls mehr.
- [ ] CI hat einen "compat-smoke"-Job der die drei Repos in ihren gepinnten
      Versionen gegeneinander testet.
- [ ] `docs/RUNBOOK.md` dokumentiert wie man die drei Komponenten lokal startet.
