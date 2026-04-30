# banned.md — Verbotene Patterns & Anti-Architektur

## ❌ Verboten
1. **Chrome DevTools Protocol (CDP)** — Direkter DOM-Zugriff über CDP
2. **Chrome Extensions** — Keine Bridge/Extension für Browser-Kommunikation
3. **DOM-Manipulation** — Kein `document.querySelector`, `element.click()` etc.
4. **Cursor-Stealing** — Kein `CGEventPost` auf System-Cursor
5. **Unverschlüsselte Credentials** — Keine Plain-Text-Passwörter in Logs/Code
6. **Globale State-Speicherung** — Kein Shared-Mutable-State zwischen Runs

## ✅ Erlaubt (Stealth Triade)
1. **skylight-cli** — Screenshot via SkyLight.framework, CGEventPostToPid
2. **playstealth-cli** — Browser-Start mit Fingerprint-Schutz
3. **unmask-cli** — Stealth-Verification und Bot-Detection
4. **cua-driver** — Fallback-MVP (gleiche SkyLight-API)
5. **Cloudflare Llama 4 Scout** — Vision-LLM via Workers AI

## Architektur-Prinzipien
- Jede Aktion ist atomar und in JSON-Trace gespeichert
- Crash bei Frage 7 = Resume bei Frage 7 (nicht Neustart)
- Kein DOM-Zugriff, kein MCP-Server, kein Daemon
