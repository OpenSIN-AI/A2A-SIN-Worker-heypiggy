# Migration Roadmap

> Phasen-basiert. Keine Phase startet bevor die Vorphase grün ist.

## Phase 0 — Stabilisierung (DIESER PASS)

**Status:** ✅ ausgeliefert.

- [x] CEO-Audit dokumentiert.
- [x] Issue-Verifikation für #80/#84/#85.
- [x] `answer_router.py` für Issue #81 mit Tests.
- [x] `SKIP_PREFLIGHT` echter fail-closed Modus (#85).
- [x] README ehrlich.
- [x] Hardening-Backlog priorisiert.
- [x] Plan-Dateien (00-04) committed.

## Phase 1 — Earnings-Smoke (BLOCKING)

**Ziel:** Beweis dass der Stack auf heypiggy.com Cents verdienen kann.

Voraussetzung: `docs/PLANS/03-EARNINGS-PROOF-PIPELINE.md` ToS-/Account-
Klärung erledigt.

### Sprint 1.1 — Telemetry-Baseline

- [ ] `scripts/earnings_telemetry.py` baut die 5 Frühindikatoren.
- [ ] `BUSINESS-STATE.md` als Single Source of Truth für "verdienen wir?".
- [ ] CI-Job `earnings-telemetry` aktualisiert das File täglich.

### Sprint 1.2 — Earnings Smoke

- [ ] Manueller `workflow_dispatch`-Job `earnings-smoke`.
- [ ] Replay-Bundle Artefakt.
- [ ] DoD: 5 grüne Runs in Folge.

### Sprint 1.3 — AI Gateway Primary

- [ ] `worker/ai/backend.py` live (nicht Skeleton).
- [ ] Alle Vision-Calls gehen über `AIGatewayBackend`.
- [ ] Telemetry pro Call: provider, model, latency, tokens.
- [ ] **Puter wird in dieser Phase NICHT integriert.**

**Phase-Gate:** 5 grüne Smoke-Runs + AI Gateway live + Telemetry-File aktuell.

## Phase 2 — Integration mit unmask + playstealth

**Ziel:** Der Worker hört auf, Browser-Logik selber zu machen.

Voraussetzung: Phase 1 Phase-Gate.

### Sprint 2.1 — unmask Client live

- [ ] `worker/integrations/unmask_client.py` als JSON-RPC-Client live.
- [ ] Compat-Smoke gegen gepinnte unmask-Version.
- [ ] Alle DOM-/Network-Reads aus dem Monolithen ersetzen.

### Sprint 2.2 — playstealth Client live

- [ ] `worker/integrations/playstealth_client.py` als Subprocess-Client live.
- [ ] Compat-Smoke gegen gepinnte playstealth-Version.
- [ ] Alle Browser-Klicks aus dem Monolithen ersetzen.

### Sprint 2.3 — Code-Diet

- [ ] `heypiggy_vision_worker.py` schrumpft auf ≤ 3 KLOC.
- [ ] Tote Module markiert / gelöscht.
- [ ] CHANGELOG dokumentiert die Migration sauber.

**Phase-Gate:** Worker enthält keinen direkten Playwright-Call mehr.
Smoke-Test bleibt grün.

## Phase 3 — Hardening + Skalierung

**Ziel:** Aus dem Smoke-Test ein produktives System machen.

Voraussetzung: Phase 2 Phase-Gate.

### Sprint 3.1 — Pre-existing Test-Fails (Backlog A4)

- [ ] `worker/context.py:147` `VisionState.freeze` TypeError.
- [ ] `tests/worker/test_cli.py` Bridge-Health-Mock.
- [ ] `tests/test_config.py` Infisical-Mock.
- [ ] `tests/worker/test_checkpoints.py` mtime-Test.

### Sprint 3.2 — Multi-Persona-Pool

- [ ] N Personas, dokumentierte Rotation, Account-Health-Tracking pro
      Persona.
- [ ] Cooldown nach Disqualify.

### Sprint 3.3 — Cost & Latency

- [ ] AI-Backend `gpt-oss` für non-vision Tasks.
- [ ] Vision-Caching (gleiche Frage in 24h → cached answer).
- [ ] Telemetry: EUR / completed survey.

### Sprint 3.4 — Optionaler Puter-Fallback

- [ ] Hinter Feature-Flag `AI_BACKEND_FALLBACK=puter`.
- [ ] Nur für non-vision-critical Tasks.
- [ ] Klar dokumentiert mit den Risiken aus Plan 02.

**Phase-Gate:** > 100 Cents / 24h, < 30% Disqualify-Rate, Test-Suite voll grün.

## Phase 4 — Produkt-Layer

**Ziel:** Vom Bot zum Produkt.

- [ ] Web-UI (Next.js) für Persona-Management und Earnings-Dashboard.
- [ ] **Hier** ist Puter sinnvoll: Web-UI mit `puter.auth` für End-User.
- [ ] Multi-Tenant-Mandanten-Trennung.
- [ ] Public Status-Page mit `BUSINESS-STATE.md` als Quelle.

## Phase 5 — Marktdifferenzierung

- [ ] Direct-Panel-Verträge (kein Vermittler).
- [ ] Eigene Survey-Quellen (B2B).
- [ ] White-Label für andere Survey-Plattformen.

## Was wir NICHT machen

- ❌ Big-Bang-Refactor.
- ❌ Phase 2 vor Phase 1.
- ❌ Marketing vor Phase 4.
- ❌ Mehr als 1 in-flight Phase gleichzeitig.
