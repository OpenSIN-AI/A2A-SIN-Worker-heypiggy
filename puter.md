# Puter.md — Bild/Video-Generierung über Puter.js (100% FREE)

> **Methode:** Lokaler HTTP-Server + Browser → Puter.js API
> **Grund:** Puter.js funktioniert NICHT mit `file://` Protokoll und NICHT im Node.js CLI.
> **Lösung:** Python HTTP-Server + HTML-Datei im Browser öffnen.

## Setup (einmalig)

```bash
# HTTP-Server starten (im Hintergrund)
cd /tmp && python3 -m http.server 8765 &
```

## Bild generieren

```bash
# HTML-Datei erstellen
cat > /tmp/puter_img.html << 'EOF'
<!DOCTYPE html><html><body>
<script src="https://js.puter.com/v2/"></script>
<div id="status">⏳ Generiere...</div>
<script>
(async () => {
  try {
    const img = await puter.ai.txt2img("DEIN PROMPT HIER");
    document.body.appendChild(img);
    document.getElementById("status").textContent = "✅ Fertig!";
  } catch(e) {
    document.getElementById("status").textContent = "❌ " + e.message;
  }
})();
</script>
</body></html>
EOF

# Im Browser öffnen
open http://localhost:8765/puter_img.html
```

## Video generieren

```bash
cat > /tmp/puter_vid.html << 'EOF'
<!DOCTYPE html><html><body>
<script src="https://js.puter.com/v2/"></script>
<div id="status">⏳ Generiere Video...</div>
<script>
(async () => {
  try {
    const vid = await puter.ai.txt2vid("DEIN PROMPT HIER");
    document.body.appendChild(vid);
    document.getElementById("status").textContent = "✅ Video fertig!";
  } catch(e) {
    document.getElementById("status").textContent = "❌ " + e.message;
  }
})();
</script>
</body></html>
EOF

open http://localhost:8765/puter_vid.html
```

## Image-to-Image (Bild als Input)

```bash
# Erst Bild in /tmp/ speichern, dann:
cat > /tmp/puter_i2i.html << 'EOF'
<!DOCTYPE html><html><body>
<img id="input" src="input.png" style="display:none">
<script src="https://js.puter.com/v2/"></script>
<div id="status">⏳ Variiere Bild...</div>
<script>
(async () => {
  try {
    const img = await puter.ai.txt2img("Make this more colorful", 
      document.getElementById("input").src);
    document.body.appendChild(img);
    document.getElementById("status").textContent = "✅ Fertig!";
  } catch(e) {
    document.getElementById("status").textContent = "❌ " + e.message;
  }
})();
</script>
</body></html>
EOF
```

## Puter-Modelle (Bild/Video)

| Modell | Typ | Verfügbar via |
|--------|-----|--------------|
| `gpt-5.4-nano` | Text+Vision | `puter.ai.chat()` |
| `claude-sonnet-4-5` | Text | `puter.ai.chat()` |
| `google/gemini-2.5-flash` | Text+Vision | `puter.ai.chat()` |
| `z-ai/glm-5v-turbo` | GUI-Grounding | `puter.ai.chat()` |
| **txt2img** (Standard) | Bild | `puter.ai.txt2img()` |
| **txt2vid** (Standard) | Video | `puter.ai.txt2vid()` |
| **img2txt (OCR)** | Text-aus-Bild | `puter.ai.img2txt()` |
| **speech2txt** | Sprache→Text | `puter.ai.speech2txt()` |
| **txt2speech** | Text→Sprache | `puter.ai.txt2speech()` |

**ALLE 100% KOSTENLOS** (User-Pays-Model — Puter-Nutzer zahlen ihre eigene Nutzung).
