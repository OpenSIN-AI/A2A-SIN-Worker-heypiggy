# AI Backend Strategy — Vercel AI Gateway primary, Puter optional fallback

> Stand 2026-04-28. Ehrliche Bewertung.

## 1. Frage des Users (wörtlich)

> "macht es nicht sinn statt nvidia oder andere modelle via api, stattdessen
> lieber free puter ai zu integrieren? das ist doch viel schneller viel besser
> und unendlich kostenlos?"

## 2. Antwort, kurz

**Nein. Puter ist NICHT der richtige Primary-Backend für diesen Worker.**

Aber: Puter hat eine sinnvolle, kleine Rolle als optionaler Fallback / Cost-
Experiment-Lane. Begründung folgt — mit Quellen, nicht mit Bauchgefühl.

## 3. Was Puter wirklich ist

Aus den offiziellen Docs (`docs.puter.com`, abgerufen 2026-04-28):

- Puter.js ist ein **Frontend-JS-SDK** (`<script src="https://js.puter.com/v2/">`)
  das LLM-Calls von einer **Browser-Session des Endbenutzers** an
  Drittanbieter (OpenAI, Anthropic, Google, xAI, Mistral, DeepSeek, OpenRouter)
  proxied.
- Geschäftsmodell: **"User-Pays Model"** — _jeder Endbenutzer zahlt seine
  eigenen AI-Kosten über sein Puter.com-Konto_. Zitat aus `docs.puter.com/user-pays-model/`:
  > "Your users cover their own cloud and AI usage."
- Authentifizierung läuft über `puter.auth.signIn()` — also über einen
  Browser-Popup mit Endbenutzer-Interaktion.
- Es gibt seit 2026 einen "Node.js Workers" Pfad — aber auch der setzt einen
  _signed-in Puter user_ voraus.

## 4. Warum Puter im Headless-Earnings-Worker scheitert

| Problem                        | Konsequenz                                                                                                                                                                                                                                                                                            |
| ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Kein interaktiver End-User** | Unser Worker läuft headless ohne Mensch. Es gibt niemanden der "seine eigenen AI-Kosten zahlt". Wir müssten _einen_ Puter-Account dauerhaft authentifiziert halten — der dann auch unsere Rechnung zahlt. Das ist nicht "kostenlos und unendlich", das ist **ein Account mit fragiler Auth-Session**. |
| **Latenz**                     | Puter ist ein Proxy: `Worker → Puter-Edge → Vendor → Puter-Edge → Worker`. Das ist NICHT schneller als ein direkter Vendor-Call. Puter wirbt nirgends mit Sub-Sekunden-Latenz. Bei einem Vision-Call der pro Step >1s kostet, ist jeder zusätzliche Hop spürbar.                                      |
| **Auth-Drift mid-session**     | Puter-Session läuft über ein Cookie / Token mit unbekannter TTL. Wenn die Session während eines Survey-Runs ausläuft, bricht der Run mitten drin ab. Das ist exakt der "halbherzig"-Failmode den wir vermeiden wollen.                                                                                |
| **ToS-Risiko**                 | Puter behält sich vor "Anti-Abuse"-Maßnahmen. Ein Worker der pro Tag tausende Vision-Calls über _einen_ Account fährt sieht aus wie Abuse — auch wenn er es nicht ist. Account-Sperre = Worker offline.                                                                                               |
| **Audit-Trail**                | Unser Worker loggt pro Vision-Call: Provider, Model, Latency, Token-Usage, Run-ID. Über Puter geht Token-Usage und Vendor-ID nicht zuverlässig zurück. Wir verlieren die Hälfte unserer Operations-Telemetry.                                                                                         |
| **Vendor-Lock-In**             | Mit Puter committen wir uns auf **Puter** — nicht auf einen LLM-Vendor. Wenn Puter morgen Pricing einführt oder pivoted, sind alle unsere Calls plötzlich teuer oder weg.                                                                                                                             |
| **Ki-Modell-Auswahl**          | Puter wirbt mit "500+ Models". Realistisch sind das die gleichen Modelle die direkt verfügbar sind, mit zusätzlichem Hop. Es gibt **kein** Vision-Modell auf Puter das nicht auch direkt erhältlich ist.                                                                                              |

## 5. Was wir stattdessen nehmen — und warum

### 5.1 Primary: **Vercel AI Gateway**

Quelle: `vercel.com/ai-gateway`, AI-SDK 6 Doku (`sdk.vercel.ai`).

| Feature                                                                                        | Status                                                                                         |
| ---------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Single API-Key, alle großen Vendors (OpenAI, Anthropic, Google Vertex, AWS Bedrock, Fireworks) | ✅ zero config                                                                                 |
| Vision-Modelle (multimodal)                                                                    | ✅ alle relevanten — `openai/gpt-5-mini`, `anthropic/claude-opus-4.6`, `google/gemini-3-flash` |
| Native Vercel-Integration                                                                      | ✅ — wir laufen ohnehin auf Vercel                                                             |
| Caching, Rate-Limit-Kontrolle, Logs                                                            | ✅ in der Plattform                                                                            |
| Failover zwischen Vendors                                                                      | ✅                                                                                             |
| Streaming, Function-Calling, Image-In                                                          | ✅                                                                                             |
| Audit-Trail (Token-Usage, Latency, Vendor)                                                     | ✅ pro Call                                                                                    |

Kosten: pay-as-you-go pro Vendor, Free-Tier-Quotas existieren. Genau das was
ein professioneller Earnings-Worker braucht.

### 5.2 Cost-Experiment-Lane: **`openai/gpt-oss-120b`** über AI Gateway

Open-source GPT-Modell, deutlich günstiger als gpt-5-mini, ausreichend für
80% der Survey-Antworten (Single/Multi/Likert). Vision-Tasks bleiben beim
großen Modell.

### 5.3 Optionaler Fallback: **Puter** (hinter einem Feature-Flag)

Sinnvoll genau dann wenn:

- Wir eine **HeyPiggy-Webview** für menschliche Nutzer bauen (dann zahlt der
  Mensch wirklich seine eigene AI-Nutzung — Puter passt perfekt).
- Wir AI Gateway Free-Tier-Quota für non-critical Tasks (z.B. Trap-
  Klassifikation in Side-Path) sparen wollen.

Aber: **NICHT als Primary-Backend für den Vision-Loop**.

## 6. Konkrete Backend-Selektor-Logik

```python
# worker/ai/backend.py
class AIBackendSelector:
    """
    Wählt pro Call das beste Backend basierend auf:
      - Task-Kategorie (vision_critical, text_routing, trap_check, ...)
      - Konfigurations-Profil (production, staging, cost_experiment)
      - Health der einzelnen Backends
    """

    BACKENDS = {
        "ai_gateway":    {"vision": True,  "cost": "med", "latency": "low"},
        "ai_gateway_oss":{"vision": False, "cost": "low", "latency": "low"},
        "puter":         {"vision": True,  "cost": "free*","latency": "med"},
    }
    # *cost = "free" only when end-user-bound; for headless workers it is
    #         effectively pay-with-account-fragility.
```

Die Logik ist bewusst trivial. Wenn AI Gateway healthy ist, geht der Vision-
Call dorthin. Punkt.

## 7. Migrations-Schritte

Siehe [`04-MIGRATION-ROADMAP.md`](./04-MIGRATION-ROADMAP.md) Phase 1.

Kurz: existierende `vision_*` Calls bekommen ein Adapter-Interface, dann
wird der eine konkrete Implementierung (`AIGatewayBackend`) gegen die
heutigen direkten Calls ausgetauscht. Puter wird **nicht** in Phase 1
integriert — erst wenn AI Gateway stabil läuft und es einen klaren
geschäftlichen Grund für einen Fallback gibt.

## 8. Was wir NICHT machen

- ❌ "Alles über Puter und billig". Begründet siehe oben.
- ❌ "NVIDIA NIM / DGX als Primary". Macht für einen Survey-Worker keinen Sinn,
  Latenz und Setup-Komplexität sind nicht gerechtfertigt.
- ❌ Mehrere Primary-Backends gleichzeitig. **Ein** primary, einer optional.
- ❌ Eigenes Modell-Hosting. Reine Infrastruktur-Beschäftigungstherapie.
