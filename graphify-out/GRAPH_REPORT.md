# Graph Report - A2A-SIN-Worker-heypiggy  (2026-05-01)

## Corpus Check
- 152 files · ~175,438 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2625 nodes · 7524 edges · 91 communities detected
- Extraction: 44% EXTRACTED · 56% INFERRED · 0% AMBIGUOUS · INFERRED: 4220 edges (avg confidence: 0.57)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 86|Community 86]]
- [[_COMMUNITY_Community 87|Community 87]]
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 96|Community 96]]
- [[_COMMUNITY_Community 98|Community 98]]
- [[_COMMUNITY_Community 99|Community 99]]
- [[_COMMUNITY_Community 101|Community 101]]
- [[_COMMUNITY_Community 103|Community 103]]
- [[_COMMUNITY_Community 104|Community 104]]
- [[_COMMUNITY_Community 105|Community 105]]
- [[_COMMUNITY_Community 106|Community 106]]
- [[_COMMUNITY_Community 107|Community 107]]
- [[_COMMUNITY_Community 108|Community 108]]

## God Nodes (most connected - your core abstractions)
1. `RunSummary` - 241 edges
2. `ScreenRingRecorder` - 225 edges
3. `GlobalBrainClient` - 206 edges
4. `CircuitBreaker` - 202 edges
5. `DriverType` - 201 edges
6. `SurveyOrchestrator` - 188 edges
7. `BrowserDriver` - 178 edges
8. `MediaRouter` - 176 edges
9. `AnswerLog` - 174 edges
10. `Persona` - 169 edges

## Surprising Connections (you probably didn't know these)
- `MediaRouter` --calls--> `router()`  [INFERRED]
  media_router.py → tests/test_media_router.py
- `OpenSIN Global Brain policy helpers.  WHY: Agents must never leave env/secret st` --uses--> `GlobalBrainClient`  [INFERRED]
  global_brain_policy.py → global_brain_client.py
- `Extended metadata for secret rotation tracking.      WHY: Secrets need lifecycle` --uses--> `GlobalBrainClient`  [INFERRED]
  global_brain_policy.py → global_brain_client.py
- `Normalize env keys to the canonical secret-name form.` --uses--> `GlobalBrainClient`  [INFERRED]
  global_brain_policy.py → global_brain_client.py
- `Classify a key so policy facts can distinguish env config from secrets.      WHY` --uses--> `GlobalBrainClient`  [INFERRED]
  global_brain_policy.py → global_brain_client.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (208): BudgetGuard, Verwaltet Limits und Counter fuer einen Worker-Run.      Usage:         guard =, True wenn eines der Budgets ueberschritten ist., Bisheriger Verbrauch in EUR (geschaetzt)., Serialisierbarer Snapshot fuer run_summary.json., CircuitBreaker, Setzt den Circuit Breaker komplett zurück.         WHY: Für Tests und manuelle R, Gibt den aktuellen Status als Dict zurück (für Logging/Monitoring).         WHY: (+200 more)

### Community 1 - "Community 1"
Cohesion: 0.02
Nodes (146): Gesamt-Konfiguration für den HeyPiggy Vision Worker.     WHY: Einzelner Entry-Po, WorkerConfig, AuditLogger, JSONL audit-log sink.      Instances are cheap to construct and reusable across, Append a single audit record. Never raises., _bridge_adapter_mode(), _build_parser(), _is_truthy() (+138 more)

### Community 2 - "Community 2"
Cohesion: 0.03
Nodes (82): BridgeDriver, ClickResult, create_driver(), _env_int(), JavascriptResult, NodriverDriver, PlaywrightDriver, Unified DOM snapshot result. (+74 more)

### Community 3 - "Community 3"
Cohesion: 0.03
Nodes (153): Meldet einen erfolgreichen API-Call.         WHY: Bei Erfolg im HALF_OPEN-State, build_brain_prompt_block(), Pingt den Daemon — cached das Ergebnis fuer die Session., Verbindet sich mit dem Brain und holt den initialen Kontext.          Fallback:, Liest den letzten synchronisierten Kontext aus .pcpm/., Fragt das Brain nach einem Kontext-Snippet fuer query.          Returns den Answ, Signalisiert dem Brain dass die Run-Session beendet ist., Verdichtet den PrimeContext in einen kompakten Prompt-Block.      WHY: Wir wolle (+145 more)

### Community 4 - "Community 4"
Cohesion: 0.02
Nodes (106): _bridge_mode(), BridgeAdapterConfig, configure_adapter(), ContractMismatchError, _is_truthy(), make_stack(), make_stack_async(), _normalize_error_codes() (+98 more)

### Community 5 - "Community 5"
Cohesion: 0.03
Nodes (84): ABC, AIBackend, AIBackendError, AIBackendSelector, AICallResult, AICapability, AIGatewayBackend, PuterFallbackBackend (+76 more)

### Community 6 - "Community 6"
Cohesion: 0.03
Nodes (104): artifact_dir(), ArtifactConfig, BridgeConfig, ensure_infisical_env_loaded(), ensure_saved_env_loaded(), ensure_worker_env_loaded(), InfisicalConfig, _is_truthy() (+96 more)

### Community 7 - "Community 7"
Cohesion: 0.02
Nodes (31): DummyGate, HeyPiggyActionLoopDetectorTests, HeyPiggyFailLearningMemoryTests, HeyPiggyFailReplayIntegrationTests, HeyPiggyFinalizeWorkerRunTests, HeyPiggyProfileAutofillTests, HeyPiggyVisionCacheTests, HeyPiggyVisionProbeTests (+23 more)

### Community 8 - "Community 8"
Cohesion: 0.03
Nodes (60): AnswerDecision, _best_option_match(), build_router_prompt_block(), classify_question(), Confidence, _extract_attention_target(), _is_date_question(), _is_multi_select_text() (+52 more)

### Community 9 - "Community 9"
Cohesion: 0.03
Nodes (86): AudioTranscript, _average_confidence(), _download_audio(), _estimate_duration_seconds(), _guess_mime_from_suffix(), _mime_to_suffix(), Lädt Audio von `audio_url`, schickt es an NVIDIA NIM und gibt Transcript zurück., Lädt Audio von http(s), data: oder file: URL. Begrenzt auf max_bytes.     WHY: A (+78 more)

### Community 10 - "Community 10"
Cohesion: 0.05
Nodes (44): call_with_retry(), classify_result(), _extract_error_text(), _main(), Klassifiziert ein Bridge-Ergebnis in 'ok' / 'transient' / 'permanent'.      WHY:, Ruft `bridge(method, params)` mit Exponential Backoff auf., Internal sentinel for result-based transient bridge failures., _TransientBridgeResult (+36 more)

### Community 11 - "Community 11"
Cohesion: 0.04
Nodes (49): Hauptloop: nimmt alle 1/fps Sekunden einen Screenshot auf.         WHY: Kontinui, # WHY: Recorder-Fehler darf NIEMALS den Worker crashen., Macht einen Screenshot via screencapture (macOS) oder Fallback.         WHY: scr, macOS screencapture nach stdout — kein Temp-File nötig.         WHY: Direkt nach, Speichert Keyframes als PNG-Dateien auf Disk.     WHY: Für manuelles Debugging u, Ein einzelner aufgenommener Frame mit Zeitstempel und Step-Annotation.     WHY:, Startet den Ring-Buffer-Recorder als Background-Task.         WHY: Muss async la, RecordedFrame (+41 more)

### Community 12 - "Community 12"
Cohesion: 0.03
Nodes (48): _best_option_match(), build_persona_prompt_block(), detect_question_topic(), _fmt_age_for_options(), _fmt_gender(), load_persona(), _normalize(), Laedt ein Persona-Profil aus profiles/<username>.json.      Returns None wenn da (+40 more)

### Community 13 - "Community 13"
Cohesion: 0.03
Nodes (43): main(), main(), capture(), EvidenceBundle, from_wire(), get_or_refresh(), health(), invalidate() (+35 more)

### Community 14 - "Community 14"
Cohesion: 0.04
Nodes (37): JSON-RPC Bridge: playstealth-cli ↔ unmask-cli.  This module provides a Python cl, Call unmask via subprocess (stdio JSON-RPC)., Call unmask via HTTP (if server is running separately)., Pre-scan a survey page before interaction.          Returns a SurveyAnalysis wit, Synchronous wrapper that falls back to basic heuristics., Basic heuristics when unmask is unavailable., Check if unmask CLI is available., Parse JSON-RPC response into SurveyAnalysis. (+29 more)

### Community 15 - "Community 15"
Cohesion: 0.05
Nodes (39): generate_fail_report_markdown(), post_github_issue_comment(), Postet einen Comment auf ein GitHub Issue via gh CLI.     WHY: Fail-Reports müss, Lädt eine Datei zu Box.com hoch via A2A-SIN-Box-Storage.     WHY: Keyframe-PNGs, Speichert den Fail-Report als Markdown + JSON auf Disk.     WHY: Lokale Kopie al, Generiert einen Markdown Fail-Report aus der NVIDIA Video-Analyse.     WHY: Stru, save_fail_report_to_disk(), upload_to_box() (+31 more)

### Community 16 - "Community 16"
Cohesion: 0.08
Nodes (42): _click_card(), main(), _open_browser(), _parser(), _print_cards(), Wartet auf URL-/DOM-Veränderung statt fixer Sleeps., _run_click_survey(), _run_open_list() (+34 more)

### Community 17 - "Community 17"
Cohesion: 0.09
Nodes (29): test_replay_harness_known_live_regressions_are_green(), ActionHint, classify_ui_state(), from_dict(), UiAssessment, UiFacts, UiSurfaceState, emit() (+21 more)

### Community 18 - "Community 18"
Cohesion: 0.11
Nodes (32): ask_vision(), ask_vision_text(), build_prompt(), click_ax_element_by_text(), cua_call(), cua_click(), cua_click_element(), cua_get_window_state() (+24 more)

### Community 19 - "Community 19"
Cohesion: 0.08
Nodes (12): install_sync_shutdown_logger(), Trigger shutdown programmatically (useful for tests)., Fallback handler for code paths that never enter an event loop.      Logs the si, Async context manager that installs graceful-shutdown signal handlers.      Thre, Wait up to ``timeout`` seconds for a shutdown signal.          Returns:, ShutdownController, Unit tests for :mod:`worker.shutdown`., Calling _restore_handlers before __aenter__ must not crash. (+4 more)

### Community 20 - "Community 20"
Cohesion: 0.1
Nodes (33): AnswerRecord, cleanup_old_entries(), clear_history(), _default_path(), get_failed_options(), get_prior_answer(), history_path(), history_summary() (+25 more)

### Community 21 - "Community 21"
Cohesion: 0.09
Nodes (29): analyze_fail_multiframe(), _maybe_downscale(), Verkleinert ein PNG wenn es zu groß ist (NVIDIA NIM Inline-Limit).     WHY: NVID, # WHY: Strukturierter Prompt erzwingt strukturiertes JSON-Output., Sendet bis zu 12 PNG-Keyframes als Multi-Image-Batch an NVIDIA NIM.     WHY: NVI, _fake_png(), _make_nvidia_response(), Tests für verschiedene API-Response-Szenarien. (+21 more)

### Community 22 - "Community 22"
Cohesion: 0.14
Nodes (30): AgentState, _append_transition_log(), archive_run_bundle(), ArchivedRun, checkpoint_path(), clear_checkpoint(), _close_heypiggy_tabs(), escalate() (+22 more)

### Community 23 - "Community 23"
Cohesion: 0.08
Nodes (5): pool(), Tests für ProfilePool — Multi-Account Account Registry., TestProfilePool, ProfilePool, ProfilePool — SQLite-backed account registry for multi-account survey automation

### Community 24 - "Community 24"
Cohesion: 0.11
Nodes (13): IllegalTransition, RuntimeState, StateMachine, StateTransition, test_blocks_after_terminal(), test_blocks_illegal_transition(), test_challenge_then_recover(), test_happy_path() (+5 more)

### Community 25 - "Community 25"
Cohesion: 0.1
Nodes (12): _answer_all_radios gibt die Anzahl der beantworteten Gruppen zurück., Wenn JS-evaluate fehlschlägt, nutze Playwright-Fallback., Ohne NVIDIA_API_KEY gibt _ask_vision_llm None zurück., _take_screenshot gibt PNG-Bytes zurück., _vision_guided_click gibt False zurück wenn Vision-Ergebnis leer ist., run_survey_loop gibt ein survey_log mit zurück., test_answer_all_radios_fallback_on_js_failure(), test_answer_all_radios_returns_count() (+4 more)

### Community 26 - "Community 26"
Cohesion: 0.19
Nodes (13): The sitepack payload failed structural validation.      Raised when the JSON is, A selector key was requested that is not declared in the sitepack., SelectorNotFoundError, SitepackValidationError, _coerce_list_map(), _coerce_string_map(), Sitepack, SitepackLoader (+5 more)

### Community 27 - "Community 27"
Cohesion: 0.15
Nodes (13): active(), from_dict(), from_json_file(), load_active_profile(), PlatformProfile, Kompiliert die Reward-Regex einmalig., # WHY: Wir liefern HeyPiggy als Default und ein paar Community-bekannte, Ermittelt das aktive Profil in dieser Prioritaet:       1) ENV PLATFORM_PROFILE_ (+5 more)

### Community 28 - "Community 28"
Cohesion: 0.18
Nodes (5): BudgetState, _cost_for_model(), Registriert Token-Verbrauch und prueft Limits sofort., Liefert (input_eur, output_eur) per MTok fuer ein Modell., Laufende Zaehler fuer einen Run.

### Community 29 - "Community 29"
Cohesion: 0.38
Nodes (2): _is_macos(), MacDesktopController

### Community 30 - "Community 30"
Cohesion: 0.2
Nodes (2): _install_playwright_stubs(), worker_module()

### Community 31 - "Community 31"
Cohesion: 0.2
Nodes (4): Zeichnet einen Schritt auf.         WHY: Zentrale Methode statt verstreuter Zähl, Metriken für einen einzelnen Worker-Schritt.     WHY: Jeder Schritt hat untersch, # WHY: HeyPiggy bestaetigt jede Umfrage mit "+0.XX EUR gutgeschrieben"., StepMetric

### Community 32 - "Community 32"
Cohesion: 0.2
Nodes (5): Speichert einen neuen Eintrag im Brain.          entry_type: "fact" | "decision", Speichert in .pcpm/brain-queue.jsonl fuer spaeteren Sync., Kurzform fuer type=fact., Kurzform fuer type=decision., Spezialisierter Ingest fuer Survey-Antworten.          WHY: Survey-Antworten sin

### Community 34 - "Community 34"
Cohesion: 0.2
Nodes (3): Guard the stability of ``worker``'s top-level public API.  If one of these asser, ``__all__`` should be sorted so diffs stay clean., TestPublicApi

### Community 35 - "Community 35"
Cohesion: 0.47
Nodes (5): get_debug_hold_seconds(), main(), Liest die Debug-Haltezeit aus der ENV statt hart zu verdrahten., Wartet auf URL-/DOM-Veränderung statt fixer Sleeps., _wait_for_page_settle()

### Community 36 - "Community 36"
Cohesion: 0.5
Nodes (2): chrome_worker_module(), _install_playwright_stubs()

### Community 37 - "Community 37"
Cohesion: 0.6
Nodes (4): main(), canary_runner.py — Live EUR Canary (SOTA #170)., run_survey(), setup()

### Community 38 - "Community 38"
Cohesion: 0.5
Nodes (2): Serialisiert den RunSummary als Dict.         WHY: Für JSON-Export und Audit-Log, Speichert den RunSummary als JSON-Datei.         WHY: Persistente Metriken für P

### Community 39 - "Community 39"
Cohesion: 0.67
Nodes (3): main(), Wartet auf den CDP-Endpoint statt blind zu schlafen., wait_for_cdp_ready()

### Community 42 - "Community 42"
Cohesion: 0.67
Nodes (1): attention.py – Attention-Check detection (extracted from monolith).

### Community 43 - "Community 43"
Cohesion: 0.67
Nodes (1): attention_check.py – Extracted from heypiggy_vision_worker.py.

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): Pytest defaults for deterministic config loading.

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): worker.modules – Extracted from monolith (Phase 3).

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (1): Liest Limits aus ENV:           BUDGET_MAX_TOKENS     (default 0 = unbegrenzt)

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (1): Baut ein Profil aus dict. Unbekannte Keys werden ignoriert,         fehlende Pfl

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (1): Laedt Profil aus JSON-Datei.

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (1): Gesamtdauer des Runs in Sekunden.

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (1): Erfolgsrate als Float (0.0 - 1.0).

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (1): Durchschnittliche Vision-Call-Dauer in Sekunden.

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (1): Durchschnittliche Bridge-Call-Dauer in Sekunden.

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (1): Berechnetes Alter in vollen Jahren aus date_of_birth.          WHY: Viele Umfrag

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (1): Return which driver type this instance implements.

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (1): Check if driver ist bereit für Operationen.

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (1): Screenshot der aktuellen Seite oder spezifischen Tab.

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (1): Click ein Element per Reference ID (accessibility ref).

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (1): Click ein Element per CSS Selector (Fallback).

### Community 61 - "Community 61"
Cohesion: 1.0
Nodes (1): Tippe Text in ein Element oder das fokussierte Element.

### Community 62 - "Community 62"
Cohesion: 1.0
Nodes (1): Führe beliebiges JavaScript im Page Context aus.

### Community 63 - "Community 63"
Cohesion: 1.0
Nodes (1): DOM Snapshot mit Accessibility Tree holen.

### Community 64 - "Community 64"
Cohesion: 1.0
Nodes (1): Hole aktuelle Page URL, Title, etc.

### Community 65 - "Community 65"
Cohesion: 1.0
Nodes (1): Navigiere zu einer URL.

### Community 66 - "Community 66"
Cohesion: 1.0
Nodes (1): Liste alle offenen Browser Tabs.

### Community 67 - "Community 67"
Cohesion: 1.0
Nodes (1): Räume Driver Resources auf.

### Community 68 - "Community 68"
Cohesion: 1.0
Nodes (1): True wenn der Circuit offen ist (Calls werden blockiert).

### Community 69 - "Community 69"
Cohesion: 1.0
Nodes (1): True wenn der Circuit geschlossen ist (normaler Betrieb).

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (1): Should we skip this survey based on risk/reward?

### Community 72 - "Community 72"
Cohesion: 1.0
Nodes (1): Anzahl der aktuell im Buffer gespeicherten Frames.

### Community 73 - "Community 73"
Cohesion: 1.0
Nodes (1): Zeitspanne die der aktuelle Buffer abdeckt (in Sekunden).

### Community 76 - "Community 76"
Cohesion: 1.0
Nodes (1): WHY: Erfolgreicher gh-Aufruf muss True zurückgeben.

### Community 77 - "Community 77"
Cohesion: 1.0
Nodes (1): WHY: Fehlgeschlagener gh-Aufruf muss False zurückgeben, kein Crash.

### Community 78 - "Community 78"
Cohesion: 1.0
Nodes (1): WHY: Exceptions (gh nicht installiert, Timeout) dürfen nicht crashen.

### Community 79 - "Community 79"
Cohesion: 1.0
Nodes (1): WHY: GitHub hat ein 65535 Zeichen Limit für Comments.

### Community 80 - "Community 80"
Cohesion: 1.0
Nodes (1): WHY: Erfolgreicher Upload muss die URL zurückgeben.

### Community 81 - "Community 81"
Cohesion: 1.0
Nodes (1): WHY: Ohne API-Key darf kein Request gesendet werden.

### Community 82 - "Community 82"
Cohesion: 1.0
Nodes (1): WHY: Ohne Keyframes gibt es nichts zu analysieren.

### Community 83 - "Community 83"
Cohesion: 1.0
Nodes (1): WHY: Mehr als 12 Frames werden abgeschnitten (NVIDIA Token-Budget).

### Community 84 - "Community 84"
Cohesion: 1.0
Nodes (1): WHY: Erfolgreiche Analyse muss alle Felder korrekt parsen.

### Community 85 - "Community 85"
Cohesion: 1.0
Nodes (1): WHY: HTTP-Fehler müssen als sauberes error-Dict zurückkommen, kein Crash.

### Community 86 - "Community 86"
Cohesion: 1.0
Nodes (1): WHY: Timeout darf den Worker nicht crashen.

### Community 87 - "Community 87"
Cohesion: 1.0
Nodes (1): WHY: Leere choices in der Response müssen erkannt werden.

### Community 88 - "Community 88"
Cohesion: 1.0
Nodes (1): WHY: Wenn NVIDIA Prosa um das JSON wickelt, muss Regex-Fallback greifen.

### Community 96 - "Community 96"
Cohesion: 1.0
Nodes (1): Absolute path to the underlying audit log file.

### Community 98 - "Community 98"
Cohesion: 1.0
Nodes (1): ``True`` once a shutdown signal has been received.

### Community 99 - "Community 99"
Cohesion: 1.0
Nodes (1): Human-readable reason (e.g. ``"SIGTERM"``) or ``None``.

### Community 101 - "Community 101"
Cohesion: 1.0
Nodes (1): Backward-compatible alias for ``max_attempts``.

### Community 103 - "Community 103"
Cohesion: 1.0
Nodes (1): Strict parser. Raises ``UnmaskError`` on missing required fields.          WHY s

### Community 104 - "Community 104"
Cohesion: 1.0
Nodes (1): Execute one JSON-RPC call. Must raise ``UnmaskError`` on RPC error.

### Community 105 - "Community 105"
Cohesion: 1.0
Nodes (1): Tear down the transport. Idempotent.

### Community 106 - "Community 106"
Cohesion: 1.0
Nodes (1): Pick a transport based on env (`UNMASK_TRANSPORT=stdio|http`).          Phase 2

### Community 107 - "Community 107"
Cohesion: 1.0
Nodes (1): True when the failure was a documented soft-fail.          Until upstream P-2 sh

### Community 108 - "Community 108"
Cohesion: 1.0
Nodes (1): Run one prompt and return a structured result.          ``images`` are URLs or d

## Knowledge Gaps
- **415 isolated node(s):** `Liefert (input_eur, output_eur) per MTok fuer ein Modell.`, `Laufende Zaehler fuer einen Run.`, `Verwaltet Limits und Counter fuer einen Worker-Run.      Usage:         guard =`, `Liest Limits aus ENV:           BUDGET_MAX_TOKENS     (default 0 = unbegrenzt)`, `Registriert Token-Verbrauch und prueft Limits sofort.` (+410 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 29`** (11 nodes): `_is_macos()`, `MacDesktopController`, `.activate_app()`, `.capture_screen_png()`, `.click_button()`, `.click_coordinates()`, `.__init__()`, `.press_key()`, `._run_osascript()`, `.type_text()`, `desktop_control.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (11 nodes): `_install_playwright_stubs()`, `test_playwright_stealth_worker_helpers.py`, `test_get_debug_hold_seconds_falls_back_on_invalid_env()`, `test_get_debug_hold_seconds_reads_env()`, `test_handle_consent_prompt_clicks_expected_controls()`, `test_handle_consent_prompt_handles_german_checkbox_flow()`, `test_is_consent_prompt_text_matches_known_prompts()`, `test_select_active_page_prefers_consent_tab()`, `test_wait_for_page_settle_returns_on_url_change()`, `test_wait_for_page_settle_returns_on_visible_selector()`, `worker_module()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (5 nodes): `chrome_worker_module()`, `_install_playwright_stubs()`, `test_playwright_chrome_worker_helpers.py`, `test_get_debug_hold_seconds_defaults_on_invalid_env()`, `test_get_debug_hold_seconds_reads_env()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (4 nodes): `Serialisiert den RunSummary als Dict.         WHY: Für JSON-Export und Audit-Log`, `Speichert den RunSummary als JSON-Datei.         WHY: Persistente Metriken für P`, `.save_to_file()`, `.to_dict()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (3 nodes): `is_attention_check()`, `attention.py – Attention-Check detection (extracted from monolith).`, `attention.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (3 nodes): `placeholder()`, `attention_check.py – Extracted from heypiggy_vision_worker.py.`, `attention_check.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (2 nodes): `conftest.py`, `Pytest defaults for deterministic config loading.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (2 nodes): `worker.modules – Extracted from monolith (Phase 3).`, `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `Liest Limits aus ENV:           BUDGET_MAX_TOKENS     (default 0 = unbegrenzt)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (1 nodes): `Baut ein Profil aus dict. Unbekannte Keys werden ignoriert,         fehlende Pfl`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (1 nodes): `Laedt Profil aus JSON-Datei.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (1 nodes): `Gesamtdauer des Runs in Sekunden.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (1 nodes): `Erfolgsrate als Float (0.0 - 1.0).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `Durchschnittliche Vision-Call-Dauer in Sekunden.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `Durchschnittliche Bridge-Call-Dauer in Sekunden.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `Berechnetes Alter in vollen Jahren aus date_of_birth.          WHY: Viele Umfrag`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `Return which driver type this instance implements.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `Check if driver ist bereit für Operationen.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `Screenshot der aktuellen Seite oder spezifischen Tab.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `Click ein Element per Reference ID (accessibility ref).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (1 nodes): `Click ein Element per CSS Selector (Fallback).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 61`** (1 nodes): `Tippe Text in ein Element oder das fokussierte Element.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 62`** (1 nodes): `Führe beliebiges JavaScript im Page Context aus.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 63`** (1 nodes): `DOM Snapshot mit Accessibility Tree holen.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 64`** (1 nodes): `Hole aktuelle Page URL, Title, etc.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 65`** (1 nodes): `Navigiere zu einer URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 66`** (1 nodes): `Liste alle offenen Browser Tabs.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 67`** (1 nodes): `Räume Driver Resources auf.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 68`** (1 nodes): `True wenn der Circuit offen ist (Calls werden blockiert).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 69`** (1 nodes): `True wenn der Circuit geschlossen ist (normaler Betrieb).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (1 nodes): `Should we skip this survey based on risk/reward?`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 72`** (1 nodes): `Anzahl der aktuell im Buffer gespeicherten Frames.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 73`** (1 nodes): `Zeitspanne die der aktuelle Buffer abdeckt (in Sekunden).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 76`** (1 nodes): `WHY: Erfolgreicher gh-Aufruf muss True zurückgeben.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 77`** (1 nodes): `WHY: Fehlgeschlagener gh-Aufruf muss False zurückgeben, kein Crash.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 78`** (1 nodes): `WHY: Exceptions (gh nicht installiert, Timeout) dürfen nicht crashen.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 79`** (1 nodes): `WHY: GitHub hat ein 65535 Zeichen Limit für Comments.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 80`** (1 nodes): `WHY: Erfolgreicher Upload muss die URL zurückgeben.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 81`** (1 nodes): `WHY: Ohne API-Key darf kein Request gesendet werden.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 82`** (1 nodes): `WHY: Ohne Keyframes gibt es nichts zu analysieren.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 83`** (1 nodes): `WHY: Mehr als 12 Frames werden abgeschnitten (NVIDIA Token-Budget).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 84`** (1 nodes): `WHY: Erfolgreiche Analyse muss alle Felder korrekt parsen.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 85`** (1 nodes): `WHY: HTTP-Fehler müssen als sauberes error-Dict zurückkommen, kein Crash.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 86`** (1 nodes): `WHY: Timeout darf den Worker nicht crashen.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 87`** (1 nodes): `WHY: Leere choices in der Response müssen erkannt werden.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 88`** (1 nodes): `WHY: Wenn NVIDIA Prosa um das JSON wickelt, muss Regex-Fallback greifen.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 96`** (1 nodes): `Absolute path to the underlying audit log file.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 98`** (1 nodes): ```True`` once a shutdown signal has been received.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 99`** (1 nodes): `Human-readable reason (e.g. ``"SIGTERM"``) or ``None``.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 101`** (1 nodes): `Backward-compatible alias for ``max_attempts``.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 103`** (1 nodes): `Strict parser. Raises ``UnmaskError`` on missing required fields.          WHY s`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 104`** (1 nodes): `Execute one JSON-RPC call. Must raise ``UnmaskError`` on RPC error.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 105`** (1 nodes): `Tear down the transport. Idempotent.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 106`** (1 nodes): `Pick a transport based on env (`UNMASK_TRANSPORT=stdio|http`).          Phase 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 107`** (1 nodes): `True when the failure was a documented soft-fail.          Until upstream P-2 sh`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 108`** (1 nodes): `Run one prompt and return a structured result.          ``images`` are URLs or d`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `main()` connect `Community 3` to `Community 0`, `Community 6`, `Community 8`, `Community 12`, `Community 17`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._
- **Why does `RunSummary` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 38`, `Community 31`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._
- **Why does `HeyPiggyWorkerProfilePathTests` connect `Community 3` to `Community 7`?**
  _High betweenness centrality (0.057) - this node is a cross-community bridge._
- **Are the 229 inferred relationships involving `RunSummary` (e.g. with `VisionGateController` and `Lädt das Benutzerprofil von Disk.     WHY: Profil-Fragen in Umfragen (Region, Na`) actually correct?**
  _`RunSummary` has 229 INFERRED edges - model-reasoned connections that need verification._
- **Are the 213 inferred relationships involving `ScreenRingRecorder` (e.g. with `VisionGateController` and `Lädt das Benutzerprofil von Disk.     WHY: Profil-Fragen in Umfragen (Region, Na`) actually correct?**
  _`ScreenRingRecorder` has 213 INFERRED edges - model-reasoned connections that need verification._
- **Are the 192 inferred relationships involving `GlobalBrainClient` (e.g. with `SecretSource` and `InfisicalTarget`) actually correct?**
  _`GlobalBrainClient` has 192 INFERRED edges - model-reasoned connections that need verification._
- **Are the 195 inferred relationships involving `CircuitBreaker` (e.g. with `VisionGateController` and `Lädt das Benutzerprofil von Disk.     WHY: Profil-Fragen in Umfragen (Region, Na`) actually correct?**
  _`CircuitBreaker` has 195 INFERRED edges - model-reasoned connections that need verification._