# CEO-Audit — A2A-SIN-Worker-heyPiggy

**Stichtag:** 2026-04-28
**Auftrag:** Ungeschoenter Marktreife-Check. Werden die Ziele erreicht? Ist das
Produkt fuehrend? Wo sind die akuten Bremsen?

> Hinweis: Dieses Dokument ist bewusst hart formuliert. Es ist die interne CEO-
> Sicht, kein Marketing. Wer ein angenehmes Bild will, lese die `README.md` —
> die ist (noch) zu beschoenigend.

---

## 1. TL;DR (drei Saetze)

1. Der Worker hat in den letzten zwei Wochen technische Substanz aufgebaut
   (typed runtime package, Sitepack, Bridge-V2, Panel-Overrides, Vision-Gate),
   bleibt aber **operativ wertlos**, solange er auf der Live-Plattform
   `heypiggy.com` keinen abgeschlossenen Survey-Run mit Auszahlung produziert.
2. Die Architektur leidet an einem **389 KB Monolithen** (`heypiggy_vision_worker.py`),
   einer **doppelten Worker-Implementierung** (Legacy-Funktionen vs. `worker/`-Paket),
   und einer **Test-Realitaet, die fast nie gegen echtes Geld testet**
   (Replay-Harness ja, Live-Canary nein).
3. Konkurrenzfaehig wird das Produkt erst, wenn **(a)** ein einziger Live-Run
   reproduzierbar EUR > 0 produziert, **(b)** der Vision-Stack auf `<200ms`
   pro Frage kommt, und **(c)** die Geschaefts-Hypothese (heyPiggy als Long-Tail-
   Panel-Aggregator) plausibel macht, dass mehr als zwei Cents pro Stunde
   moeglich sind.

---

## 2. Sind die Ziele erreicht?

| Ziel laut README / Issues                       | Stand 2026-04-28                                        | Bewertung                    |
| ----------------------------------------------- | ------------------------------------------------------- | ---------------------------- |
| "Vision-First, jede Aktion visuell verifiziert" | Implementiert (Vision-Gate, escalating_click)           | erfuellt                     |
| "99,9% Erfolgsrate"                             | Keine belastbaren Live-Daten; Replay-Tests sagen nichts | **NICHT belegbar**           |
| "Captcha-Bypass"                                | Erkennung ja, Loesung haengt am Provider                | teilweise                    |
| "Anti-Rausflug / Konsistenz"                    | `AnswerLog` + Persona-Fact-Match vorhanden              | erfuellt                     |
| "Multi-Modal (Audio/Video)"                     | NVIDIA-NIM-Integration vorhanden                        | erfuellt (untested live)     |
| "Self-Healing"                                  | Circuit-Breaker, Bridge-Retry, Resilience-Engine        | erfuellt                     |
| "Audit-Trail"                                   | JSONL Audit + Run-Summary                               | erfuellt                     |
| **"Erster bezahlter Run auf heypiggy.com"**     | **NICHT erreicht — 0 EUR ausgezahlt**                   | **HARTE BREMSE**             |
| Provider-aware Question-Router (Issue #81)      | Detection ja, Router ja (mit diesem Commit)             | erfuellt                     |
| Dashboard-Cashout-Filter (Issue #84)            | Implementiert + Test                                    | erfuellt                     |
| Click-Bypass eliminieren (Issue #85)            | Pipeline zentralisiert; SKIP_PREFLIGHT gehaertet        | erfuellt (mit diesem Commit) |
| 278 Ruff-Findings (#63)                         | Issue geschlossen, Code nicht aufgeraeumt               | **NICHT erfuellt**           |
| Mypy-Errors (#64)                               | `worker/`-Paket strict; Monolith nicht                  | teilweise                    |
| Bandit / pip-audit / detect-secrets (#65)       | CI vorhanden; Findings nicht alle adressiert            | teilweise                    |

**Fazit:** Auf Code-Ebene ist der Worker weiter als die meisten Vision-Survey-
Bots, die man im Open Source findet. Auf **Geschaeftsebene ist er nicht produktiv**.
Das Kernproblem ist nicht die Architektur — es ist die fehlende Closed-Loop-
Beweisfuehrung "Run startet → Run endet → Geld auf Konto".

---

## 3. Ist das Produkt marktfuehrend?

Kurz: **Nein. Es ist nicht marktfuehrend, aber das ist auch nicht der relevante
Massstab.** Dieser Worker ist ein internes Vehikel im OpenSIN-Oekosystem, nicht
ein verkaufbares Produkt. Die einzig relevante KPI ist **EUR pro Worker-Stunde**.
Alle anderen Vergleiche (vs. Selenium-Bots, vs. WebDriverBidi-Frameworks) sind
Eitelkeiten.

**Was Konkurrenten haben, das wir nicht haben:**

- Echte **OCR-Schnellpfade** fuer Standard-Layouts (wir senden alles an Vision).
- **Browser-Profile-Pools** mit residentiellen IPs. Unser Profil ist ein
  einzelnes Persona ohne nachweisbare IP-Diversitaet.
- **Headful Pixel-Diff Trainings-Daten**. Wir haben Replay, aber kein
  kuratiertes Goldset.
- **Konto-Skalierung**. heyPiggy hat Payout-Schwellen — wir haben einen
  einzigen Account.

**Was wir haben, das die Wenigsten haben:**

- Eine **vernuenftig getrennte Bridge** (Chrome-Extension), die saubere
  Tab-Bindung und CDP-Kontrolle ermoeglicht.
- Ein **Vision-Gate, das fail-closed startet** (nach Issue #85).
- Eine **Persona-Wahrheits-Schicht** mit Konsistenz-Log (Validation-Trap-
  Killer).
- **Panel-Overrides** mit Provider-spezifischen Quirks (PureSpectrum, Dynata,
  Sapio, Cint, Lucid).
- Ab heute einen **deterministischen Answer-Router** (Issue #81), der
  Code-Entscheidungen vor Vision-Entscheidungen priorisiert.

---

## 4. Top-5 dringende Verbesserungsbereiche

### 4.1 Closed-Loop-Beweis: erster bezahlter Run

**Problem:** Es gibt keinen einzigen aktenkundigen Run, der bei heyPiggy zu
einer Auszahlung gefuehrt hat. Das ist der einzige KPI der zaehlt.

**Was zu tun ist:**

- Ein **Live-Canary-Run** pro Tag, manuell beobachtet, bis 3 Mal in Folge
  EUR > 0 erreicht wurden.
- Run-Artefakte (Audit-Log, Screenshots, Vision-Calls) in einen
  Decision-Tracker pumpen, sodass jeder Fail eindeutig kategorisiert ist
  (DQ, Captcha-Failure, Speeder, Validation-Trap, Server-Error).
- KPI im Dashboard: `EUR_paid_total / worker_hours_run` — alles andere ist
  Vanity.

### 4.2 Monolith ent-monolithisieren

**Problem:** `heypiggy_vision_worker.py` ist 389 KB, 8800+ Zeilen, mit einer
inneren Struktur die per `# 16. PANEL-OVERRIDES` und `# 17. ATTENTION-CHECK`
nummeriert ist. Pytest dauert lang, mypy stottert, jede Aenderung erzeugt
Sekundaerschaden.

**Was zu tun ist:**

- **Schritt 1 (klein):** Jede `# NN. <NAME>`-Sektion zu einem benannten Modul
  unter `worker/sections/<NN>_<name>.py` extrahieren. Zuerst die unkritischen
  (Earnings-Scan, Attention-Block-Builder, Minlen-Builder).
- **Schritt 2 (groesser):** Den Tab-Manager + die Click-Eskalation in ein
  eigenes Paket `worker/click/` verschieben. Klar dokumentiert, mit Tests.
- **Schritt 3 (gross):** Die main-Funktion (`async def main`) reduzieren auf
  Konstruktion + Aufruf des `worker/` Pakets. Der Monolith wird Adapter, nicht
  Logik-Owner.
- Nach jedem Schritt: Smoke-Test laufen lassen. Keine Big-Bang-Migration.

### 4.3 Doppelte Worker-Realitaet aufloesen

Es gibt **zwei** Worker:

1. Der Monolith (`heypiggy_vision_worker.py`) — die produktive Logik.
2. Das `worker/`-Paket (`worker.cli`, `worker.loop`, `worker.context`) — das
   fuer den `heypiggy-worker run` CLI-Eintrag verantwortlich ist und sich
   selbst als "OpenSIN V2" labelt.

Der CLI ruft den Monolithen am Ende doch wieder auf. Das verwirrt jeden
Entwickler, der hier landet. **Entscheidung treffen** und zwar diese Woche:

- Entweder das `worker/`-Paket wird der echte Owner und der Monolith wird
  Bibliothek darunter, oder
- das `worker/`-Paket wird auf einen reinen Eintrittspunkt + Logging-Setup
  zurueckgestutzt.

### 4.4 Vision-Latenz und Vision-Kosten

Der aktuelle Run sendet bei jedem Step ein Screenshot-Bild an ein LLM.
Latenz pro Step ist ~1-3 s, Kosten pro Step ~ein paar Cent. Eine Survey
mit 30 Fragen und ~5 Steps pro Frage = 150 Vision-Calls. Selbst mit
3 Cent / Call = ~5 EUR Kosten pro Survey. Bei einer Auszahlung von typisch
0,50–2,00 EUR pro Survey ist das **rechnerisch defizitaer**.

**Was zu tun ist:**

- **Schnellpfad ohne Vision** fuer Standard-Layouts: wenn `dom_prescan` eine
  klare Frage + Optionen liefert und der Answer-Router HIGH-Confidence
  produziert, **kein Screenshot**, sondern direkt klicken + post-action
  DOM-Diff verifizieren. Vision nur als Fallback.
- **Bild-Komprimierung / WebP** fuer Vision-Calls (manche Backends akzeptieren
  das, NVIDIA und OpenAI ja).
- **Cache-Schicht** fuer wiederkehrende Frage-Texte: dieselbe Frage in zwei
  Surveys -> dieselbe Antwort, ohne Vision.

### 4.5 Das Geschaeftsmodell selbst

**Unbequeme Frage:** Warum ueberhaupt heyPiggy? heyPiggy ist ein Long-Tail-
Panel-Aggregator mit niedrigen EUR/min-Werten und harten Anti-Bot-Massnahmen
ueber die Subprovider (PureSpectrum, Dynata). Der Worker hat in zwei Wochen
0 EUR verdient — das deutet darauf hin, dass die Plattform pro Stunde menschen-
arbeit selbst fuer Menschen knapp bei <2 EUR liegt.

Das Konstrukt **"automatisierter Survey-Worker"** verdient nur Geld, wenn:

- die Stueckkosten pro Survey **deutlich unter** der Auszahlung liegen
  (siehe 4.4),
- der Worker mehrere Konten parallel betreiben kann (Anti-Bot-Risiko +
  ToS-Risiko),
- die Auszahlungsschwellen erreicht werden (oft 5–10 EUR Mindestauszahlung).

**Empfehlung als CEO:** vor weiteren Investitionen einen Wirtschaftlichkeits-
Check ansetzen. Wenn die Math nicht aufgeht, ist die heyPiggy-Spezifik der
falsche Anker — der Worker sollte als allgemeines OpenSIN-Vision-Subsystem
positioniert werden, das **B2B-Use-Cases** bedient (z.B. interne QA-
Automatisierung, accessibility-aware E2E-Tests). Das ist verkaufbar.

---

## 5. Was diese Iteration konkret liefert

Mit dem zugehoerigen Commit:

- **`docs/CEO-AUDIT.md`** (dieses Dokument).
- **`docs/ISSUE-VERIFICATION.md`** — pro geschlossenem Issue die ehrliche
  Beweiskette: wirklich gefixt, halbgar, oder nur kosmetisch zugemacht.
- **`answer_router.py` + `tests/test_answer_router.py`** — schliesst Issue #81
  als ECHTER Router, nicht als Prompt-Hint.
- **Hardening von `SKIP_PREFLIGHT`** — Bypass nur in expliziten dev/test/CI-Modi.
- **`docs/RUNBOOK.md`** — Eine Source of Truth fuer "wie starte ich das".
- **`docs/HARDENING-BACKLOG.md`** — die nicht erledigten Issues #63/#64/#65
  ehrlich aufgelistet, statt sie als "done" zu fakturieren.
- **README-Korrektur** — die "99,9% Erfolgsrate"-Claims entfernt.

---

## 6. Empfehlungen fuer die naechsten 14 Tage

Reihenfolge wichtig:

1. **Tag 1–3:** Live-Canary-Setup. Manueller Run pro Tag bis erstes EUR > 0.
2. **Tag 3–5:** Fail-Klassifizierung der Canary-Runs in einer einzigen
   Tabelle. Top-3 Fail-Klassen werden zu fokussierten Tickets.
3. **Tag 5–8:** Schnellpfad-ohne-Vision (siehe 4.4) — der einzige Hebel mit
   direktem Margenimpact.
4. **Tag 8–11:** Monolith-Splittung Schritt 1 (siehe 4.2).
5. **Tag 11–14:** Doppelte-Worker-Entscheidung (siehe 4.3).

Wenn nach 14 Tagen kein wiederholbarer EUR > 0 Run existiert, ist die
heyPiggy-Spezifik aufzugeben (siehe 4.5).

---

_Audit erstellt durch automatischen CEO-Review mit vollstaendigem Repo-Scan.
Nicht beschoenigt. Bei Widerspruch: dieselben Daten, andere Wertung._
