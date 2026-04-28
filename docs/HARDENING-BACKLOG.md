# Hardening-Backlog

Dieser Backlog ist die **ehrliche** Liste der Dinge, die als "geschlossen"
markiert sind, aber aus Code-Sicht nicht vollstaendig erledigt sind, plus
neue Hardening-Aufgaben, die durch den CEO-Audit aufgedeckt wurden.

Das Dokument ersetzt die GitHub-Issues #63, #64, #65 nicht — es ergaenzt
sie durch die Wahrheit, die in der Issue-Schliessung verloren gegangen ist.

---

## Block A — Carry-over aus #63 / #64 / #65

### A1 · Ruff-Findings im Monolithen (Issue #63)

- **Symptom:** `ruff check heypiggy_vision_worker.py` liefert mehrere hundert
  Hinweise (lange Zeilen, fehlende Type-Hints, ungenutzte Variablen, schwache
  Exception-Handler).
- **Status:** GitHub-Issue ist `closed`. Code ist es nicht.
- **Schritt 1:** Auto-fix laufen lassen (`ruff check --fix`).
- **Schritt 2:** Verbleibende Hand-Aufgaben in Topic-Buckets schneiden
  (zu lange Zeilen, except-Bloecke, dead code).
- **Schritt 3:** CI-Gate: `ruff check` muss in `ci.yml` als blocking step
  laufen, nicht nur als Annotation.

### A2 · Mypy-Strict im Monolithen (Issue #64)

- **Symptom:** `mypy --strict heypiggy_vision_worker.py` liefert Hunderte
  Fehler. Das `worker/`-Paket ist strict; der Monolith nicht.
- **Status:** Teilweise erledigt (fuer das `worker/`-Paket).
- **Plan:**
  - Module aus dem Monolith schrittweise nach `worker/sections/` extrahieren
    (siehe CEO-AUDIT 4.2). Pro Extraktion gleich mypy-strict aktivieren.
  - Kein "Big-Bang-Mypy" auf den Monolithen — das fuehrt zu einer
    Megapatch-PR, die niemand reviewen kann.

### A3 · Security-Scans (Issue #65)

- **Bandit:** laeuft in CI. Mehrere Findings werden noch nicht als Fail
  gewertet. Aktion: schwere Findings (B-HIGH) als blocking. Mittelschwere
  als annotated.
- **pip-audit:** laeuft. Vulnerable Versions werden nicht automatisch
  upgegradet. Aktion: bei HIGH automatic Dependabot-PR.
- **detect-secrets:** Baseline existiert. Aktion: pre-commit hook ist da,
  CI-Gate fehlt — bitte ergaenzen.

### A4 · Test-Suite ist gruen — aber nicht ueberall

Stand 2026-04-28 nach dem Audit-Pass: `pytest tests/` liefert
**578 passed, 13 failed** (ohne `tests/integration`). Die 13 Fails sind
pre-existierend und haben nichts mit dem Audit-Pass zu tun:

- `tests/worker/test_context.py::test_freeze_blocks_late_mutation` und
  `tests/worker/test_loop.py::test_dry_run_does_not_touch_bridge`,
  `test_shutdown_before_start_raises` — alle drei: gleicher Bug in
  `worker/context.py:147` (`super().freeze()` schlaegt mit
  `TypeError: super(type, obj): obj must be an instance or subtype of type`
  fehl). Das ist ein Dataclass-/Slots-/Inheritance-Problem in
  `VisionState.freeze` und gehoert in einen kleinen, fokussierten Fix-PR.
- `tests/test_config.py::test_worker_env_loader_pulls_from_infisical_when_enabled`,
  `tests/test_e2e_smoke.py::TestInfisicalSmoke::*` — verlangen entweder
  `INFISICAL_TOKEN` oder einen funktionierenden Mock. Aktuell fallen sie
  in CI bewusst silent durch, weil keine Test-Credentials gesetzt sind.
- `tests/worker/test_cli.py::*` — fuenf Tests scheitern weil der CLI-Smoke
  einen Live-Bridge-Health-Check aufruft. Sollten auf `respx`/Mock umgestellt
  werden.
- `tests/worker/test_checkpoints.py::test_find_latest_checkpoint_returns_newest_fresh_checkpoint`
  — Zeit-Vergleich (`mtime`-Floor). Kleiner Fix oder klar als
  `freezegun`-Test umschreiben.

Wichtig: kein einziger dieser Fails liegt an `answer_router.py` oder den
Worker-Aenderungen aus dem Audit-Pass. Die Audit-Aenderungen wurden gegen
den vorhandenen Test-Bestand validiert (33 / 33 fuer den neuen Router,
20 / 20 fuer die relevanten Worker-Patterns wie `dashboard`, `cashout`,
`click_ref`, `preflight`, `router`).

**Aktion:** Diese 13 Fails als eigene, kleine Issues anlegen
(`fix: VisionState.freeze TypeError`, `chore: mock infisical for CI`,
`chore: mock bridge health for CLI tests`, `fix: checkpoint mtime test`).
Nicht als ein Mega-Fix-PR — das verschleiert die Diffs.

---

## Block B — Aus dem CEO-Audit

### B1 · Live-Canary-Run (Audit 4.1)

- **Aufgabe:** Manueller, beaufsichtigter Live-Run pro Tag, dokumentiert in
  `docs/canary/<datum>.md` mit Run-ID, finalem Exit-Reason, EUR-Wert,
  Fail-Klasse.
- **Erfolgskriterium:** 3 aufeinanderfolgende Tage mit EUR > 0.

### B2 · Schnellpfad ohne Vision (Audit 4.4)

- **Aufgabe:** Wenn der `answer_router` HIGH-Confidence + PERSONA_FACT |
  PRIOR_CONSISTENCY | ATTENTION_LITERAL liefert, **kein Vision-Call**.
  Stattdessen: direkt klicken, post-action DOM-Diff verifizieren, nur bei
  Diff-Failure auf Vision eskalieren.
- **Begruendung:** Direkter Hebel auf die Margen-Math (siehe Audit).
- **Wo einbauen:** an der einen Stelle in `heypiggy_vision_worker.py` wo
  vor jedem Step ein Screenshot an Vision geschickt wird; davor das
  Router-Resultat aus `answer_router.route_answer` pruefen.

### B3 · Monolith-Splittung Schritt 1 (Audit 4.2)

- **Aufgabe:** Sektionen 16–22 aus `heypiggy_vision_worker.py` in
  `worker/sections/<NN>_<name>.py` extrahieren. Reine Funktionen, keine
  globals.
- **Sektionen (laut Code-Kommentaren):**
  - 16 — PANEL-OVERRIDES
  - 17 — ATTENTION-CHECK AUTO-SOLVER
  - 18 — OPEN-ENDED MINIMUM-LENGTH ENFORCER
  - 19 — ERROR-BANNER RECOVERY
  - 20-22 — TBD (siehe Code)

### B4 · Doppelte Worker-Realitaet (Audit 4.3)

- **Aufgabe:** Entscheidung treffen, welcher Worker der "Owner" ist.
  Empfehlung: das `worker/`-Paket bleibt der CLI-Owner; der Monolith wird
  Bibliothek dahinter. Kein Code in `worker/` darf das Vorhandensein des
  Monolithen erzwingen — Cross-Imports nur in eine Richtung.

### B5 · Answer-Router-Wiring (Issue #81 Followup)

- **Status nach diesem Commit:** `answer_router.py` ist erstellt + getestet,
  aber noch NICHT in den `dom_prescan`/Vision-Prompt-Pfad geleitet. Das ist
  Absicht — erst CI gruen, dann Wiring.
- **Aufgabe:** in `heypiggy_vision_worker.py` Sektion 16 (oder neue Sektion
  16b) den Aufruf
  `decision = answer_router.route_answer(...)` einfuegen, das Ergebnis als
  `as_prompt_block()` an den Vision-Prompt anhaengen, und bei
  `decision.strategy != ASK_VISION` Vision **uebersteuern**.

### B6 · SKIP_PREFLIGHT-Tests

- Regressions-Test schreiben:
  - `SKIP_PREFLIGHT=1` ohne `WORKER_ENV` ODER `WORKER_ALLOW_PREFLIGHT_SKIP`
    → Preflight LAEUFT (skip wird ignoriert).
  - `SKIP_PREFLIGHT=1` mit `WORKER_ENV=development` → Preflight wird
    uebersprungen.

### B7 · README ehrlich machen

- "99,9% Erfolgsrate" entfernt. Real ist: keine Live-Daten.
- "Durchschnittliche Latenz <500ms" — real sind 1-3 s pro Vision-Call.
  Mit dem Schnellpfad (B2) wird das wieder erreichbar.

---

## Wer abarbeitet, was wann

Reihenfolge nach Hebel auf Geld-Output:

1. B1 (Canary) — sofort, jeden Tag.
2. B2 (Schnellpfad) — direkt nach erstem Canary-Erfolg.
3. B5 (Router-Wiring) — Voraussetzung fuer B2.
4. A1 (Ruff Auto-Fix) — kann parallel laufen.
5. B3 (Monolith Schritt 1) — nach erstem Canary-Erfolg, nicht davor.
6. B4 (Worker-Owner-Entscheidung) — Architektur-Diskussion eine Iteration
   spaeter.
7. A2 / A3 — laufend, nicht als Sprint-Block.

---

*Dieser Backlog ist lebendig. Wer eine Zeile abarbeitet, traegt Datum und
Resultat hier ein. Issue-Closure ohne Eintrag in diesem Dokument ist
nicht zulaessig.*
