---
name: Productization Sprint
about: 10-Tage Produktisierungs-Roadmap — Login → Survey → Balance stabil machen
title: "[SPRINT] Productization Sprint (10 Tage)"
labels: sprint, p0, productization
assignees: ""
---

## 🧩 MASTER ISSUE: Productization Sprint

**Ziel:** Login → Survey → Completion → Balance-Check stabil, beobachtbar und reproduzierbar machen.

### Referenzen
- `MASTER-PLAN-2026-05-02.md`
- `ROADMAP-10-DAY-2026-05-02.md`

### Subissues (Child Issues)

- [ ] **[SR-01]** Stabilitätsbaseline und Erfolgsmetriken definieren
- [ ] **[SR-02]** Command-Reliability für kritische Aktionen härten
- [ ] **[SR-03]** End-to-End-Flow schließen: Login → Survey → Completion → Balance
- [ ] **[SR-04]** Recovery-Layer mit Retry/Backoff/Snapshots bauen
- [ ] **[SR-05]** Observability mit Logs, Metriken und Alerts ergänzen
- [ ] **[SR-06]** Minimalen Produkt-Shell bauen: Start / Stop / Status
- [ ] **[SR-07]** Queue, Session-Isolation und Skalierung vorbereiten
- [ ] **[SR-08]** Quality Gates und Smoke-Tests für Core-Steps ergänzen
- [ ] **[SR-09]** Adoption Pack: Quickstart, Known Issues, Troubleshooting
- [ ] **[SR-10]** Release-Readiness Review mit Go/No-Go durchführen

### Definition of Done
- Core-Steps schlagen zuverlässig an
- Fehler werden automatisch erkannt und abgefangen
- Status ist jederzeit sichtbar
- neue Läufe starten ohne Codeänderung
- Balance-Check bestätigt den Erfolg

### KPI Targets
| KPI | Ziel |
|---|---:|
| Full-flow success rate | 90%+ |
| Recovery success rate | 80%+ |
| Time-to-first-success | < 15 min |
| Manual intervention rate | < 10% |
| Observability coverage | 100% critical paths |

### Risiken
| Risiko | Impact | Mitigation |
|---|---|---|
| Vision model variability | high | validation + capped retries |
| Popup drift | high | TRIO isolation + fallback |
| Session flakiness | high | snapshots + recovery |
| Scale collisions | medium | queue + isolation |
| Poor UX | high | product shell + onboarding |

---
**Canonical Reading Order:** EXEC-1PAGER → MASTER-PLAN → ROADMAP-10-DAY → PLAN-TECH → PLAN-SOTA
