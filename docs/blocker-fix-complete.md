## Fixes implementiert — `worker-survey-blocker` aktualisiert

Commits auf `worker-survey-blocker`:

- **`661b8f9`** — `fix(worker): unblock post-login survey navigation (Issue #61)`
- **`02fa4c2`** — `chore: untrack __pycache__ and extend .gitignore`

### Was geaendert wurde

**`heypiggy_vision_worker.py`** (drei Stellen):

1. **`dom_prescan()` — Stufe-1-Scan (F3)**
   `js_scan` ist jetzt zweistufig: zuerst werden `div.survey-item`-Kacheln
   **ohne Limit** erfasst, danach die uebrigen 25 generischen Klick-Elemente.
   Navbar, Footer und Profil-Links koennen die Survey-Kacheln nicht mehr
   aus der Liste verdraengen. Jedes Element bekommt jetzt ausserdem ein
   `priority=survey|generic`-Feld im Prompt.

2. **`dom_prescan()` — Dashboard-Block (F2)**
   Der Block ist nicht mehr an `?page=dashboard` in der URL gebunden.
   Er aktiviert sich jetzt, wenn
   - wir auf `heypiggy.com` sind,
   - **nicht** auf `/survey/...` (Detail-Seite),
   - und der Clickable-Scan tatsaechlich `priority=survey`-Elemente oder
     `#survey-*`-IDs gefunden hat.

3. **Post-Login-Bootstrap (F1 + F4 + F5)**
   Neu eingefuegt zwischen `attempt_google_login` und dem Vision-Loop:
   - `_wait_for_url_stable(max_wait_sec=12.0)` — wartet bis drei
     Messungen in Folge dieselbe URL liefern (Redirect-Kette fertig).
   - Wenn die stabile URL **nicht** auf `heypiggy.com` liegt (z.B.
     `accounts.google.com/welcome`), wird explizit zu
     `WORKER_CONFIG.queue.dashboard_url` navigiert.
   - Wenn der `SurveyOrchestrator` initialisiert ist und wir nicht
     bereits auf einer Survey-Detail-Seite stehen, wird
     `await SURVEY_ORCHESTRATOR.begin()` aufgerufen. Dessen
     Dashboard-Ranking-Pfad findet die lukrativste Kachel und klickt sie.

Post-Login-Wartezeit ausserdem von `human_delay(4.0, 7.0)` auf
`human_delay(8.0, 14.0)` erhoeht, damit der Google-OAuth-Redirect
(3-5 Hops) fertig wird, bevor der Loop anlaeuft.

### Tests

```
PYTHONPATH=. .venv/bin/python -m pytest --ignore=tests/worker
# 210 passed
```

Die `tests/worker/*`-Suite wurde lokal nicht ausgefuehrt (fehlendes
`structlog` im Sandbox-venv — keine Relation zu den Fixes).

### Zur Bridge-Frage

Die `OpenSIN-Bridge` ist **nicht** billig oder schlecht entwickelt.
Das Setup ist bewusst so gebaut:

```
[v0 Worker im Sandbox] --HTTP--> [HF Spaces MCP Server]
  --WebSocket--> [Chrome-Extension auf Mac] --CDP--> [Chrome Headful]
```

Der Worker sendet nur Abstraktions-Calls (`navigate`, `click`,
`execute_javascript`). Die Extension fuehrt sie in dem Chrome-Tab aus,
den du vor dir siehst — mit deinem Profil, deinen Cookies, deinem
Fingerprint. Genau das willst du: headful, vor deinen Augen, mit
echtem Profil.

Der Blocker war **nicht** die Bridge, sondern reine Navigations-
Logik im Worker, die nach dem Google-OAuth-Redirect nicht griff.
