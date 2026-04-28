# CMD 03: Puter.js — Status & Limitations (28.4.2026)

**Pricing:** 100% FREE für Entwickler (User-Pays-Model). Endnutzer zahlen ihre eigene Nutzung. Free-Tier deckt grundlegende `gpt-5.4-nano` Vision-Calls ab.

**Auth:** Token via `getAuthToken()` erfolgreich erhalten (JWT, gültig). Im Browser funktioniert alles.

**Shell/CLI-Integration:**
- ❌ Node.js SDK (`init(authToken)`) crasht mit `RangeError: Maximum call stack size exceeded` (WebSocket-Bug)
- ❌ REST API (`api.puter.com/ai/chat`) returns "Forbidden"
- ✅ Browser SDK funktioniert einwandfrei mit `<script src="https://js.puter.com/v2/">`

**Fazit:** Puter für Browser-Tools nutzbar. Für Shell-basierte Survey-Steuerung NICHT geeignet.
**Alternative:** NVIDIA Vision API via curl — <1s mit 512px Bildern, funktioniert zuverlässig.

**Nützliche Puter-Features (Browser-only):**
- `puter.ai.chat(prompt, image, {model:"gpt-5.4-nano"})` — Vision
- `puter.ai.img2txt(image)` — OCR
- `puter.fs.write/read` — Cloud Storage (free)
- `puter.kv.set/get` — Key-Value DB (free)
