# CMD 02: NVIDIA Vision (schnell — 512px Bild)

**Befehl (Shell one-liner):**
```bash
screencapture -x /tmp/step.png && sips -Z 512 /tmp/step.png --out /tmp/step_s.png && IMG=$(base64 -i /tmp/step_s.png) && curl -s --max-time 30 https://integrate.api.nvidia.com/v1/chat/completions \
  -H "Authorization: Bearer nvapi-YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"meta/llama-3.2-11b-vision-instruct\",\"messages\":[{\"role\":\"user\",\"content\":[{\"type\":\"text\",\"text\":\"DEIN PROMPT HIER\"},{\"type\":\"image_url\",\"image_url\":{\"url\":\"data:image/png;base64,$IMG\"}}]}],\"max_tokens\":50}"
```

**Beschreibung:** Screenshot → auf 512px verkleinern → NVIDIA Vision API (Llama 3.2 11B).
**Dauer:** <1 Sekunde für Netzwerk + Inferenz (184KB Bild).
**Wichtig:** Immer auf 512px verkleinern! 1920px-Fullscreen = 500KB+ = 45s Timeout.

**Prompt für Survey-Koordinaten:**
```
Find center pixel coords of first survey button. Answer ONLY: X=NUM Y=NUM
```

**Abhängigkeiten:** NVIDIA_API_KEY (nvapi-...), curl, sips (macOS)

**Modelle (Stand 28.4.2026):**
- ✅ `meta/llama-3.2-11b-vision-instruct` — FREE, ~1s, 11B
- ✅ `meta/llama-3.2-90b-vision-instruct` — FREE, langsamer, 90B
- ❌ Phi-3.5-vision — EOL 15.4.2026
- ❌ Mistral Small 3.1 — EOL 15.4.2026
- ❌ Phi-4-multimodal — DEGRADED
