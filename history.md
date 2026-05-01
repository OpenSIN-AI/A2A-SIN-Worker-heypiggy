# history.md — Development History (Updated 2026-05-01)

## 2026-05-01: Archivierung + Cross-Reference

- **BRAIN.md**: 🚨 Archivierungs-Warnung + Verweis auf aktive Codebase in `stealth-runner`
- **Klarstellung**: Dieses Repo ist ARCHIVIERT. Alle aktiven Änderungen in `~/dev/stealth-runner/`
- **Aktives Modell**: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` (NICHT `meta/llama-3.2-11b-vision-instruct`)
- **LiveEye v7** mit Motion Detection, Frame-Differencing, Conv3D Optimierung, CRF Auto-Adjust

## 2026-05-01: SOTA Turnaround

**3 kritische Lücken geschlossen:**

1. **Cross-Repo Integration** — stealth-runner orchestriert jetzt alle 4 CLIs:
   - `runner/drivers/unmask.py`: DOM-Scan via unmask-cli
   - `runner/drivers/screen_follow.py`: Recording via screen-follow
   - `runner/state_machine.py`: Neuer DOM_PRESCAN State zwischen CAPTURE und VISION

2. **Vision-free Fast Path** — Answer-Router Confidence Gate ersetzt 60% der Vision-Calls:
   - `runner/dom_prescan.py`: DOM-Klassifikation mit Threshold 0.85
   - A2A `heypiggy_vision_worker.py` `_try_answer_router_fast_path()`: Router vor Vision
   - Kosteneinsparung: ~$2.70/Survey

3. **CreepJS CI Validation** — Stealth-Claims werden jetzt gemessen:
   - `playstealth-cli/scripts/stealth_benchmark.py`: CreepJS Score-Runner
   - `.github/workflows/stealth-bench.yml`: Wöchentlich + Push/PR, Gate 80%

**CEO Strategic Verdict:** `docs/CEO_STRATEGIC_VERDICT_2026-05-01.md` (444 Zeilen)

**7 SOTA-Pläne erstellt:** `docs/sota-plans/` mit GH Issues #168-#171 und SIN-CLIs/*#5,#75,#77

**Security-Breach dokumentiert:** `.env` mit HEYPIGGY_PASSWORD und NVIDIA_API_KEY im Git-Track. Fix geplant als SOTA-001.

## 2026-04-30: AXPress-Durchbruch

- Klick via `AXUIElementPerformAction(kAXPressAction)` funktioniert auf Chrome 148/macOS 26
- CGEventPostToPid ist TOT auf Chrome 148
- VoiceOver-Trick: 1× starten, AX-Tree bleibt dauerhaft aktiv

## 2026-04-28: Erster CEO-Audit

- docs/CEO-AUDIT.md erstellt
- docs/HARDENING-BACKLOG.md erstellt
- docs/ISSUE-VERIFICATION.md erstellt
- docs/RUNBOOK.md erstellt

## 2026-04-27: Anti-Learn/Learn Implementierung

- answer_history.py: Persistenter JSON-Store für Fehloptionen
- answer_router.py: `failed_options` + `ASK_VISION` auf wiederholte Fehler
- session_store.py: Persist/Restore von answer_history
