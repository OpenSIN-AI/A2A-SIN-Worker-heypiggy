# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added (Answer-History & Anti-Learn Pass, 2026-04-30)

- **`answer_history.py`** — persistenter JSON-Store für erfolgreiche und fehlgeschlagene Antworten.
- **`answer_router.py`** — berücksichtigt jetzt `failed_options` und vermeidet bekannte Fehlpfade; bei Wiederholung schaltet das Routing auf Vision-Review.
- **`heypiggy_vision_worker.py`** — schreibt Learn-/Anti-Learn-Ergebnisse in die History zurück.
- **`session_store.py`** — Session-Cache speichert und restauriert `answer_history` mit.
- **`tests/test_answer_history.py`**, **`tests/test_answer_router.py`**, **`tests/test_session_store.py`** — Regression-Coverage für Anti-Learn und Persistenz.

### Changed

- **Semver bump to `2.1.0`** — neue Learn-/Anti-Learn-Persistenz ist eine backward-compatible Feature-Erweiterung.

### Added (Strategy Reset Pass, 2026-04-28)

- **`docs/PLANS/00-NORTHSTAR.md`** — strategische Nordstern-Doku.
  Architektur-Vision, Verantwortlichkeitsmatrix mit
  [SIN-CLIs/unmask-cli](https://github.com/SIN-CLIs/unmask-cli) und
  [SIN-CLIs/playstealth-cli](https://github.com/SIN-CLIs/playstealth-cli).
- **`docs/PLANS/01-INTEGRATION-UNMASK-PLAYSTEALTH.md`** — verbindlicher
  Integrations-Plan gegen die zwei Schwester-CLIs (JSON-RPC für unmask,
  Subprocess für playstealth).
- **`docs/PLANS/02-AI-BACKEND-STRATEGY.md`** — ehrliche Bewertung
  Vercel AI Gateway (primary) vs. Puter (optionaler Fallback). **Nein,
  Puter ist nicht der richtige Primary-Backend für einen headless Earnings-
  Worker** — Begründung mit Quellen.
- **`docs/PLANS/03-EARNINGS-PROOF-PIPELINE.md`** — der Geld-Pfad. Solange
  der nicht reproduzierbar grün ist, ist alles andere Theater.
- **`docs/PLANS/04-MIGRATION-ROADMAP.md`** — Phasen 0-5 mit harten
  Phase-Gates.
- **`docs/ISSUES-TO-CREATE.md`** — Copy-paste-fertige Issue-Templates für
  fünf EPICs (E1 Earnings, E2 Integration, E3 AI-Backend, E4 Pre-existing
  Test-Fails, E5 Productization) plus Cross-Repo-Issues gegen unmask + playstealth.
- **`worker/integrations/__init__.py`** — neues Adapter-Paket.
- **`worker/integrations/unmask_client.py`** — Async JSON-RPC 2.0 Client
  Skeleton für unmask-cli. Strikt typisierte `UnmaskResponse`-Parser,
  abstrakter Transport-Layer (stdio / HTTP+WS), JSON-RPC-Envelope-
  Validator. Bodies der RPC-Calls sind Phase 2 — die Surface ist heute
  vertraglich gepinnt.
- **`worker/integrations/playstealth_client.py`** — Subprocess-Client-
  Skeleton für playstealth-cli. Exit-Code-Klassifikation, atomar gelesener
  State-File, Argument-Validation greift heute schon.
- **`worker/ai/__init__.py`**, **`worker/ai/backend.py`** — AI-Backend-
  Selektor mit `AIGatewayBackend` (primary) und `PuterFallbackBackend`
  (optional). Selektor verweigert Vision-Calls über den Puter-Fallback.
- **`tests/test_integrations_skeletons.py`** — 36 Contract-Tests für die
  drei Skeletons. Alle grün.

### Added (Audit + Answer-Loop Pass, 2026-04-28)

- **`answer_router.py`** — neuer **provider-aware Question Router** (Issue #81).
  Erkennt Fragetyp (single/multi/likert/grid/numeric/openend/screener/attention/
  consistency_trap), wählt eine Strategie unter Berücksichtigung von Panel
  (Cint/Lucid/Dynata/PureSpectrum/Sapio) und Persona, und produziert einen
  kompakten Prompt-Block mit harten DO/DONT-Regeln. Wird im Worker direkt
  nach `panel_overrides.detect_panel()` aufgerufen und in das Vision-Prompt
  als `router_block` injiziert. Trap-Erkennung (Konsistenz, Attention,
  unmögliche Behauptungen) ist eingebaut. Volle Test-Coverage in
  `tests/test_answer_router.py`.
- **`docs/CEO-AUDIT.md`** — ungeschönte CEO-Bewertung von Funktionalität,
  UX, Innovation, Wettbewerb, Marktreife, Top-Risiken und Geschäftsmodell-
  Realität. Keine Schönfärberei.
- **`docs/ISSUE-VERIFICATION.md`** — Code-basierte Verifikation, ob die
  zuletzt geschlossenen Issues #80, #84, #85 wirklich umgesetzt sind oder
  nur cosmetic geschlossen wurden. Mit Datei + Zeilenangaben.
- **`docs/RUNBOOK.md`** — Operations-Runbook (Preflight, Bypass-Regeln,
  Triage-Pfade, Verifikations-Checks).
- **`docs/HARDENING-BACKLOG.md`** — priorisierter SOTA-Backlog mit harten
  Akzeptanz-Kriterien.

### Changed (Audit + Answer-Loop Pass, 2026-04-28)

- **`heypiggy_vision_worker.py` — `SKIP_PREFLIGHT` echter fail-closed Modus
  (Issue #85).** Ein bloßes `SKIP_PREFLIGHT=1` reicht nicht mehr aus, um den
  Vision-Auth-Preflight zu umgehen. Es wird zusätzlich `WORKER_ENV` aus
  `{dev, development, test, ci}` ODER ein explizites
  `WORKER_ALLOW_PREFLIGHT_SKIP=1` verlangt. In allen anderen Fällen wird das
  Skip ignoriert und im Audit-Log mit `worker_env` markiert.
- **`README.md`** — Marketing-Bullshit raus. Statt "99.9% Erfolgsrate" steht
  jetzt eine ehrliche Status-Zusammenfassung mit Verlinkung auf den CEO-
  Audit, die Issue-Verifikation und den Hardening-Backlog. Feature-Tabelle
  beschreibt was wirklich existiert.

### Changed

- **Hardened `worker/` package** — consumed external feedback and tightened typing + docs:
  - `worker.cli` now has proper `BoundLogger` typing throughout (no more `log: object` +
    `# type: ignore[attr-defined]` soup) and uses `log.exception(...)` in the
    top-level except-blocks so stack traces are preserved in structured logs.
  - `worker.shutdown` replaced two runtime `assert self._loop is not None`
    invariants with explicit `RuntimeError` checks — assertions get stripped
    under `python -O`, which would silently corrupt state.
  - `worker.retry` now guarantees that `asyncio.CancelledError`,
    `KeyboardInterrupt` and `SystemExit` are **never** retried, even if the
    caller passes `retry_on=(BaseException,)`. Retrying a cancelled task
    would deadlock the event loop; retrying a SIGINT would swallow it.
  - `worker.__init__` exports the full public API (`run_worker`,
    `RetryPolicy`, `AuditLogger`, `ShutdownController`, every exception
    class, `configure_logging`, `get_logger`).
- **LICENSE** and **SECURITY.md** are no longer empty — MIT license text
  is present, and `SECURITY.md` documents a complete coordinated
  vulnerability disclosure policy (scope, channels, response targets,
  hardening baseline).
- **README.md** quick-start uses the new `heypiggy-worker` CLI, the
  Python-support badge reflects the real 3.11 / 3.12 / 3.13 support
  matrix, and a `Development` + `Exit Codes` section was added.
- **Dockerfile** — OCI image labels added, `PYTHONHASHSEED=random` set in
  runtime stage, and the brittle `pip install --no-deps || fallback`
  pattern replaced by a single dependency-resolving install that fails
  loudly on real errors.
- **GitHub Actions `ci.yml`** — `bandit` now runs in the lint job, JUnit
  artefacts are uploaded per matrix entry, and `ruff` emits GitHub
  annotations.
- **`.gitignore`** — added `!.pcpm/sessions/**` override so the session
  summaries ship with the repo (previously the blanket `sessions/` rule
  matched them).

### Added

- `tests/worker/test_public_api.py` — guards the top-level re-export
  surface (`__all__` shape, sortedness, semver-shaped version, star-import
  coverage).
- Additional `tests/worker/test_retry.py` cases for the new
  cancellation-safety guarantees (CancelledError, KeyboardInterrupt,
  SystemExit).
- Additional `tests/worker/test_shutdown.py` cases for safe restore
  before `__aenter__` and the programmer-error path when `_install_handlers`
  runs without an active context.

### Added

- New `worker/` package with typed, strict-mypy modules:
  - `worker.context` — `WorkerContext` DI container (replaces 32+ module globals).
  - `worker.logging` — `structlog`-based JSON logs with run-id correlation and secret redaction.
  - `worker.audit` — append-only JSONL audit log for compliance.
  - `worker.exceptions` — explicit error hierarchy (no more bare `except Exception`).
  - `worker.retry` — dependency-free async retry decorator with jitter.
  - `worker.shutdown` — cooperative SIGTERM/SIGINT handler with double-tap hard-exit.
  - `worker.telemetry` — optional OpenTelemetry tracing (opt-in via `OTEL_ENABLED`).
  - `worker.cli` — new `heypiggy-worker` console script (`run`, `doctor`, `version`).
  - `worker.loop` — orchestrator that wraps the legacy coroutine with preflight + audit + shutdown.
- `python -m worker` entry point.
- `.env.example` with every supported environment variable documented.
- `CHANGELOG.md` (this file).
- GitHub Actions: `ci.yml` (lint + mypy + pytest matrix + Docker build), `security.yml`
  (bandit, pip-audit, detect-secrets).
- `dependabot.yml` for pip, GitHub Actions, and Docker.
- PR template + structured issue forms (bug, feature).
- `.pre-commit-config.yaml`, `.editorconfig`.

### Changed

- **Breaking (container):** Dockerfile rewritten from a broken Node.js base to a
  hardened Python 3.13 multi-stage image with non-root user, `tini` PID 1 and
  an import-based HEALTHCHECK.
- `.gitignore` expanded to cover Python, coverage, IDE and runtime artefact noise.
- `.dockerignore` added to keep the build context small.
- `README.md` left untouched in content but now matches the new CI badge target.

### Security

- Pre-commit hooks (`.githooks/`) block secret leaks and external-source references.
- Runtime container drops to a dedicated unprivileged user (`app`, UID 10001).
- `detect-secrets` baseline scanned on every push + PR.

## [2.0.0] — initial public baseline

First public release of the HeyPiggy Vision Worker as part of the OpenSIN-AI
A2A ecosystem. Vision-gate loop, NVIDIA fail analysis, self-healing memory,
circuit breaker, typed config and Ring-Buffer recorder.

[Unreleased]: https://github.com/OpenSIN-AI/A2A-SIN-Worker-heypiggy/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/OpenSIN-AI/A2A-SIN-Worker-heypiggy/releases/tag/v2.0.0
