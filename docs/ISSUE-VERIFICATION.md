# Issue-Verification — was wurde wirklich gefixt?

**Stichtag:** 2026-04-28

Dieses Dokument ist eine **forensische Pruefung** der zuletzt geschlossenen
Issues. Hintergrund: am 2026-04-28 wurden mehrere kritische Issues
gleichzeitig geschlossen, ohne dass jeweils ein zugehoeriger Merge-PR sichtbar
war. Hier wird pro Issue der Code-Beweis gefuehrt — wirklich gefixt, halbgar
gefixt, oder nur kosmetisch zugemacht.

Format pro Issue: **Status • Code-Evidenz • Test-Evidenz • Verbleibende Luecke**.

---

## #84 — `fix: stop dashboard recovery from routing to cashout/giftcard`

**Status:** WIRKLICH GEFIXT.

**Code-Evidenz:**
- `survey_orchestrator.py:240` — JS-Side Forbidden-Pattern-Regex wird in den
  Page-Scoring-Code injiziert, sodass die Dashboard-Bewertung Cashout-/
  Giftcard-Tiles aktiv ausschliesst.
- `survey_orchestrator.py:705-727` — Python-Side Filter mit derselben Regex
  (`r"cashout|auszahlen|gift.?card|geschenkkarte|einstellungen|..."`).
- `opensin_runtime/ui_state.py:11-150` — Neuer Klassifizierer-State
  `WRONG_LANDING_CASHOUT` mit Detector basierend auf URL und kombinierten
  Body-Markern.
- `heypiggy_vision_worker.py:1799` — Worker reagiert explizit auf
  `WRONG_LANDING_CASHOUT` und steuert zurueck.
- `heypiggy_vision_worker.py:7704-7706` — Cashout/Giftcard-URLs sind in der
  zentralen URL-Filter-Liste.

**Test-Evidenz:**
- `tests/test_survey_orchestrator.py:565` — `test_v2_dashboard_rejects_cashout_link`
- `tests/runtime/test_ui_state_classifier.py:41` — `test_cashout_landing_is_classified_as_wrong_landing`
- `tests/test_heypiggy_vision_worker.py:1206` — `test_needs_post_login_dashboard_bootstrap_for_cashout_page`

**Verbleibende Luecke:** Keine (auf Code-Ebene). Live-Canary nicht ausgefuehrt
(siehe CEO-AUDIT 4.1).

---

## #85 — `fix: remove click_ref bridge bypass and fail closed before tab mutations`

**Status:** GROSSTEILS GEFIXT, eine Restschwaeche bis zu diesem Commit.

**Code-Evidenz (positiv):**
- `heypiggy_vision_worker.py:7501-7576` — `run_click_action()` ist die zentrale
  Eskalationspipeline. Jeder Click-Entry-Point laeuft hier durch
  `escalating_click()`. Direkt-Bypass an die Bridge gibt es nicht mehr.
- `heypiggy_vision_worker.py:7509` — explizite Code-Annotation
  `WHY: Issue #85 verlangt, dass click_ref keinen direkten Bridge-Bypass mehr hat.`
- `heypiggy_vision_worker.py:2349-2459` — `ensure_worker_preflight()` als
  fail-closed Gate vor jeder Browser-Mutation.
- `heypiggy_vision_worker.py:7862-7869` — Preflight wird in `main()` aufgerufen
  und beendet den Run hart bei Fehler.

**Schwaeche vor diesem Commit:**
- `heypiggy_vision_worker.py:7850-7860` — `SKIP_PREFLIGHT=1` in der Umgebung
  reichte aus, um den fail-closed-Preflight zu deaktivieren. Nur eine
  Audit-Warnung, keine Schutzschicht. Fuer "fail closed" zu schwach: ein
  unbedacht gesetztes ENV-Var im Prod-Container deaktiviert die Sicherheit.

**Mit diesem Commit:**
- `SKIP_PREFLIGHT` wird nur noch akzeptiert, wenn ZUSAETZLICH `WORKER_ENV` in
  `{dev, development, test, ci}` steht **oder** `WORKER_ALLOW_PREFLIGHT_SKIP=1`
  explizit gesetzt ist. Ansonsten wird `SKIP_PREFLIGHT` mit Audit-Eintrag
  ignoriert.
- Test in `tests/test_heypiggy_vision_worker.py` (siehe TODO in
  Hardening-Backlog).

**Verbleibende Luecke:** Keine bekannte Bypass-Route mehr. Falls neue
Click-Entry-Points hinzugefuegt werden, bitte explizit durch `run_click_action`
routen — die Pipeline ist die einzige zugelassene Tuer.

---

## #80 — `regression tracker: restore path from dashboard click to real question pages`

**Status:** GUELTIG GESCHLOSSEN als Tracker; haengt funktional an #84.

**Code-Evidenz:** Tracker referenziert ausdruecklich #84 als Ursache. Da #84
echt gefixt ist und der Recovery-Pfad in `survey_orchestrator.py` und
`heypiggy_vision_worker.py` zentralisiert ist, ist dieser Tracker schluessig
geschlossen.

**Verbleibende Luecke:** Live-Canary-Beweis steht aus (siehe CEO-AUDIT 4.1).

---

## #81 — `Answer loop: add provider-aware question router` (OFFEN bis Commit)

**Status (vor Commit):** NICHT IMPLEMENTIERT als Router.

Vorhandene Bausteine:
- `panel_overrides.py` — Detection und Prompt-Hint-Generierung.
- `persona.py:resolve_answer()` — Persona-Fact-Match.
- `persona.py:AnswerLog.find_prior_answer()` — Konsistenz-Pruefung.

Was fehlte: ein **deterministischer Code-Pfad**, der diese Bausteine zu
einer einzigen Antwort-Entscheidung verschmilzt, bevor Vision aufgerufen
wird. Vision wurde bisher mit allen Hints geflutet und musste selber
priorisieren — das ist nicht-deterministisch und teuer.

**Mit diesem Commit:** `answer_router.py` schliesst die Luecke. Reihenfolge:

1. Captcha / DQ-Page → Sofortaktion
2. Attention-Check → woertliche Anweisung, Persona ignorieren
3. Prior-Consistency → fruehere Antwort wiederverwenden
4. Persona-Fact (HIGH) → aus Profil
5. Panel-Rule + strukturelle Heuristik (Grid/FreeText/Slider)
6. ASK_VISION → letzte Instanz

Tests in `tests/test_answer_router.py` decken alle Pfade ab.

**Verbleibende Luecke:** Wiring in den Monolithen passiert in einem zweiten
Schritt (TODO im Hardening-Backlog). Aktuell ist der Router importierbar und
testbar, aber noch nicht in den Vision-Prompt-Build geleitet — das ist
absichtlich, damit der Router erst CI-gruen ist, bevor er den Live-Pfad
veraendert.

---

## #63 / #64 / #65 — Ruff / Mypy / Bandit Findings

**Status:** ALS GESCHLOSSEN MARKIERT, ABER NICHT VOLLSTAENDIG ADRESSIERT.

**Realitaet:**
- `worker/`-Paket ist mypy-strict und ruff-clean. Das ist echt.
- Der Monolith `heypiggy_vision_worker.py` ist NICHT ruff-clean.
- Bandit / pip-audit / detect-secrets laufen in CI; Findings werden noch nicht
  in PRs geblockt.

**Was zu tun ist:** siehe `docs/HARDENING-BACKLOG.md`. Diese Issues sind
ehrlicher als "geschlossen aber halbherzig" einzustufen — die GitHub-Schliessung
spiegelt nicht die Code-Realitaet wider.

---

## Sonstige zuletzt geschlossene Issues

- **#82** (compact Playwright window) — gefixt: Playwright-Worker startet
  defaultmaessig kompakt.
- **#83** (Playwright snapshot accessibility API) — gefixt: snapshot ruft die
  korrekte API.
- **#43, #38, #34, #32** — alles substantielle Bug-Fixes mit Code-Evidenz im
  jeweiligen PR. Schliessungen sauber.

---

## Zusammenfassung

| Issue | Schliessung | Echt gefixt? | Test-Coverage | Live-Beweis |
| ----- | ----------- | ------------ | ------------- | ----------- |
| #84   | sauber      | ja           | ja            | offen       |
| #85   | sauber      | ja (mit diesem Commit) | wird nachgezogen | offen |
| #80   | sauber      | ja (depends on #84) | -      | offen       |
| #81   | offen → Commit | ja (mit diesem Commit) | ja | offen     |
| #63   | **kosmetisch** | nein, Monolith dirty | -    | -           |
| #64   | teilweise   | `worker/` ja, Monolith nein | -  | -           |
| #65   | teilweise   | CI ja, Findings nicht alle behoben | - | -      |

"Live-Beweis offen" bedeutet: das Code-Verhalten stimmt, aber es gibt keinen
aktenkundigen Live-Run, der den Fix unter Produktionsbedingungen zeigt.
Siehe `docs/CEO-AUDIT.md`, Punkt 4.1.
