# Earnings-Proof Pipeline — der Geld-Pfad

> Wenn dieser Plan nicht grün wird, ist alles andere Theater.

## 1. Warum dieser Plan existiert

Aus dem CEO-Audit (`docs/CEO-AUDIT.md`):

> "Es gibt aktuell keine produktive End-to-End-Erfolgsmetrik mit Auszahlung
> auf heypiggy.com."

Solange das so ist, ist der Worker Engineering-Übung, kein Produkt.

## 2. Was wir genau beweisen müssen

Eine **reproducible** Sequenz, die in einem dokumentierten 24h-Fenster diese
sechs Schritte produziert und in einem Artefakt-Bundle einreicht:

1. Worker startet, Persona ist geladen, Bridge ist healthy.
2. Worker öffnet die heypiggy-Survey-Liste.
3. Worker wählt mindestens **eine** Survey aus.
4. Worker durchläuft sie bis zum **Survey-Complete-Screen** (kein Disqualify,
   kein Quota-Voll, kein Trap-Fail).
5. Punkte werden im heypiggy-Dashboard sichtbar gutgeschrieben.
6. (Bonus): Auszahlungs-Schwelle erreicht und Cashout angestoßen.

Bewiesen wird das durch:

- Audit-Log mit `survey_completed` Event (run-id, panel, points, timestamp)
- Bridge-Trace + DOM-Snapshot vom Complete-Screen
- API-Response-Diff: `account.balance` vorher vs nachher
- Replay-Bundle (HAR + screenshots + JSONL events)

## 3. Was wir vor Phase 1 wissen MÜSSEN

Diese Fragen sind **rechtliche und geschäftliche** Themen, kein Engineering.

### 3.1 ToS-Klarheit

| Panel / Vermittler  | Erlaubt automatisierte Antworten?                | Belege                       |
| ------------------- | ------------------------------------------------ | ---------------------------- |
| heypiggy.com selbst | ❓ ToS-Auszug nötig                              | TODO                         |
| Cint                | ❌ generell verboten ("automated participation") | Cint Quality Policy          |
| Lucid (jetzt Cint)  | ❌                                               | Lucid Marketplace-AGB        |
| Dynata              | ❌                                               | Dynata Panel Code of Conduct |
| PureSpectrum        | ❌                                               | PureSpectrum Quality         |
| Sapio Research      | ❓ B2B fokussiert                                | TODO                         |

**Konsequenz:** Auch wenn heypiggy.com selbst Automation duldet — sobald der
Worker auf einen Cint/Lucid/Dynata/PureSpectrum-redirect landet, verstößt er
gegen deren ToS. Account-Bans sind **deren** Reaktion, nicht heypiggy-Bug.

**Aktion:** Vor Phase 1 muss klar sein, **welche Panels heypiggy bedient**
und welche davon explizit ihrerseits Automation tolerieren oder ignorieren.
Wenn die Antwort "keine" ist, ist das ein Geschäfts-, kein Engineering-Problem.

### 3.2 Account-Strategie

- **Single Account** der dauerhaft genutzt wird → hohes Ban-Risiko.
- **Multi Account** mit Persona-Rotation → ToS-Konflikt mit heypiggy
  (Multi-Account meist explizit verboten).
- **Test-Account in Sandbox** → falls heypiggy eine Sandbox bietet, muss die
  genutzt werden bevor der Live-Account angefasst wird.

**Aktion:** Vor Phase 1 muss die Account-Strategie schriftlich fixiert sein.
Nicht "wir probieren halt".

## 4. Definition of Done — Earnings-Smoke-Test

Ein einziger CI-Job, manuell triggerbar (`workflow_dispatch`), der:

1. Den Worker im Live-Mode gegen einen dedizierten Test-Account startet.
2. Maximal 90 Minuten läuft.
3. Bei Erfolg ein Replay-Bundle nach `gh release` hängt mit:
   - `audit.jsonl`
   - `survey-complete.har`
   - `dashboard-balance-before.json`
   - `dashboard-balance-after.json`
   - Screenshots aller Surveycomplete-Screens.
4. Status in `BUSINESS-STATE.md` aktualisiert (eine kleine, neue Datei die der
   Single Source of Truth über "Verdienen wir Geld?" wird).

Wenn 5 aufeinanderfolgende Smoke-Runs grün sind: Phase 1 ist abgeschlossen.

Wenn nicht: keine Phase 2. Punkt.

## 5. Frühindikatoren die wir SOFORT messen können

Auch ohne erfolgreichen Smoke-Test können wir heute schon messen:

| Indikator                       | Datenquelle                      | Aktuell                     |
| ------------------------------- | -------------------------------- | --------------------------- |
| Surveys gestartet / 24h         | `audit.jsonl` `survey_started`   | ❓ unbekannt                |
| Surveys completed / 24h         | `audit.jsonl` `survey_completed` | ❓ unbekannt — vermutlich 0 |
| Häufigster Disqualify-Grund     | Audit `disq_reason`              | ❓ unbekannt                |
| Häufigster Trap-Hit             | `trap_detected`                  | ❓ unbekannt                |
| Vision-Calls / completed survey | Telemetry                        | ❓ unbekannt                |

**Action item:** kleines Script `scripts/earnings_telemetry.py` das diese fünf
Zahlen aus dem letzten 24h-Audit-Log zusammenzieht und nach `BUSINESS-STATE.md`
schreibt. Ohne diese Zahlen sind wir blind.

## 6. Was passiert wenn der Smoke-Test nicht grün wird

Drei mögliche Wahrheiten:

1. **Der Code reicht, aber die Panels banen uns.** Dann ist das ein Vertriebs-
   /Legal-Problem. Lösung: andere Panels suchen, B2B-Research-Pfade prüfen,
   eigene Direct-Connections aufbauen. **Code allein wird das nicht lösen.**
2. **Der Code reicht nicht.** Dann gehen wir zurück in den Hardening-Backlog
   und arbeiten gezielt an dem konkreten Failmode der gemessen wird.
3. **Das Geschäftsmodell heypiggy selbst funktioniert nicht für Bots.** Dann
   müssen wir das Produkt anders positionieren — z.B. als "human-assist tool"
   statt "earn-while-you-sleep agent".

In allen drei Fällen ist die nächste Aktion eine **Geschäfts-Entscheidung**,
nicht ein Refactor.
