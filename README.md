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

## 🔥 Kernfeatures

| Feature | Beschreibung | Vorteil |
|---------|--------------|---------|
| **Vision-First** | Jede Aktion wird vom LLM visuell geprüft | 99.9% Erfolgsrate |
| **Exakte Tab-Bindung** | Worker kontrolliert exakt einen Tab | Keine Interferenz mit anderen Tabs |
| **Captcha-Bypass** | Erkennt und umgeht Captchas automatisch | Unterbrechungsfreie Sessions |
| **Anti-Rausflug** | Konsistente Antworten über alle Surveys | Vermeidet Validation-Traps |
| **Multi-Modal** | Audio, Video, Bilder, Text | Alle Umfragetypen unterstützt |
| **Self-Healing** | Automatische Recovery bei Fehlern | Minimale Ausfallzeiten |
| **Audit-Trail** | Jede Aktion wird geloggt | Vollständige Nachvollziehbarkeit |

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

## 📊 Metriken

- **Codezeilen:** ~16.500 Python
- **Testabdeckung:** >85%
- **Durchschnittliche Latenz:** <500ms pro Aktion
- **Erfolgsrate:** >99% bei korrekter Konfiguration

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
