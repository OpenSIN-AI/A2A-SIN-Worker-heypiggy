# A2A-SIN-Worker-heyPiggy

**Vision-Gate Worker für OpenSIN AI Agent System**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![OpenSIN](https://img.shields.io/badge/OpenSIN-AI%20Agent%20System-green)](https://github.com/OpenSIN-AI)

## 🎯 Zweck

Dieser Worker ist die **visuelle Intelligenz** des OpenSIN-Systems. Er verbindet sich mit der OpenSIN-Bridge (Chrome Extension) und führt **jede Aktion unter visueller Kontrolle eines Vision-LLMs** aus. Keine Aktion wird blind ausgeführt – jeder Klick, jede Eingabe wird vorher analysiert und nachher verifiziert.

```
┌─────────────────────────────────────────────────────────────────┐
│                    OpenSIN AI Ökosystem                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │ Global Brain │────▶│   Bridge     │────▶│  HeyPiggy    │   │
│  │  (Zentrale)  │     │ (Extension)  │     │   Worker     │   │
│  └──────────────┘     └──────────────┘     └──────────────┘   │
│         │                   │                   │              │
│         ▼                   ▼                   ▼              │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │  Strategie   │     │  DOM + CDP  │     │ Vision LLM   │   │
│  │  Koordination│     │  Steuerung  │     │  Verifikation│   │
│  └──────────────┘     └──────────────┘     └──────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Status

> **Ehrliche Bestandsaufnahme (siehe [docs/CEO-AUDIT.md](./docs/CEO-AUDIT.md)).**
> Der Worker ist eine seriöse, vision-first Automatisierungs-Pipeline mit
> rund 17 KLOC Python und einer breiten Testbasis. Er ist **nicht** "fertig":
> die Answer-Loop ist jetzt persistenter dank Answer-History/Anti-Learn,
> der Earnings-Pfad auf heypiggy.com ist noch nicht reproduzierbar, und mehrere Closed-
> Issues hatten zum Schliess-Zeitpunkt keinen verifizierten Code-Pfad. Diese
> Punkte sind in [docs/ISSUE-VERIFICATION.md](./docs/ISSUE-VERIFICATION.md)
> dokumentiert und in [docs/HARDENING-BACKLOG.md](./docs/HARDENING-BACKLOG.md)
> priorisiert.

## Kernfeatures

| Feature | Beschreibung |
|---------|--------------|
| **Vision-First** | Jede mutierende Aktion (Klick/Type/Navigate) läuft durch einen Vision-LLM-Gate-Call. Es gibt keine blinde DOM-Selektion. |
| **Exakte Tab-Bindung** | Der Worker kontrolliert genau einen Tab über die OpenSIN-Bridge. Keine Interferenz mit anderen Tabs. |
| **Panel-aware Routing** | Detektoren für PureSpectrum / Dynata / Sapio / Cint / Lucid + ein Answer-Router (`answer_router.py`) der pro Step Frage-Typ und Antwort-Strategie als Prompt-Block injiziert. |
| **Answer-History / Anti-Learn** | Fehloptionen werden persistiert (`answer_history.py`) und beim nächsten Schritt vermieden; wiederholte Fallen schalten auf Vision-Review statt Blind-Repeat. |
| **Attention/Trap-Detection** | Heuristiken für Attention-Checks, Konsistenz-Traps, Mindestlängen, Quota-/Disqualifikations-Banner. |
| **Multi-Modal** | Audio-/Video-/Bild-Fragen werden über Media-Router transkribiert/beschrieben und ins Vision-Prompt eingespeist. |
| **Self-Healing** | Bridge-Retries, Recovery-Pfade und ein Fail-Replay-Recorder; Recovery routet **nicht** auf Cashout/Giftcard (siehe Issue #84). |
| **Fail-Closed Preflight** | Der Worker startet keine Tab-Mutation, wenn Vision-Auth oder Pflicht-Env fehlt. `SKIP_PREFLIGHT=1` ist nur in `WORKER_ENV=development/test/ci` oder mit `WORKER_ALLOW_PREFLIGHT_SKIP=1` wirksam (siehe Issue #85). |
| **Audit-Trail** | Append-only JSONL Audit-Log, strukturierte Logs mit Run-ID-Korrelation, Secret-Redaction. |

## 📦 Installation

```bash
# Repository klonen
git clone https://github.com/OpenSIN-AI/A2A-SIN-Worker-heypiggy.git
cd A2A-SIN-Worker-heypiggy

# Virtuelle Umgebung erstellen
python -m venv venv
source venv/bin/activate  # Linux/Mac
# oder: venv\Scripts\activate  # Windows

# Abhängigkeiten installieren
pip install -r requirements.txt

# Konfiguration anpassen
cp .env.example .env
# Bearbeite .env mit deinen API-Keys
```

## 🚀 Schnellstart

```bash
# Worker-Umgebung prüfen
heypiggy-worker doctor

# Worker starten
heypiggy-worker run

# Oder mit Docker
docker-compose up -d
```

## 🏗️ Architektur

### Hauptkomponenten

1. **heypiggy_vision_worker.py** – Zentrale Steuerlogik
2. **media_router.py** – Multi-Modal Media Pipeline
3. **survey_orchestrator.py** – Survey Queue Management
4. **persona.py** – Persona-basierte Antwortgenerierung
5. **global_brain_client.py** – OpenSIN Global Brain Integration
6. **opensin_bridge/** – Bridge-Kommunikation
7. **worker/** – Worker Runtime Utilities

### Datenfluss

```
1. Global Brain sendet Ziel-URL
2. Worker öffnet exakt einen Tab (tabId wird gespeichert)
3. Vision-LLM analysiert Screenshot
4. Worker plant nächste Aktion
5. Bridge führt Aktion im Tab aus
6. Vision-LLM verifiziert Erfolg
7. Bei Fehler: Retry mit alternativer Strategie
8. Ergebnisse an Global Brain melden
```

## 📋 Dokumentation

- [AGENTS.md](./AGENTS.md) – Guide für KI-Agenten
- [CONTRIBUTING.md](./CONTRIBUTING.md) – Beiträge leisten
- [SECURITY.md](./SECURITY.md) – Sicherheitsrichtlinien
- [docs/](./docs/) – Technische Dokumentation

## 🔧 Konfiguration

Wichtige Umgebungsvariablen:

| Variable | Beschreibung | Beispiel |
|----------|--------------|----------|
| `NVIDIA_API_KEY` | NVIDIA NIM API Key | `nvapi-...` |
| `VISION_BACKEND` | Backend Auswahl | `auto`, `nvidia` |
| `BRIDGE_MCP_URL` | HTTP URL zur Bridge | `https://.../mcp` |
| `BRIDGE_HEALTH_URL` | Health-Endpoint der Bridge | `https://.../health` |
| `BRIDGE_ADAPTER` | Bridge-Modus (`legacy`/`opensin`) | `opensin` |
| `OPENSIN_BRIDGE_V2` | Opt-in Alias für V2-Adapter | `1` |
| `INFISICAL_AUTO_PULL` | Canonical Secrets automatisch laden | `1` |
| `PERSONA_FILE` | Pfad zur Persona-Datei | `profiles/jeremy.json` |

## 🧪 Tests

```bash
# Alle Tests ausführen
pytest tests/

# Mit Coverage
pytest --cov=. tests/
```

## Metriken (gemessen, nicht beworben)

- **Codezeilen:** ~17 KLOC Python (Monolith `heypiggy_vision_worker.py` ~9 KLOC + Module).
- **Testabdeckung:** Komponententests vorhanden für Worker-Runtime, Persona, Survey-Orchestrator, Panel-Overrides, Answer-Router, UI-State-Klassifizierer. Echte Coverage-Zahl wird über `pytest --cov` produziert — keine pauschale Behauptung.
- **Latenz pro Step:** abhängig von Vision-Backend. Zielwert <2s p50, hart abhängig von Provider-Latency.
- **Erfolgsrate:** Es gibt aktuell **keine produktive End-to-End-Erfolgsmetrik** mit Auszahlung auf heypiggy.com. Sobald die Earnings-Pipeline reproduzierbar grün ist, wird hier eine echte Zahl mit Messbedingungen stehen — und nur dann.

## 🔗 Integration ins OpenSIN-Ökosystem

Dieser Worker ist Teil des größeren OpenSIN AI Agent Systems:

- **[OpenSIN-Bridge](https://github.com/OpenSIN-AI/OpenSIN-Bridge)** – Chrome Extension für Browser-Automatisierung
- **[Infra-SIN-Global-Brain](https://github.com/OpenSIN-AI/Infra-SIN-Global-Brain)** – Zentrale Koordinationsstelle
- **[OpenSIN-overview](https://github.com/OpenSIN-AI/OpenSIN-overview)** – Gesamtübersicht aller Repos

## ⚠️ Wichtige Hinweise für Entwickler

1. **Keine blinden Änderungen:** Jede Datei ist ausführlich kommentiert. Lies die Kommentare bevor du änderst.
2. **Tab-Bindung respektieren:** Ändere nichts an der Tab-ID-Logik – das bricht die gesamte Isolation.
3. **Credentials schützen:** Passwörter werden NIEMALS an LLMs gesendet.
4. **Human-Delays beibehalten:** Zufällige Pausen sind kritisch für Anti-Bot-Schutz.
5. **Audit-Logs nicht deaktivieren:** Sie sind essenziell für Debugging und Compliance.

## 📝 Lizenz

MIT License – siehe [LICENSE](./LICENSE)

---

**OpenSIN AI Agent System** – Building the future of autonomous agents.
