# goal.md — A2A-SIN-Worker-heypiggy (Updated 2026-05-01)

## Primärziel
Automatisierte, unsichtbare Umfrage-Teilnahme auf HeyPiggy.com mit maximalem Stealth-Level.
**Erster EUR > 0 Beweis ist das einzige Ziel das zählt.**

## SOTA Critical Path (2026-05-01)
Siehe `docs/sota-plans/` für vollständige Pläne mit PERT-Schätzungen, Dependency-DAGs und Risk-Registern.

| Priorität | Plan | Issue |
|-----------|------|-------|
| 🔴 P0 | BFG Credential Purge (.env aus Git-History) | [#168](https://github.com/OpenSIN-AI/A2A-SIN-Worker-heypiggy/issues/168) |
| 🔴 P0 | Monolith Split (9.137 → <500 LOC) | [#169](https://github.com/OpenSIN-AI/A2A-SIN-Worker-heypiggy/issues/169) |
| 🔴 P0 | Live EUR Canary (3× EUR > 0) | [#170](https://github.com/OpenSIN-AI/A2A-SIN-Worker-heypiggy/issues/170) |
| 🟡 P1 | screen-follow Tests (0→20+) | SIN-CLIs/screen-follow#5 |
| 🟡 P1 | skylight-cli Tests (1→15+) | SIN-CLIs/skylight-cli#77 |
| 🟡 P1 | PyPI Release playstealth-cli | SIN-CLIs/playstealth-cli#75 |
| 🔵 P2 | Multi-Account Support | [#171](https://github.com/OpenSIN-AI/A2A-SIN-Worker-heypiggy/issues/171) |

## OKRs Q2 2026 (Updated)
1. ✅ Vision-free Fast Path implementiert (DOM + Answer-Router)
2. ✅ CreepJS CI Gate bei 80% aktiv
3. ✅ Cross-Repo Integration (alle 4 CLIs orchestriert)
4. 🔴 **ERSTER EUR > 0 auf heypiggy.com — noch nicht erreicht**
5. 🔴 Credential Security Breach behoben (BFG Repo-Cleaner)
6. 🔴 Monolith von 9.137 auf <500 Zeilen reduziert
7. 🟡 PyPI Release: `pip install playstealth-cli` möglich
8. 🟡 Test Coverage: screen-follow ≥ 20 Tests, skylight-cli ≥ 15 Tests

## Architekturziel
Vollständige, getestete, und dokumentierte Stealth-Quad:
```
playstealth-cli (HIDE) → skylight-cli (ACT) → unmask-cli (SENSE) → screen-follow (RECORD)
                    ↘───stealth-runner (ORCHESTRATE)───↙
                                         ↓
                    A2A-SIN-Worker-heypiggy (APPLICATION)
