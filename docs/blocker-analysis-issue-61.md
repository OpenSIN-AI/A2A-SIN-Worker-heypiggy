# Blocker-Analyse: Worker öffnet nach Login keine Umfragen

**Scope:** Punkt 3 aus Issue #61 — "Worker loggt erfolgreich ein, klickt danach aber keine Umfrage an".
**Analyse-Datum:** 2026-04-19
**Untersuchte Dateien:** `heypiggy_vision_worker.py`, `survey_orchestrator.py`, `session_store.py`, `platform_profile.py`.

---

## TL;DR

Nach erfolgreichem Google-Login fehlt **jeder deterministische Code-Pfad, der die erste Umfrage öffnet**. Die komplette "Dashboard → erste Umfrage"-Entscheidung ist in fünf ineinandergreifenden Bugs an Vision delegiert, dem aber gleichzeitig die nötigen Prompt-Bausteine entzogen werden. Das Netto-Verhalten: Vision sieht Login-Seite oder Dashboard-Homepage, bekommt keine Survey-Ref-IDs im Prompt, halluziniert Selektoren (`div.survey-item` ohne ID) und landet in der RETRY-Spirale bis `MAX_NO_PROGRESS` den Worker stoppt.

### Recovery-Milestone (2026-04-26)

- **PlayStealth-Baseline teilweise wiederhergestellt:** Der Worker kommt im Playwright-Pfad wieder durch Vision-Preflight, bindet einen stabilen Worker-Tab, scannt das Dashboard nativ und erzeugt wieder einen echten `queue_begin`-Versuch statt bei `MAX_NO_PROGRESS` zu verhungern.
- **Wichtige Rückbauten:**
  - `clickSurvey('<id>')`-Pfad für Dashboard-Karten in `heypiggy_vision_worker.py` wiederhergestellt.
  - Playwright-Driver auf echte Multi-Tab-Isolation und `tabId`-Routing zurückgeführt (`driver_interface.py`).
  - Consent-/Start-Modal-Follow-up aus dem alten PlayStealth-Flow wieder in den Monolithen eingebaut.
  - `dom.queryAll` / `ghost_click` im Playwright-Pfad nativ verfügbar gemacht, damit der Orchestrator nicht mehr sofort in den Bridge-Fallback kippt.
- **Neuer Stand des Blockers:** Statt gar nichts anzuklicken, landet der Worker jetzt reproduzierbar auf `https://www.heypiggy.com/?page=cashout`. Das beweist, dass der Dashboard→Click-Pfad wieder lebt — der verbleibende Fehler liegt jetzt in der **Survey-Karten-Auswahl / Cashout-Fehlrouting**, nicht mehr im ursprünglichen "klickt gar nichts"-Stillstand.

---

## Die fünf Ursachen im Detail

### Cause 1 (kritisch): `SurveyOrchestrator.begin()` wird nie aufgerufen

- `SurveyOrchestrator.begin()` existiert genau für diesen Zweck (`survey_orchestrator.py:273-298`):
  > "Startet die erste Survey: explizite URL oder Dashboard + höchster Reward."
- Im Worker wird der Orchestrator instanziiert (`heypiggy_vision_worker.py:5363`), aber **`.begin()` taucht in der gesamten Codebase nur in Tests auf** (`tests/test_survey_orchestrator.py`).
- Der Orchestrator wird erst nach dem ersten `survey_done` aktiv (`heypiggy_vision_worker.py:5934` `on_survey_completed(...)`) — für die allererste Umfrage existiert also keine deterministische Logik.
- **Konsequenz:** Nach Login muss Vision selbst erkennen, dass sie im Dashboard ist, und die richtige Karte klicken. Ohne Prompt-Hinweise (siehe Cause 2+3) ist das unmöglich.

### Cause 2: Dashboard-Ranking-Block feuert nur bei URL-Token `page=dashboard`

`heypiggy_vision_worker.py:2641-2644`:

```python
is_dashboard = (
    ("heypiggy.com" in current_url.lower() or "heypiggy" in (page_context or "").lower())
    and "page=dashboard" in (page_context or "").lower()
)
```

- Google-OAuth redirectet i. d. R. auf `https://www.heypiggy.com/`, `/?tab=surveys` oder `/dashboard` — **niemals automatisch** auf `/?page=dashboard` (das ist ein Legacy-Query-Tab).
- Fallback-Text-Check (`"Deine verfügbaren Erhebungen"`) matcht nur auf Deutsch; bei englischer Browser-Locale schlägt auch der fehl.
- **Konsequenz:** `dashboard_block` bleibt leer, Vision bekommt keine Top-5-Liste mit `ref`-IDs, kein "DRINGENDE AKTION: click_ref auf die TOP-1 Karte".

### Cause 3: Generischer Clickable-Scan auf 25 Elemente gekappt

`heypiggy_vision_worker.py:2044-2070`:

```js
var all = document.querySelectorAll('[onclick], [role="button"], a[href], button,
    input[type="submit"], [style*="cursor: pointer"], .survey-item, .survey-card,
    [class*="card"], [class*="survey"]');
for (var i = 0; i < Math.min(all.length, 25); i++) { ... }
```

- Auf dem HeyPiggy-Dashboard liefern Navbar, Profil-Dropdown, Filter, FAQ-Links, Footer und Social-Icons **locker >25 Treffer** im Query-Selector **bevor** die ersten `div.survey-item`-Kacheln kommen.
- Der Scan iteriert in DOM-Reihenfolge — Umfrage-Karten landen typischerweise jenseits von Index 25.
- **Konsequenz:** `clickable_info` enthält keine Survey-IDs. Vision kann nur die generischen `#nav-*`-Buttons klicken → no_progress.

### Cause 4: Kein explizites Dashboard-Navigate nach Login

`heypiggy_vision_worker.py:5662-5670`:

```python
if "login" in _current_url or "signin" in _current_url or not _current_url:
    _google_result = await attempt_google_login(email or "")
    ...
    if _google_result.get("ok"):
        await human_delay(4.0, 7.0)
        await save_session("after_google_login")
# --- kein navigate() zur Dashboard-URL ---
# Hauptloop startet sofort.
```

- Nach OAuth landet der Tab, wo immer HeyPiggy ihn zurückwirft (Root-Page, Onboarding-Modal, Consent-Popup, Welcome-Screen).
- Weder `platform_profile.active().dashboard_url` (`https://www.heypiggy.com/`) noch `/?page=dashboard` werden aktiv angesteuert.
- **Konsequenz:** Vision sieht möglicherweise eine Welcome-Seite oder ein Modal und hat kein mentales Modell "ich bin auf dem Dashboard".

### Cause 5: Post-Login-Delay von 4–7 s ist zu kurz

- Google-OAuth-Flow = 3–5 Redirect-Hops (account-picker → consent → callback → heypiggy.com/auth/google/callback → final redirect).
- Bei durchschnittlicher Verbindung dauert der komplette Flow **8–15 s**.
- `human_delay(4.0, 7.0)` kann das erste Vision-Snapshot mitten in einem Redirect abfeuern → weißer Screenshot oder Google-Splash → Vision liefert `RETRY`, `no_progress_count` zählt hoch.

---

## Vorgeschlagene Fixes (Reihenfolge = Priorität)

| Fix                                                                                                                                                                                                                                                | Wirkung                                                         | Aufwand | Datei / Zeile                            |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- | ------- | ---------------------------------------- |
| **F1** (Root-Fix): Nach `after_google_login` explizit `await SURVEY_ORCHESTRATOR.begin()` aufrufen. Orchestrator navigiert dann zur Dashboard-URL **und** klickt die beste Karte selbstständig. Vision wird erst für die Screener-Frage aktiviert. | Eliminiert Cause 1+4 in einem Schritt.                          | ~15 LOC | `heypiggy_vision_worker.py` nach Z. 5668 |
| **F2**: `is_dashboard`-Check umbauen: URL-Pfad-Prefix (`/`, `/dashboard`, `/?page=dashboard`, `/?tab=surveys`) + Existenz eines `div.survey-item` im DOM. Query-Token-Check entfernen.                                                             | Dashboard-Ranking-Block wird auch bei Homepage-Landing geladen. | ~20 LOC | Z. 2641-2644                             |
| **F3**: Im `js_scan` die Priorität umdrehen: erst `.survey-item, [id^="survey-"]` (unlimitiert), dann andere Elemente (25 Cap).                                                                                                                    | Survey-Karten kommen garantiert in `clickable_info`.            | ~10 LOC | Z. 2041-2071                             |
| **F4**: `human_delay` nach Google-Login auf `8-14 s` + aktive URL-Stabilitäts-Probe (drei gleiche Samples in 2 s Abstand).                                                                                                                         | Kein Screenshot während OAuth-Redirect.                         | ~15 LOC | Z. 5667                                  |
| **F5**: `HIGHEST_REWARD_JS` im Orchestrator um `div.survey-item, [class*="SurveyCard"]` erweitern, falls HeyPiggy das Frontend-CSS migriert.                                                                                                       | Robustheit gegen Frontend-Refactor.                             | ~5 LOC  | `survey_orchestrator.py:164-191`         |

**Alle fünf Fixes zusammen = ~65 LOC** + passende Tests in `tests/test_survey_orchestrator.py` / `tests/test_heypiggy_vision_worker.py`.

---

## Verifikations-Plan

1. **Repro ohne Fix:** Worker mit leerem `~/.heypiggy/session_cache.json` starten, Google-Login abwarten, in `/tmp/heypiggy_<runid>/audit.jsonl` nach `dashboard_ranked` greppen — darf **nicht** auftauchen (Beweis für Cause 2).
2. **Nach F1+F2:** `dashboard_ranked` erscheint innerhalb der ersten 3 Steps, gefolgt von `queue_begin` mit `url=https://www.heypiggy.com/survey/...`.
3. **Metrik:** `run_summary.json["step_metrics"]` sollte `steps_to_first_survey <= 5` zeigen (heute meist `>30` oder `MAX_NO_PROGRESS` hit).

---

## Offene Fragen

1. **CSS-Selektoren-Drift:** `div.survey-item` ist in `A2A-CARD.md`, `sitepacks/heypiggy/v1/` und im Worker-Code **hardgecodet**. Wenn HeyPiggy das Frontend auf z. B. `[data-testid="survey-card"]` migriert, fallen alle fünf Blocks gleichzeitig aus. Sollte als Monitoring-Task (Canary-Scan) abgesichert werden.
2. **Session-Restore-Pfad:** Soll `SurveyOrchestrator.begin()` auch laufen wenn `session_restore` erfolgreich war? Aktuelle Logik: "erst Login, dann Loop" — mit Session-Restore spart man den Login, aber die "erste Umfrage öffnen"-Lücke bleibt.
3. **Quick-Workaround:** `HEYPIGGY_DASHBOARD_URL=https://www.heypiggy.com/?page=dashboard` in `.env.example` setzen umgeht Cause 2 ohne Code-Änderung (aber behebt Cause 1, 3, 4, 5 nicht).

---

_Analyse durchgeführt von v0 am 2026-04-19. Code-Zeilenangaben beziehen sich auf Commit-Basis `main` @ `34bf4a3c`._
