# Issues to create — copy/paste-ready

> **Wichtig:** mein gh-Sandbox-Token ist auf diesem Repo **read-only**. Ich
> kann keine Issues programmatisch öffnen. Diese Datei ist 1:1 in GitHub
> einkopierbar (oder mit `gh issue create` als Skript ausführbar — siehe
> Abschnitt am Ende).

Issue-Nummerierung hier ist intern. GitHub vergibt eigene Nummern.

---

## EPIC E1 — Earnings-Proof Pipeline (BLOCKING — alles andere wartet darauf)

**Title:** `EPIC: Earnings-Proof Pipeline (Phase 1, blocking)`

**Body:**

Wir können heute nicht beweisen, dass der Worker auf heypiggy.com auch nur
einen Cent verdient. Bevor wir an Refactor / Integration / UI denken, muss
genau das beweisbar werden.

Verbindlicher Plan: [`docs/PLANS/03-EARNINGS-PROOF-PIPELINE.md`](../docs/PLANS/03-EARNINGS-PROOF-PIPELINE.md)

### Sub-Issues

- [ ] E1-1 ToS-Klarheit: welche Panels (Cint/Lucid/Dynata/PureSpectrum/Sapio)
      bedient heypiggy, und welche tolerieren Automation? Schriftliche
      Antwort.
- [ ] E1-2 Account-Strategie schriftlich fixiert (Single / Multi / Sandbox).
- [ ] E1-3 `scripts/earnings_telemetry.py` — 5 Frühindikatoren aus dem
      Audit-Log.
- [ ] E1-4 `BUSINESS-STATE.md` — Single Source of Truth, täglich autoupdated.
- [ ] E1-5 CI-Job `earnings-smoke` (workflow_dispatch) mit Replay-Bundle.
- [ ] E1-6 Acceptance: 5 grüne Smoke-Runs in Folge.

**Labels:** `epic`, `earnings`, `blocking`, `phase-1`

---

## EPIC E2 — Integration mit unmask-cli + playstealth-cli

**Title:** `EPIC: Replace in-tree browser logic with unmask-cli + playstealth-cli`

**Body:**

Der Worker re-implementiert heute Browser-Logik die in
[`SIN-CLIs/unmask-cli`](https://github.com/SIN-CLIs/unmask-cli) und
[`SIN-CLIs/playstealth-cli`](https://github.com/SIN-CLIs/playstealth-cli)
bereits sauber, getestet und MIT-licensed verfügbar ist.

Verbindlicher Plan: [`docs/PLANS/01-INTEGRATION-UNMASK-PLAYSTEALTH.md`](../docs/PLANS/01-INTEGRATION-UNMASK-PLAYSTEALTH.md)

**Voraussetzung:** EPIC E1 grün.

### Sub-Issues

- [ ] E2-1 `worker/integrations/unmask_client.py` — Skeleton ist im Repo
      (siehe diese PR-Serie); jetzt live verkabeln gegen unmask `serve`.
- [ ] E2-2 `worker/integrations/playstealth_client.py` — Skeleton ist im
      Repo; jetzt live als Subprocess-Adapter.
- [ ] E2-3 `compatibility.json` mit gepinnten unmask + playstealth Versionen.
- [ ] E2-4 CI-Job `compat-smoke` der die drei Repos in ihren gepinnten
      Versionen gegeneinander testet.
- [ ] E2-5 `heypiggy_vision_worker.py` shrink: ≤ 3 KLOC.
- [ ] E2-6 Tote Module markieren / löschen.

**Labels:** `epic`, `integration`, `phase-2`

---

## EPIC E3 — AI Backend Strategy

**Title:** `EPIC: Vercel AI Gateway primary, Puter optional fallback`

**Body:**

Klärung der AI-Backend-Frage. **Puter ist NICHT der richtige Primary-Backend**
für einen headless Earnings-Worker. Begründung mit Quellen:
[`docs/PLANS/02-AI-BACKEND-STRATEGY.md`](../docs/PLANS/02-AI-BACKEND-STRATEGY.md)

### Sub-Issues

- [ ] E3-1 `worker/ai/backend.py` — Skeleton ist im Repo; jetzt
      `AIGatewayBackend` als konkrete Implementierung.
- [ ] E3-2 Telemetrie pro Vision-Call: provider, model, latency, tokens.
- [ ] E3-3 Cost-Lane: `openai/gpt-oss-120b` für non-vision-Tasks.
- [ ] E3-4 Vision-Caching (gleiche Frage in 24h → cached answer).
- [ ] E3-5 (Phase 3) Optionaler Puter-Fallback hinter Feature-Flag,
      ausschließlich für non-critical text tasks.

**Labels:** `epic`, `ai`, `phase-1`

---

## EPIC E4 — Pre-existing Test Failures (Hardening A4)

**Title:** `EPIC: Fix 13 pre-existing test failures from before Audit Pass`

**Body:**

Aus dem Audit-Pass (siehe `docs/HARDENING-BACKLOG.md` Abschnitt A4):
**578 passed, 13 failed**. Keiner dieser Fails wurde durch den Audit-Pass
verursacht — sie waren vorher schon rot. Sie sind aber peinlich und müssen
einzeln gefixt werden, nicht als ein Mega-Fix-PR.

### Sub-Issues

- [ ] E4-1 `worker/context.py:147` — `VisionState.freeze` `TypeError: super(...)`. Drei betroffene Tests: `test_freeze_blocks_late_mutation`, `test_dry_run_does_not_touch_bridge`, `test_shutdown_before_start_raises`.
- [ ] E4-2 `tests/test_config.py::test_worker_env_loader_pulls_from_infisical_when_enabled` + `tests/test_e2e_smoke.py::TestInfisicalSmoke::*` — Infisical mocken statt Live-Token zu erwarten.
- [ ] E4-3 `tests/worker/test_cli.py` (5 Tests) — Bridge-Health auf `respx`/Mock umstellen statt Live-Call.
- [ ] E4-4 `tests/worker/test_checkpoints.py::test_find_latest_checkpoint_returns_newest_fresh_checkpoint` — `mtime`-Vergleich mit `freezegun` deterministisch machen.

**Labels:** `epic`, `tests`, `hardening`

---

## EPIC E5 — Productization Layer (späte Phase)

**Title:** `EPIC: Web-UI + multi-tenant + public status page`

**Body:**

Erst nach E1-E4 grün. Plan: `docs/PLANS/04-MIGRATION-ROADMAP.md` Phase 4.

### Sub-Issues

- [ ] E5-1 Web-UI (Next.js) — Persona-Management + Earnings-Dashboard.
- [ ] E5-2 Hier passt Puter `puter.auth` für End-User-Login (genau die
      Stelle wo "User-Pays" tatsächlich funktioniert).
- [ ] E5-3 Multi-Tenant-Trennung.
- [ ] E5-4 Public Status-Page mit `BUSINESS-STATE.md` als Quelle.

**Labels:** `epic`, `productization`, `phase-4`

---

## Cross-Repo Issues — gegen `SIN-CLIs/unmask-cli`

**Title:** `feat: typed RPC schema dump (--dump-rpc-schema)`

**Body:** unmask soll seine JSON-RPC-Surface als JSON-Schema dumpen können,
damit Konsumenten (heypiggy worker) typed clients bauen können ohne aus
dem TS-Code zu raten.

**Title:** `feat: stable semver for IPC dispatch surface`

**Body:** Dispatch-Methoden brauchen semver-Garantien sobald > 1.0. Heute
ist drift möglich.

---

## Cross-Repo Issues — gegen `SIN-CLIs/playstealth-cli`

**Title:** `feat: --json flag per command`

**Body:** Subprocess-Konsumenten müssen heute stdout-text parsen. Wir
brauchen `--json` pro Command für deterministisches Konsumieren.

**Title:** `feat: defined exit codes (0 ok / 64 soft-fail / 65 hard-fail)`

**Body:** Aktuell schwer aus dem Subprocess heraus zu klassifizieren ob ein
Run resumable ist oder eine manuelle Intervention braucht.

**Title:** `feat: streaming events endpoint (NDJSON)`

**Body:** `playstealth events --follow` für real-time Telemetry an den
Worker.

---

## Anhang — Skript um die Issues automatisch zu öffnen

Sobald du einen Token mit `Contents: write` + `Issues: write` Scope hast:

```bash
# Auf eigene Verantwortung ausführen.
gh issue create --repo OpenSIN-AI/A2A-SIN-Worker-heypiggy \
  --title "EPIC: Earnings-Proof Pipeline (Phase 1, blocking)" \
  --body-file - <<'EOF'
... (Body aus diesem File kopieren)
EOF
```

Das gleiche für die anderen Epics. Die Cross-Repo-Issues gehen analog gegen
`SIN-CLIs/unmask-cli` bzw. `SIN-CLIs/playstealth-cli`.
