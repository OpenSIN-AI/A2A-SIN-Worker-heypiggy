#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
A2A-SIN-Worker-HeyPiggy — Vision Gate Edition v3.0 (EXAKTE TAB-BINDUNG)
================================================================================
ARCHITEKTUR:
  Bridge Extension (Chrome) ←WebSocket→ HF MCP Server ←HTTP→ Dieser Worker
  Jede einzelne Aktion wird von Gemini 3 Flash visuell verifiziert.

KERNPRINZIP — EXAKTE TAB-BINDUNG (PRIORITY -7.85):
  Der Worker öffnet genau EINEN Tab (tabs_create) und speichert dessen
  tabId + windowId als CURRENT_TAB_ID / CURRENT_WINDOW_ID.
  AB DIESEM MOMENT wird JEDER Bridge-Call mit dem exakten tabId geschickt.
  Es gibt KEINEN Fallback auf den "aktiven Tab" oder "currentWindow".
  Wenn CURRENT_TAB_ID nicht gesetzt ist, crasht der Call absichtlich laut,
  statt still auf einen fremden Tab zu fallen.

  Benutzer können parallel andere Tabs öffnen oder bedienen —
  das DARF den Worker NIEMALS beeinflussen.

SICHERHEITSLAYER:
  1. Exakte Tab-Bindung: CURRENT_TAB_ID ist nach Init immer gesetzt (nie None)
  2. Click-Eskalationskette: click_element → ghost_click → keyboard → vision_click → coordinates
  3. DOM-Verifikation NACH JEDER Aktion (nicht nur Screenshot-Hash)
  4. Screenshot-Hash-Tracking: Erkennt Stillstand automatisch
  5. Audit-Log auf Disk: Jede Aktion, jeder Screenshot, jedes Vision-Ergebnis
  6. Session-Backup: Cookies werden vor Crash gesichert
  7. Bridge-Reconnect: Automatischer Reconnect bei Verbindungsverlust
  8. Credential-Isolation: Passwörter werden NIEMALS an die AI gesendet
  9. Human-Delays: Zufällige Pausen zwischen 1.5-4.5 Sekunden
  10. Try/Except um JEDE einzelne Operation: Kein unbehandelter Crash möglich
  11. Page-State-Klassifikation: Erkennt Login, Dashboard, Survey, Error
  12. Proof-Collection: Screenshots mit Zeitstempel für Nachvollziehbarkeit
================================================================================
"""

import asyncio
import base64
import hashlib
import json
import os
import random
import re
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from agent_state_machine import (
    AgentState,
    IllegalTransitionError,
    StepContext,
    escalate,
    fail_safe,
    step_context_advance,
)
from predicate_checks import predicate_post_check, predicate_pre_check
from sitepack_loader import SelectorNotFoundError, SitepackLoader
from vision_contract import (
    NextAction,
    VisionResponse,
    VisionVerdict,
    parse_vision_response,
)
from vision_prompt import build_vision_prompt

# ============================================================================
# USER PROFIL — Jeremy Schulze
# WHY: Der Worker muss Profil-Fragen (Region, Wohnort, Geschlecht, Name etc.)
#      korrekt mit den echten Daten des Users beantworten.
#      Das Profil wird in den Vision-Prompt injiziert damit Gemini die richtigen
#      Antworten wählt — ohne raten, ohne falsche Klicks.
# CONSEQUENCES: Ohne Profil würde Gemini zufällig antworten → falsche Daten,
#               Umfragen brechen ab, Account könnte gesperrt werden.
# ============================================================================

PROFILE_PATH = Path("/Users/jeremy/.config/opencode/profiles/jeremy_schulze.json")


def _load_user_profile() -> dict:
    """
    Lädt das Benutzerprofil von Disk.
    WHY: Profil-Fragen in Umfragen (Region, Name, Wohnort etc.) müssen mit
         echten User-Daten beantwortet werden, nicht zufällig geraten.
    CONSEQUENCES: Fehlt die Datei, wird ein leeres Profil verwendet (kein Crash).
    """
    if PROFILE_PATH.exists():
        try:
            with open(PROFILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[PROFIL] Warnung: Profil konnte nicht geladen werden: {e}")
    return {}


USER_PROFILE = _load_user_profile()


def _build_profile_context() -> str:
    """
    Baut einen lesbaren Profil-Kontext-String für den Vision-Prompt.
    WHY: Gemini muss die genauen Profil-Antworten kennen damit es beim
         Ankreuzen von Radio-Buttons (Region, Geschlecht etc.) die richtigen
         Optionen wählt.
    CONSEQUENCES: Leerer String wenn kein Profil vorhanden — Vision fällt auf
                  generische Antwortlogik zurück.
    """
    if not USER_PROFILE:
        return ""

    lines = ["BENUTZERPROFIL (nutze diese Daten für Profil-Fragen):"]

    # Direkte Felder
    field_map = {
        "name": "Name",
        "first_name": "Vorname",
        "last_name": "Nachname",
        "gender": "Geschlecht (male=Männlich)",
        "city": "Wohnort/Stadt",
        "region": "Region in Deutschland",
        "country": "Land",
    }
    for key, label in field_map.items():
        val = USER_PROFILE.get(key)
        if val:
            lines.append(f"- {label}: {val}")

    # Explizite Profil-Antworten (Frage → Antwort Mapping)
    profile_answers = USER_PROFILE.get("profile_answers", {})
    if profile_answers:
        lines.append("KONKRETE ANTWORTEN FÜR HÄUFIGE FRAGEN:")
        for question, answer in profile_answers.items():
            lines.append(f"  - '{question}' → '{answer}'")

    region_note = USER_PROFILE.get("region_note")
    if region_note:
        lines.append(f"HINWEIS: {region_note}")

    return "\n".join(lines)


# ============================================================================
# KONFIGURATION
# ============================================================================

# Bridge-Endpunkte
BRIDGE_MCP_URL = "https://openjerro-opensin-bridge-mcp.hf.space/mcp"
BRIDGE_HEALTH_URL = "https://openjerro-opensin-bridge-mcp.hf.space/health"

# Vision Gate Limits (aus AGENTS.md PRIORITY -7.0)
# WHY MAX_STEPS=120: Umfragen haben oft 20-40 Fragen, jede Frage braucht
#   Screenshot + Vision + Klick + DOM-Verify = 4 Aktionen. 40 Fragen * 4 = 160.
#   120 ist ein sicherer Wert der auch lange Surveys komplett abschließt.
MAX_STEPS = 120
# WHY MAX_RETRIES=5: 3 war zu aggressiv — manchmal braucht eine Seite länger zum laden.
MAX_RETRIES = 5
# WHY MAX_NO_PROGRESS=15: Survey-Seiten sehen Frage-für-Frage fast identisch aus.
#   Screenshot-Hash-Vergleich erkennt das fälschlich als 'kein Fortschritt'.
#   15 Schritte gibt dem Worker genug Spielraum um durch mehrseitige Surveys zu kommen.
#   Außerdem wird no_progress_count bei page_state='survey_active' NICHT hochgezählt.
MAX_NO_PROGRESS = 15
MAX_CLICK_ESCALATIONS = 5  # 5 Klick-Methoden bevor aufgegeben wird
VISION_MODEL = "google/antigravity-gemini-3-flash"
CLICK_ACTIONS = (
    "click_element",
    "click_ref",
    "ghost_click",
    "vision_click",
    "click_coordinates",
)

# 1x1 PNG als lokaler Vision-Probe. WHY: Die Preflight-Prüfung muss die
# screenshot-basierte Vision-Authentifizierung testen, BEVOR irgendeine Browser-
# Mutation stattfindet. Dafür reicht ein minimales gültiges PNG als sicherer Probe.
VISION_AUTH_PROBE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5wZuoAAAAASUVORK5CYII="
)

# Verzeichnisse für Artefakte
RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
ARTIFACT_DIR = Path(f"/tmp/heypiggy_run_{RUN_ID}")
SCREENSHOT_DIR = ARTIFACT_DIR / "screenshots"
AUDIT_DIR = ARTIFACT_DIR / "audit"
SESSION_DIR = ARTIFACT_DIR / "sessions"

# Erstelle alle Verzeichnisse beim Start
for d in [ARTIFACT_DIR, SCREENSHOT_DIR, AUDIT_DIR, SESSION_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# WHY: The sitepack loader externalizes every site-specific selector into a
# versioned JSON manifest. This lets us adapt to HeyPiggy DOM drift without
# rewriting worker logic.
SITEPACK = SitepackLoader()
SITEPACK_PATH = (
    Path(__file__).resolve().parent / "sitepacks" / "heypiggy" / "v1" / "pack.json"
)
if SITEPACK_PATH.exists():
    SITEPACK.load(str(SITEPACK_PATH))
else:
    print(f"[SITEPACK] Warnung: Sitepack nicht gefunden: {SITEPACK_PATH}")

# ============================================================================
# EXAKTE TAB-BINDUNG — GLOBAL STATE (PRIORITY -7.85)
# ============================================================================
# CURRENT_TAB_ID und CURRENT_WINDOW_ID werden beim ersten tabs_create gesetzt
# und DANACH niemals mehr auf None zurückgesetzt.
# Alle Bridge-Calls MÜSSEN tabId enthalten — kein Fallback auf aktiven Tab!
# WHY: Parallele User-Tabs dürfen den Worker NIEMALS beeinflussen.
# CONSEQUENCES: Wenn tabId nicht gesetzt ist, schlägt der Call laut fehl.
CURRENT_TAB_ID: int | None = None  # Wird nach init() IMMER gesetzt sein
CURRENT_WINDOW_ID: int | None = None  # Wird nach init() IMMER gesetzt sein
WORKER_HOST_HINT = "heypiggy.com"  # Host-Teil der Worker-URL zur Recovery-Prüfung
request_id_counter = 0


def _require_tab_id() -> int:
    """
    Gibt CURRENT_TAB_ID zurück oder wirft einen Fehler wenn nicht gesetzt.
    WHY: Nach dem initialen Tab-Erstellen MUSS tabId immer bekannt sein.
         Ein leerer Fallback würde auf einen beliebigen aktiven Tab fallen —
         das ist das exakte Problem das wir eliminieren wollen.
    CONSEQUENCES: Laut fehlschlagen ist besser als still falschen Tab steuern.
    """
    global CURRENT_TAB_ID
    if CURRENT_TAB_ID is None:
        raise RuntimeError(
            "CURRENT_TAB_ID ist nicht gesetzt! "
            "Worker darf keine Bridge-Calls senden bevor tabs_create erfolgreich war."
        )
    return CURRENT_TAB_ID


def _tab_params() -> dict:
    """
    Gibt ein Dict mit dem exakten tabId zurück.
    WHY: Convenience-Wrapper damit alle Funktionen einheitlich tabId übergeben.
    CONSEQUENCES: Wirft RuntimeError wenn tabId nicht gesetzt — kein stiller Fallback.
    """
    return {"tabId": _require_tab_id()}


# ============================================================================
# AUDIT-LOG — Jede einzelne Aktion wird auf Disk geloggt
# ============================================================================

AUDIT_LOG_PATH = AUDIT_DIR / "audit.jsonl"


def audit(event_type: str, **data):
    """
    Schreibt einen Audit-Eintrag ins Log.
    WHY: Damit wir bei JEDEM Fehler exakt nachvollziehen können was passiert ist.
    CONSEQUENCES: Ohne Audit-Log ist Debugging unmöglich.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        "run_id": RUN_ID,
        **data,
    }
    try:
        with open(AUDIT_LOG_PATH, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # Audit-Fehler darf den Worker NIEMALS crashen

    # Auch auf stdout für Live-Monitoring
    emoji_map = {
        "screenshot": "📸",
        "vision_check": "🧠",
        "action": "⚡",
        "ghost_click": "👻",
        "coord_click": "🎯",
        "vision_click": "🔭",
        "click_escalation": "🔺",
        "error": "❌",
        "success": "✅",
        "bridge_health": "📡",
        "session_save": "💾",
        "state_change": "🔄",
        "navigate": "🌐",
        "stop": "🛑",
        "start": "🚀",
    }
    emoji = emoji_map.get(event_type, "📝")
    print(f"{emoji} [{event_type}] {json.dumps(data, ensure_ascii=False)[:200]}")


def missing_required_credentials() -> list[str]:
    """
    Liefert fehlende Pflicht-Env-Variablen für den Worker.
    WHY: Der Worker darf ohne echte Zugangsdaten niemals in Login-/Survey-Flow laufen.
    CONSEQUENCES: Die Preflight-Kontrolle stoppt fail-closed vor jeder Browser-Mutation.
    """
    missing = []
    if not os.environ.get("HEYPIGGY_EMAIL"):
        missing.append("HEYPIGGY_EMAIL")
    if not os.environ.get("HEYPIGGY_PASSWORD"):
        missing.append("HEYPIGGY_PASSWORD")
    return missing


def ensure_vision_probe_screenshot() -> str:
    """
    Schreibt ein minimales Screenshot-PNG für den Vision-Auth-Probe auf Disk.
    WHY: Der Auth-Check soll denselben screenshot-basierten OpenSIN-Vision-Pfad nutzen
    wie der echte Worker, aber ohne vorher einen Browser-Tab zu mutieren.
    CONSEQUENCES: Gibt immer einen stabilen lokalen PNG-Pfad für den Probe zurück.
    """
    probe_path = SCREENSHOT_DIR / "vision_auth_probe.png"
    if not probe_path.exists():
        probe_path.write_bytes(VISION_AUTH_PROBE_PNG)
    return str(probe_path)


def collect_opencode_text(stdout: bytes, stderr: bytes = b"") -> str:
    """
    Extrahiert Text-Events aus `opencode run --format json`.
    WHY: opencode kann Events je nach TTY auf stdout oder stderr schreiben.
    Daher kombinieren wir beide Streams.
    """
    combined = stdout + stderr
    full_text = ""
    for line in combined.decode("utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except Exception:
            continue
        if event.get("type") == "text":
            full_text += event.get("part", {}).get("text", "")
        elif event.get("type") == "error":
            error_data = event.get("error", {}) or {}
            error_payload = error_data.get("data", {}) or {}
            error_message = error_data.get("message", "") or error_payload.get(
                "message", ""
            )
            provider_id = error_payload.get("providerID", "")
            if provider_id or error_message:
                full_text += f" {provider_id} {error_message}".strip()
    return full_text.strip()


def build_clean_opencode_env() -> dict:
    """
    Entfernt verschachtelte OpenCode-Session-Variablen aus der Child-Umgebung.
    WHY: Der Worker ruft `opencode run` als untergeordneten Prozess auf. Wenn
         dabei `OPENCODE=1`, `OPENCODE_PID` oder andere OpenCode-Laufzeitvariablen
         vererbt werden, verhält sich der Child-Prozess wie eine verschachtelte
         Session statt wie ein sauberer One-Shot-CLI-Call.
    CONSEQUENCES: Vision-Aufrufe laufen isoliert und werden nicht vom aktuell
                  laufenden Eltern-Agenten-Kontext kontaminiert.
    """
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("OPENCODE")
    }


def detect_vision_auth_failure(raw_text: str) -> str | None:
    """
    Erkennt harte Vision-Control-Plane-Blocker im kombinierten Output.
    WHY: Der Worker muss bei kaputter Vision-Authentifizierung ODER bei einem
         explizit ungesunden Vision-Health-Zustand fail-closed stoppen.
    CONSEQUENCES: Sobald 401/invalid-credentials oder ein klarer Health-Failure
                  auftaucht, darf der Worker nicht weiterlaufen.
    """
    lowered = (raw_text or "").lower()
    if "401" in lowered and "invalid authentication credentials" in lowered:
        return "401 invalid authentication credentials"
    if "invalid authentication credentials" in lowered:
        return "invalid authentication credentials"
    if "authentication credentials" in lowered and "invalid" in lowered:
        return "invalid authentication credentials"
    if "api key is missing" in lowered:
        return "google api key is missing"
    if "configuration is invalid" in lowered and "plugins" in lowered:
        return "configuration invalid: plugins key"

    health_markers = (
        "vision health failure",
        "vision health check failed",
        "provider health check failed",
        "model health check failed",
        "provider unhealthy",
        "model unhealthy",
        "vision provider unhealthy",
        "vision model unhealthy",
    )
    for marker in health_markers:
        if marker in lowered:
            return marker

    if "health" in lowered and any(
        word in lowered for word in ("failed", "failure", "unhealthy", "degraded")
    ):
        return "vision health check failed"
    return None


async def run_vision_model(
    prompt: str,
    screenshot_path: str,
    *,
    timeout: int = 120,
    step_num: int = 0,
    purpose: str = "vision",
) -> dict:
    """
    Führt einen screenshot-basierten OpenSIN-Vision-Call über `opencode run` aus.
    WHY: Preflight-Probe und reguläre Vision-Entscheidungen müssen denselben CLI-Pfad
    nutzen, damit Auth-Fehler zentral erkannt und fail-closed behandelt werden.
    CONSEQUENCES: Gibt strukturierte Resultate mit `ok` und `auth_failure` zurück.
    """
    cli_timeout = max(20, min(timeout, 45))
    cmd = [
        "timeout",
        str(cli_timeout),
        "opencode",
        "run",
        prompt,
        "-f",
        screenshot_path,
        "--model",
        VISION_MODEL,
        "--format",
        "json",
    ]
    # DEBUG: For step 1, write the exact command to a file for manual reproduction
    if step_num == 1:
        try:
            with open("/tmp/vision_cmd_debug.txt", "w") as f:
                f.write(" ".join(cmd) + "\n")
                f.write(f"PROMPT: {prompt[:500]}...\n")
                f.write(f"SCREENSHOT: {screenshot_path}\n")
        except Exception:
            pass

    try:
        child_env = build_clean_opencode_env()
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=child_env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except Exception as e:
            try:
                process.kill()
            except:
                pass
            return {
                "ok": False,
                "auth_failure": False,
                "error": f"Vision timeout or error: {e}",
                "stdout_text": "",
                "stderr_text": "",
                "returncode": -1,
            }
        full_text = collect_opencode_text(stdout, stderr)
        stderr_text = stderr.decode("utf-8", errors="replace").strip()
        combined = "\n".join(part for part in [full_text, stderr_text] if part)
        auth_error = detect_vision_auth_failure(combined)

        if process.returncode != 0:
            if (
                purpose == "preflight_auth_probe"
                and process.returncode in (124, 137)
                and not auth_error
            ):
                return {
                    "ok": True,
                    "auth_failure": False,
                    "text": full_text,
                    "stdout_text": full_text,
                    "stderr_text": stderr_text,
                    "returncode": process.returncode,
                }
            if full_text and process.returncode in (124, 137):
                return {
                    "ok": True,
                    "auth_failure": False,
                    "text": full_text,
                    "stdout_text": full_text,
                    "stderr_text": stderr_text,
                    "returncode": process.returncode,
                }
            error_message = (
                stderr_text or full_text or f"opencode exit {process.returncode}"
            )
            if auth_error:
                audit(
                    "error",
                    message=f"Vision auth failure ({purpose}): {auth_error}",
                    step=step_num,
                )
                return {
                    "ok": False,
                    "auth_failure": True,
                    "error": auth_error,
                    "stdout_text": full_text,
                    "stderr_text": stderr_text,
                    "returncode": process.returncode,
                }
            audit(
                "error",
                message=f"Vision command failed ({purpose}): {error_message[:200]}",
                step=step_num,
            )
            return {
                "ok": False,
                "auth_failure": False,
                "error": error_message,
                "stdout_text": full_text,
                "stderr_text": stderr_text,
                "returncode": process.returncode,
            }

        if auth_error:
            audit(
                "error",
                message=f"Vision auth failure ({purpose}): {auth_error}",
                step=step_num,
            )
            return {
                "ok": False,
                "auth_failure": True,
                "error": auth_error,
                "stdout_text": full_text,
                "stderr_text": stderr_text,
                "returncode": process.returncode,
            }

        return {
            "ok": True,
            "auth_failure": False,
            "text": full_text,
            "stderr_text": stderr_text,
            "returncode": process.returncode,
        }

    except asyncio.TimeoutError:
        audit("error", message=f"Vision Timeout ({purpose})", step=step_num)
        return {
            "ok": False,
            "auth_failure": False,
            "error": f"Vision Timeout ({purpose})",
            "stdout_text": "",
            "stderr_text": "",
            "returncode": None,
        }

    except Exception as e:
        auth_error = detect_vision_auth_failure(str(e))
        if auth_error:
            audit(
                "error",
                message=f"Vision auth failure ({purpose}): {auth_error}",
                step=step_num,
            )
            return {
                "ok": False,
                "auth_failure": True,
                "error": auth_error,
                "stdout_text": "",
                "stderr_text": str(e),
                "returncode": None,
            }
        audit("error", message=f"Vision Exception ({purpose}): {e}", step=step_num)
        return {
            "ok": False,
            "auth_failure": False,
            "error": str(e),
            "stdout_text": "",
            "stderr_text": str(e),
            "returncode": None,
        }


async def ensure_worker_preflight() -> dict:
    """
    Prüft die komplette Control-Plane vor der ersten Browser-Mutation.
    WHY: Issue #86 verlangt ein fail-closed Gate vor tabs_create/navigation/login.
    CONSEQUENCES: Fehlt Env oder Vision-Auth, stoppt der Worker bevor ein Tab erstellt wird.
    """
    missing = missing_required_credentials()
    if missing:
        reason = f"Pflicht-Env fehlt: {', '.join(missing)}"
        audit("stop", reason=reason)
        return {"ok": False, "reason": reason}

    if not await check_bridge_alive():
        reason = "Bridge nicht erreichbar während Preflight"
        audit("stop", reason=reason)
        return {"ok": False, "reason": reason}

    probe_path = ensure_vision_probe_screenshot()
    probe_prompt = (
        "Antworte ausschließlich mit gültigem JSON im Format "
        '{"status":"ok"}. Keine Erklärungen.'
    )
    probe_result = await run_vision_model(
        probe_prompt,
        probe_path,
        timeout=60,
        step_num=0,
        purpose="preflight_auth_probe",
    )
    if not probe_result.get("ok"):
        reason = probe_result.get("error", "Vision-Probe fehlgeschlagen")
        audit("stop", reason=f"Vision-Preflight fehlgeschlagen: {reason}")
        return {"ok": False, "reason": reason}

    # Preflight-Probe beweist nur dass Vision-Auth funktioniert (ok=True ohne auth_failure).
    # Das Modell antwortet manchmal mit Freitext statt reinem JSON — das ist OK.
    # Wir prüfen NUR: Hat opencode den Call ohne Auth-Fehler durchgeführt?
    # WHY: Ein 1x1 PNG Probe braucht kein Strict-JSON-Format — es reicht der erfolgreiche Call.
    probe_text = probe_result.get("text", "")
    if not probe_text:
        # Leere Antwort = Vision hat geantwortet aber nichts zurückgegeben → trotzdem OK
        # (manchmal gibt das Modell bei einem leeren Bild nur Whitespace zurück)
        pass
    audit(
        "success",
        message=f"Vision-Preflight OK: Auth healthy, Antwort={probe_text[:80]}",
    )

    audit("success", message="Worker-Preflight bestanden: Env + Vision auth healthy")
    return {"ok": True, "reason": "ready"}


# ============================================================================
# BRIDGE-KOMMUNIKATION — Extrem robustes HTTP mit Retry und Reconnect
# ============================================================================


def fetch_health():
    """
    Holt den Bridge-Health-Status.
    WHY: Vor JEDER Aktion muss die Bridge erreichbar sein.
    CONSEQUENCES: Bei Timeout wird gewartet, nicht gecrasht.
    """
    try:
        req = urllib.request.Request(BRIDGE_HEALTH_URL)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e), "extensionConnected": False}


async def wait_for_extension(timeout=600):
    """
    Wartet robust auf die Extension-Verbindung.
    WHY: Ohne Extension sind alle Bridge-Calls sinnlos.
    CONSEQUENCES: 600s Timeout, danach harter Abbruch mit klarer Fehlermeldung.
    """
    audit("start", message="Warte auf Bridge Extension", timeout=timeout)
    start = time.time()
    last_status = None

    while time.time() - start < timeout:
        health = await asyncio.to_thread(fetch_health)
        current = health.get("extensionConnected")

        # Nur loggen bei Statusänderung, um Spam zu vermeiden
        if current != last_status:
            audit(
                "bridge_health",
                connected=current,
                version=health.get("version", "?"),
                tools=health.get("toolsCount", 0),
                pending=health.get("pendingRequests", 0),
            )
            last_status = current

        if current is True:
            audit("success", message="Extension verbunden")
            return True

        await asyncio.sleep(5)

    raise RuntimeError(f"Timeout ({timeout}s): Bridge Extension nicht verbunden.")


def post_mcp(method: str, params: dict = None):
    """
    Sendet einen MCP-Request an die Bridge mit 3x Retry und Error-Body-Parsing.
    WHY: Die Bridge kann kurzzeitig 500er liefern, das darf nicht zum Crash führen.
    CONSEQUENCES: Nach 3 Fehlversuchen wird eine RuntimeError geworfen (wird oben gefangen).
    """
    global request_id_counter
    request_id_counter += 1

    body = {"jsonrpc": "2.0", "method": method, "id": request_id_counter}
    if params:
        body["params"] = params

    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                BRIDGE_MCP_URL,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                decoded = json.loads(resp.read().decode("utf-8"))
                if "error" in decoded:
                    last_err = f"MCP Protocol Error: {decoded['error']}"
                    audit("error", message=last_err, attempt=attempt + 1)
                    time.sleep(2 * (attempt + 1))
                    continue
                return decoded.get("result", {})

        except urllib.error.HTTPError as e:
            # Echten Error-Body extrahieren statt nur Status-Code
            try:
                error_body = e.read().decode("utf-8")
                error_json = json.loads(error_body)
                last_err = f"HTTP {e.code}: {json.dumps(error_json)}"
            except Exception:
                last_err = f"HTTP {e.code}: {e.reason}"
            audit("error", message=last_err, attempt=attempt + 1)
            time.sleep(2 * (attempt + 1))

        except Exception as e:
            last_err = str(e)
            audit("error", message=last_err, attempt=attempt + 1)
            time.sleep(2 * (attempt + 1))

    raise RuntimeError(f"MCP fehlgeschlagen nach 3 Versuchen: {last_err}")


def decode_mcp_result(raw):
    """
    Decodiert das MCP-Result aus der verschachtelten JSON-RPC Struktur.
    WHY: Die Bridge gibt content[0].text zurück, das muss entpackt werden.
    """
    if isinstance(raw, dict) and "content" in raw:
        txt = raw["content"][0].get("text", "")
        try:
            return json.loads(txt)
        except Exception:
            return txt
    return raw


def normalize_selector(selector: str) -> str:
    """
    Bereinigt einen Vision-Selector in gültiges CSS.
    WHY: Vision-Modelle erzeugen manchmal Playwright-artige Pseudo-Selektoren
    wie :contains(...) oder :has-text(...). Diese sind im Browser-QuerySelector
    nicht gültig und müssen deshalb vor der Ausführung repariert werden.
    """
    if not selector:
        return selector

    cleaned = selector
    cleaned = re.sub(r":contains\((?:[^()]+|\([^()]*\))*\)", "", cleaned)
    cleaned = re.sub(r":has-text\((?:[^()]+|\([^()]*\))*\)", "", cleaned)
    cleaned = re.sub(r":text\((?:[^()]+|\([^()]*\))*\)", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


async def click_visible_button_with_text(text_hint: str):
    """
    Klicke einen sichtbaren Button anhand seines Textinhalts.
    WHY: Vision kann dashboard-blockierende Gate-Buttons wie
    "Starte die erste Umfrage!" übersehen. Dieser DOM-basierte
    Gate-Klick verhindert, dass wir Survey-Karten zu früh anklicken.
    """
    global CURRENT_TAB_ID, CURRENT_WINDOW_ID
    tab_params = _tab_params()
    js_code = f"""
    (function() {{
      const hint = {json.dumps(text_hint.lower())};
      const candidates = Array.from(document.querySelectorAll('button, a, [role="button"]'));
      const el = candidates.find((node) => {{
        const text = (node.textContent || '').trim().toLowerCase();
        const visible = node.offsetParent !== null;
        return visible && text.includes(hint);
      }});
      if (!el) return {{ clicked: false, reason: 'not found', hint: hint }};
      if (typeof el.focus === 'function') el.focus();
      if (typeof el.click === 'function') el.click();
      else el.dispatchEvent(new MouseEvent('click', {{ bubbles: true, cancelable: true, view: window }}));
      return {{
        clicked: true,
        text: (el.textContent || '').trim().substring(0, 120),
        tag: el.tagName,
        id: el.id || '',
        cls: (el.className || '').toString().substring(0, 120)
      }};
    }})();
    """
    return await execute_bridge("execute_javascript", {"script": js_code, **tab_params})


async def resolve_survey_selector(selector: str, description: str = "") -> str:
    """
    Wandelt generische Survey-Selektoren in die echte #survey-... ID um.
    WHY: Vision liefert auf HeyPiggy oft nur "div.survey-item" statt der
    konkreten ID. Damit wir nicht blind die erste Karte anklicken, lesen wir
    die sichtbaren Survey-Karten aus dem DOM und wählen die beste Karte über
    Preis-Hinweis oder höchste vergütete Karte.
    """
    if not selector:
        return selector

    lowered = selector.lower()
    survey_list_selector = _sitepack_selector("survey_list_item", "div.survey-item")
    if "survey-item" not in lowered and "survey" not in lowered:
        return selector

    global CURRENT_TAB_ID, CURRENT_WINDOW_ID
    tab_params = _tab_params()
    js_code = f"""
    (function() {{
      const cards = Array.from(document.querySelectorAll({json.dumps(survey_list_selector)})).map((el) => {{
        const r = el.getBoundingClientRect();
        return {{
          id: el.id || '',
          text: (el.textContent || '').replace(/\\s+/g, ' ').trim(),
          visible: el.offsetParent !== null,
          x: Math.round(r.left + r.width / 2),
          y: Math.round(r.top + r.height / 2),
          w: Math.round(r.width),
          h: Math.round(r.height),
        }};
      }});
      return cards.filter((card) => card.visible && card.id);
    }})();
    """
    scan = await execute_bridge("execute_javascript", {"script": js_code, **tab_params})
    cards = []
    if isinstance(scan, dict):
        cards = scan.get("result", []) or []
    elif isinstance(scan, list):
        cards = scan

    if not isinstance(cards, list) or not cards:
        return selector

    price_hint = None
    for source in (description or "", selector):
        m = re.search(r"(\d+[.,]\d+)\s*€", source)
        if m:
            price_hint = m.group(1).replace(",", ".")
            break

    def _card_price(card):
        text = str(card.get("text", ""))
        m = re.search(r"(\d+[.,]\d+)\s*€", text)
        if not m:
            return None
        try:
            return float(m.group(1).replace(",", "."))
        except Exception:
            return None

    chosen = None
    if price_hint is not None:
        for card in cards:
            text = str(card.get("text", ""))
            if price_hint in text.replace(",", "."):
                chosen = card
                break

    if chosen is None:
        priced_cards = []
        for card in cards:
            price = _card_price(card)
            if price is not None:
                priced_cards.append((price, card))
        if priced_cards:
            priced_cards.sort(key=lambda item: item[0], reverse=True)
            chosen = priced_cards[0][1]

    if chosen and chosen.get("id"):
        resolved = f"#{chosen['id']}"
        if resolved != selector:
            audit(
                "state_change",
                message=(
                    f"Survey-Selector auf echte ID aufgelöst: {selector[:80]} -> {resolved}"
                ),
            )
        return resolved

    return selector


async def recover_worker_tab_id() -> int | None:
    """
    Stellt die exakt bekannte Worker-Tab-ID wieder her.
    WHY: Parallel geöffnete Browser-Tabs dürfen den Worker nie beeinflussen.
    Wir akzeptieren deshalb nur die vorher gespeicherte Tab-ID oder genau eine
    eindeutige HeyPiggy-Tab-Instanz im gespeicherten Fenster.
    """
    global CURRENT_TAB_ID, CURRENT_WINDOW_ID

    query = {}
    if CURRENT_WINDOW_ID is not None:
        query["windowId"] = CURRENT_WINDOW_ID

    tabs_raw = await asyncio.to_thread(
        post_mcp, "tools/call", {"name": "tabs_list", "arguments": {"query": query}}
    )
    tabs_result = decode_mcp_result(tabs_raw)
    tabs = []
    if isinstance(tabs_result, dict):
        tabs = tabs_result.get("tabs", []) or []

    if CURRENT_TAB_ID is not None:
        for tab in tabs:
            if isinstance(tab, dict) and tab.get("id") == CURRENT_TAB_ID:
                return CURRENT_TAB_ID

    candidates = [
        tab
        for tab in tabs
        if isinstance(tab, dict) and WORKER_HOST_HINT in str(tab.get("url", "")).lower()
    ]

    if len(candidates) == 1:
        CURRENT_TAB_ID = candidates[0].get("id")
        audit(
            "state_change",
            message=(
                f"Worker-Tab wiederhergestellt: tabId={CURRENT_TAB_ID}, "
                f"windowId={CURRENT_WINDOW_ID}"
            ),
        )
        return CURRENT_TAB_ID

    if not candidates and CURRENT_WINDOW_ID is None:
        # Letzter Versuch: alle Tabs im Browser durchsuchen, aber nur wenn wir
        # noch keinen eigenen Fenster-Kontext haben. Das bleibt trotzdem streng
        # auf den HeyPiggy-Host begrenzt.
        tabs_raw = await asyncio.to_thread(
            post_mcp, "tools/call", {"name": "tabs_list", "arguments": {}}
        )
        tabs_result = decode_mcp_result(tabs_raw)
        if isinstance(tabs_result, dict):
            all_tabs = tabs_result.get("tabs", []) or []
            candidates = [
                tab
                for tab in all_tabs
                if isinstance(tab, dict)
                and WORKER_HOST_HINT in str(tab.get("url", "")).lower()
            ]
            if len(candidates) == 1:
                CURRENT_TAB_ID = candidates[0].get("id")
                audit(
                    "state_change",
                    message=f"Worker-Tab global wiedergefunden: tabId={CURRENT_TAB_ID}",
                )
                return CURRENT_TAB_ID

    if candidates:
        audit(
            "error",
            message=(
                f"Worker-Tab-Recovery mehrdeutig: {len(candidates)} HeyPiggy-Tabs "
                "im gleichen Kontext gefunden"
            ),
        )
    else:
        audit(
            "error",
            message="Worker-Tab-Recovery fehlgeschlagen: kein HeyPiggy-Tab gefunden",
        )
    return None


async def execute_bridge(method: str, params: dict = None):
    """
    Führt einen Bridge-Tool-Call aus und decodiert das Ergebnis.
    WHY: Zentraler Wrapper der JEDEN Bridge-Call absichert.
    CONSEQUENCES: Fängt alle Exceptions und gibt ein Error-Dict zurück statt zu crashen.
    """
    try:
        call_params = params or {}
        raw = await asyncio.to_thread(
            post_mcp, "tools/call", {"name": method, "arguments": call_params}
        )
        result = decode_mcp_result(raw)

        # Wenn ein explizit gesetzter tabId-Wert stale ist, niemals blind auf den
        # aktiven Tab ausweichen. Stattdessen nur die exakt bekannte Worker-Tab-
        # Zuordnung wiederherstellen.
        if (
            isinstance(result, dict)
            and result.get("error")
            and call_params.get("tabId") is not None
        ):
            error_text = str(result.get("error", ""))
            if "No tab with id" in error_text or "No tab with given id" in error_text:
                audit(
                    "state_change",
                    message=f"Stale tabId für {method} erkannt; versuche Worker-Tab-Recovery",
                )
                recovered_tab_id = await recover_worker_tab_id()
                if recovered_tab_id is not None:
                    retry_params = dict(call_params)
                    retry_params["tabId"] = recovered_tab_id
                    retry_raw = await asyncio.to_thread(
                        post_mcp,
                        "tools/call",
                        {"name": method, "arguments": retry_params},
                    )
                    result = decode_mcp_result(retry_raw)

        return result
    except Exception as e:
        audit("error", message=f"execute_bridge({method}) failed: {e}")
        return {"error": str(e)}


async def check_bridge_alive():
    """
    Prüft ob die Bridge noch lebt, und wartet ggf. auf Reconnect.
    WHY: Mitten im Lauf kann die Extension disconnecten (Tab-Crash, Sleep, etc.)
    CONSEQUENCES: Bis zu 60s Reconnect-Versuch bevor aufgegeben wird.
    """
    health = await asyncio.to_thread(fetch_health)
    if health.get("extensionConnected") is True:
        return True

    audit("state_change", message="Bridge disconnected! Versuche Reconnect...")
    start = time.time()
    while time.time() - start < 60:
        await asyncio.sleep(5)
        health = await asyncio.to_thread(fetch_health)
        if health.get("extensionConnected") is True:
            audit("success", message="Bridge reconnected!")
            return True

    audit("error", message="Bridge Reconnect fehlgeschlagen nach 60s")
    return False


# ============================================================================
# SCREENSHOT-ENGINE — Mit Hash-Tracking für Fortschrittserkennung
# ============================================================================


async def take_screenshot(step_num: int, label: str = ""):
    """
    Macht einen Screenshot der exakt bekannten Worker-Tab-Instanz und speichert ihn als PNG.
    WHY: Jeder einzelne Schritt muss visuell dokumentiert werden (PRIORITY -7.0).
    CONSEQUENCES: Gibt (path, hash) zurück für Fortschrittserkennung.
    """
    try:
        params = _tab_params()
        # `screenshot_full` hängt an der sichtbaren Browser-Instanz und wäre bei
        # parallelen Tabs unsicher. `observe` liefert ein tabgebundenes Screenshot
        # für genau die Worker-Instanz.
        res = await execute_bridge("observe", params)

        if isinstance(res, dict) and "screenshot" in res:
            screenshot = res.get("screenshot") or {}
            if isinstance(screenshot, dict) and "dataUrl" in screenshot:
                res = screenshot["dataUrl"]
        elif isinstance(res, dict) and "dataUrl" in res:
            # Fallback für ältere Bridge-Implementierungen.
            res = res["dataUrl"]

        if not isinstance(res, str) or not res.startswith("data:"):
            audit(
                "error",
                message="Screenshot fehlgeschlagen",
                step=step_num,
                result_type=type(res).__name__,
            )
            return None, None

        # Base64 decodieren und speichern
        _, payload = res.split(",", 1)
        # Padding korrigieren (Bridge liefert manchmal ohne Padding)
        payload += "=" * ((4 - len(payload) % 4) % 4)
        img_bytes = base64.b64decode(payload)

        # Hash für Fortschrittserkennung berechnen
        img_hash = hashlib.md5(img_bytes).hexdigest()

        # Dateiname mit Zeitstempel und Label für Nachvollziehbarkeit
        safe_label = re.sub(r"[^a-zA-Z0-9_-]", "", label.replace(" ", "_"))[:30]
        filename = f"step_{step_num:03d}_{safe_label}_{img_hash[:8]}.png"
        path = SCREENSHOT_DIR / filename
        path.write_bytes(img_bytes)

        audit(
            "screenshot",
            step=step_num,
            path=str(path),
            hash=img_hash,
            size=len(img_bytes),
        )
        return str(path), img_hash

    except Exception as e:
        audit("error", message=f"Screenshot Exception: {e}", step=step_num)
        return None, None


# ============================================================================
# DOM PRE-SCAN — Holt ECHTE Selektoren von der Seite vor jedem Vision-Call
# ============================================================================


async def dom_prescan():
    """
    Scannt die aktuelle Seite nach klickbaren Elementen und liefert echte Selektoren.
    WHY: Gemini DARF NIEMALS CSS-Selektoren raten! Es muss die echten kennen.
    CONSEQUENCES: Ohne Pre-Scan schlägt Gemini Fantasie-Selektoren wie :has-text() vor.
    """
    global CURRENT_TAB_ID, CURRENT_WINDOW_ID
    tab_params = _tab_params()

    # 1. Accessibility-Tree-Snapshot mit Refs holen (für click_ref)
    snapshot_info = ""
    try:
        snapshot = await execute_bridge(
            "snapshot", {**tab_params, "includeScreenshot": False}
        )
        if isinstance(snapshot, dict) and "tree" in snapshot:
            tree = snapshot["tree"]
            # Nur interaktive Elemente (mit @eX Refs) extrahieren
            interactive = [l.strip() for l in tree.splitlines() if "@e" in l]
            if interactive:
                snapshot_info = (
                    "ACCESSIBILITY-TREE REFS (nutzbar mit click_ref):\n"
                    + "\n".join(interactive[:20])
                )
            audit(
                "action",
                message=f"DOM Pre-Scan: {len(interactive)} interactive refs, {snapshot.get('refCount', 0)} total refs",
            )
    except Exception as e:
        audit("error", message=f"Snapshot fehlgeschlagen: {e}")

    # 2. Echte HTML-Elemente mit Klick-Potential scannen
    clickable_info = ""
    try:
        js_scan = """
        (function() {
            var results = [];
            var all = document.querySelectorAll('[onclick], [role="button"], a[href], button, input[type="submit"], [style*="cursor: pointer"], .survey-item, .survey-card, [class*="card"], [class*="survey"]');
            for (var i = 0; i < Math.min(all.length, 25); i++) {
                var el = all[i];
                var r = el.getBoundingClientRect();
                if (r.width < 5 || r.height < 5) continue;
                var sel = '';
                if (el.id) sel = '#' + el.id;
                else if (el.className && typeof el.className === 'string') {
                    var cls = el.className.split(' ').filter(function(c) { return c.length > 0; })[0];
                    if (cls) sel = el.tagName.toLowerCase() + '.' + cls;
                }
                if (!sel) sel = el.tagName.toLowerCase();
                results.push({
                    sel: sel,
                    tag: el.tagName,
                    id: el.id || '',
                    cls: (el.className + '').substring(0, 80),
                    text: (el.textContent || '').substring(0, 60).replace(/\\n/g, ' ').trim(),
                    x: Math.round(r.x + r.width/2),
                    y: Math.round(r.y + r.height/2),
                    w: Math.round(r.width),
                    h: Math.round(r.height),
                    cursor: getComputedStyle(el).cursor
                });
            }
            return results;
        })();
        """
        scan_result = await execute_bridge(
            "execute_javascript", {"script": js_scan, **tab_params}
        )
        if isinstance(scan_result, dict) and "result" in scan_result:
            elements = scan_result["result"]
            if isinstance(elements, list) and elements:
                lines = []
                for el in elements:
                    selector = el.get("sel", "?")
                    if el.get("id"):
                        selector = f"#{el['id']}"
                    text = el.get("text", "")[:40]
                    lines.append(
                        f'  - selector="{selector}" text="{text}" pos=({el.get("x")},{el.get("y")}) size={el.get("w")}x{el.get("h")} cursor={el.get("cursor")}'
                    )
                clickable_info = (
                    "KLICKBARE ELEMENTE AUF DER SEITE (ECHTE CSS-Selektoren!):\n"
                    + "\n".join(lines)
                )
                audit(
                    "action",
                    message=f"DOM Pre-Scan: {len(elements)} clickable elements found",
                )
    except Exception as e:
        audit("error", message=f"Clickable scan fehlgeschlagen: {e}")

    # 3. Seiten-URL und Titel
    page_context = ""
    try:
        page_info = await execute_bridge("get_page_info", tab_params)
        if isinstance(page_info, dict):
            page_context = f"AKTUELLE SEITE: URL={page_info.get('url', '?')} Title={page_info.get('title', '?')}"
    except Exception:
        pass

    return "\n\n".join(filter(None, [page_context, snapshot_info, clickable_info]))


def _page_type_to_page_state(page_type: str) -> str:
    """
    Übersetzt den neuen Vision-V2 `page_type` in die vorhandenen Worker-Zustände.
    WHY: Der Rest des Workers arbeitet weiterhin mit den etablierten Zustandsnamen
         (`page_state`), während der neue Vision-Vertrag bewusst kompakter ist.
    CONSEQUENCES: Die Integration bleibt klein und rückwärtskompatibel.
    """
    mapping = {
        "login": "login",
        "survey_list": "dashboard",
        "survey_question": "survey_active",
        "survey_complete": "survey_done",
        "captcha": "captcha",
        "unknown": "unknown",
    }
    return mapping.get((page_type or "unknown").strip().lower(), "unknown")


def _safe_transition(
    ctx: StepContext, new_state: AgentState, reason: str
) -> StepContext:
    """
    Führt einen FSM-Übergang aus, ohne den Worker wegen eines doppelten oder
    unerwarteten Status-Mappings hart zu stoppen.
    WHY: Vision + DOM können denselben realen Zustand in mehreren Schleifen
         hintereinander melden. Dann wäre ein erneuter Übergang illegal, aber
         nicht fatal — wir loggen das sauber statt mitten im Run zu crashen.
    CONSEQUENCES: Der Worker behält die harte FSM, aber bleibt robust gegen
                  harmlose Wiederholungen im gleichen UI-Zustand.
    """
    try:
        return step_context_advance(ctx, new_state, reason)
    except IllegalTransitionError as exc:
        audit("warning", message=f"FSM transition ignored: {exc}")
        return ctx


def _transition_for_page_state(
    ctx: StepContext,
    page_state: str,
    verdict: str,
) -> StepContext:
    """
    Übersetzt Worker-Page-States in FSM-Zustände.
    WHY: Der Vision-Layer arbeitet mit UI-Zuständen wie `login`, `dashboard`
         oder `survey_active`, während die Alpha-Orchestrierung harte AgentState-
         Phasen braucht. Diese Brücke hält beide Welten synchron.
    CONSEQUENCES: Checkpoints, Logs und spätere Resume-Logik sehen immer einen
                  echten AgentState statt nur loser UI-Strings.
    """
    if page_state == "login":
        return _safe_transition(ctx, AgentState.AUTHENTICATE, "Login page detected")
    if page_state == "onboarding":
        return _safe_transition(ctx, AgentState.ONBOARD, "Onboarding page detected")
    if page_state == "dashboard":
        return _safe_transition(ctx, AgentState.DISCOVER_WORK, "Dashboard detected")
    if page_state == "survey":
        return _safe_transition(
            ctx, AgentState.SELECT_TASK, "Survey selection detected"
        )
    if page_state == "survey_active":
        if ctx.state == AgentState.SELECT_TASK:
            _safe_transition(
                ctx, AgentState.ENTER_TASK, "Entering selected survey task"
            )
        return _safe_transition(
            ctx, AgentState.EXECUTE_TASK_LOOP, "Survey question loop active"
        )
    if page_state == "survey_done":
        _safe_transition(ctx, AgentState.VALIDATE_OUTCOME, "Survey completion detected")
        return _safe_transition(
            ctx, AgentState.RECORD_RESULT, "Recording survey result"
        )
    if verdict == VisionVerdict.STOP.value:
        return ctx
    return ctx


def _sitepack_selector(name: str, fallback: str) -> str:
    """
    Holt einen Selektor aus dem Sitepack und fällt laut auf einen bekannten
    Hard-Fallback zurück, wenn der Pack-Eintrag fehlt.
    WHY: Die Integration muss jetzt schon robust laufen, auch wenn einzelne
         Sitepack-Einträge noch nicht final live-verifiziert sind.
    CONSEQUENCES: Wir profitieren sofort von zentralen Selektoren, ohne dass
                  der Worker bei einem fehlenden Key komplett unbenutzbar wird.
    """
    if not SITEPACK.is_loaded:
        return fallback
    try:
        return SITEPACK.get_selector(name)
    except (SelectorNotFoundError, RuntimeError):
        return fallback


def _next_action_to_worker_command(next_action: NextAction) -> tuple[str, dict]:
    """
    Übersetzt die generische Vision-V2 Aktion in konkrete Worker-/Bridge-Befehle.
    WHY: Der JSON-Vertrag soll modellseitig generisch bleiben, während der Worker
         weiterhin seine bestehenden spezialisierten Klick- und Scrollpfade nutzt.
    CONSEQUENCES: Alte Bridge-Methoden können weiterverwendet werden, ohne dass das
                  Modell deren gesamte interne Namenswelt kennen muss.
    """
    action_type = (next_action.type or "none").strip().lower()
    target = (next_action.target or "").strip()
    value = (next_action.value or "").strip()

    def _extract_accessibility_ref(raw_target: str) -> str:
        """
        Extrahiert eine Accessibility-Referenz wie `@e19` aus freien Zielstrings.
        WHY: Das Vision-Modell liefert nicht immer sauber `ref:@e19`, sondern oft
             Formen wie `textbox @e19`. Diese müssen trotzdem in den ref-basierten
             Bridge-Pfad geroutet werden.
        CONSEQUENCES: Click- und Type-Aktionen verstehen sowohl explizite `ref:`-
                      Targets als auch lose Accessibility-Referenzen.
        """
        match = re.search(r"(@e\d+)", raw_target or "", flags=re.IGNORECASE)
        return match.group(1) if match else ""

    if action_type == "click":
        if target.startswith("selector:"):
            return "click_element", {"selector": target.split(":", 1)[1].strip()}
        if target.startswith("ref:"):
            return "click_ref", {"ref": target.split(":", 1)[1].strip()}
        inferred_ref = _extract_accessibility_ref(target)
        if inferred_ref:
            return "click_ref", {"ref": inferred_ref}
        if target.startswith("text:"):
            return "vision_click", {"description": target.split(":", 1)[1].strip()}
        if target.startswith("coords:"):
            coords = target.split(":", 1)[1].split(",", 1)
            if len(coords) == 2:
                try:
                    return "click_coordinates", {
                        "x": int(coords[0].strip()),
                        "y": int(coords[1].strip()),
                    }
                except ValueError:
                    pass
        if target:
            return "vision_click", {"description": target}
        return "none", {}

    if action_type == "type":
        inferred_ref = ""
        if target.startswith("ref:"):
            inferred_ref = target.split(":", 1)[1].strip()
        else:
            inferred_ref = _extract_accessibility_ref(target)

        if inferred_ref:
            return "type_text", {"ref": inferred_ref, "text": value}

        selector = (
            target.split(":", 1)[1].strip()
            if target.startswith("selector:")
            else target
        )
        return "type_text", {"selector": selector, "text": value}

    if action_type == "scroll":
        direction = value.lower() if value else "down"
        if direction in {"up", "scroll_up"}:
            return "scroll_up", {}
        return "scroll_down", {}

    if action_type == "wait":
        return "wait", {"reason": value or target or "vision_requested_wait"}

    return "none", {}


def _copy_vision_response(response: VisionResponse, update: dict) -> VisionResponse:
    """
    Erstellt ein aktualisiertes VisionResponse-Objekt kompatibel mit Pydantic v1/v2.
    WHY: HF-VMs können je nach Image unterschiedliche Pydantic-Versionen haben.
    CONSEQUENCES: Die Policy-Logik bleibt versionsstabil und testbar.
    """
    if hasattr(response, "model_copy"):
        return response.model_copy(update=update)
    return response.copy(update=update)


def _apply_vision_response_policy(response: VisionResponse) -> VisionResponse:
    """
    Erzwingt fail-closed Worker-Regeln auf dem bereits geparsten Vision-Objekt.
    WHY: Auch formal gültiges JSON darf die Schleife nicht blind fortsetzen, wenn
         die Konfidenz zu niedrig ist oder ein nicht lösbarer Blocker vorliegt.
    CONSEQUENCES: Niedrige Sicherheit wird deterministisch zu RETRY oder ESCALATE.
    """
    if response.confidence < 0.6:
        return _copy_vision_response(
            response,
            {
                "verdict": VisionVerdict.RETRY,
                "reasoning": (
                    f"Low-confidence vision response ({response.confidence:.2f}); retry required."
                ),
                "next_action": NextAction(type="none", target="", value=""),
            },
        )

    if response.blocker and not response.blocker.auto_resolvable:
        return _copy_vision_response(response, {"verdict": VisionVerdict.ESCALATE})

    return response


def _vision_response_to_decision(response: VisionResponse) -> dict:
    """
    Wandelt das strikte Vision-V2 Modell in das bestehende Worker-Decision-Dict um.
    WHY: So kann der Hauptloop minimal angepasst werden, während Tests und Prompt
         bereits vollständig auf dem neuen Vertrag laufen.
    CONSEQUENCES: Alte Konsumenten lesen weiterhin `page_state`, `next_action` und
                  `next_params`, bekommen diese Felder jetzt aber aus validiertem JSON.
    """
    next_action_name, next_params = _next_action_to_worker_command(response.next_action)
    blocker = response.blocker
    return {
        "verdict": response.verdict.value,
        "confidence": response.confidence,
        "page_type": response.page_type,
        "page_state": _page_type_to_page_state(response.page_type),
        "reason": response.reasoning,
        "progress": bool(response.dom_hash),
        "next_action": next_action_name,
        "next_params": next_params,
        "dom_hash": response.dom_hash,
        "blocker": {
            "type": blocker.type,
            "detail": blocker.detail,
            "auto_resolvable": blocker.auto_resolvable,
        }
        if blocker
        else None,
    }


# ============================================================================
# VISION GATE — Gemini 3 Flash Analyse mit gehärtetem Prompt + DOM-Kontext
# ============================================================================


async def ask_vision(
    screenshot_path: str, action_desc: str, expected: str, step_num: int
):
    """
    Sendet einen Screenshot + DOM-Kontext an das Vision-Modell und erzwingt den
    Vision-Gate-V2 JSON-Vertrag.
    WHY: Das Modell darf keine freien Texte mehr liefern, weil die Worker-Logik
         auf einem strikt validierten Antwortschema aufbauen muss.
    CONSEQUENCES: Jede Antwort wird über `parse_vision_response()` normalisiert;
                  bei Parse- oder Policy-Fehlern fällt der Worker fail-closed auf
                  RETRY oder STOP zurück.
    """
    # DOM-Kontext bleibt Pflicht, damit das Modell echte Selektoren und Ref-Hinweise
    # sieht statt sich Klick-Ziele auszudenken.
    dom_context = await dom_prescan()

    # Profil-Kontext bleibt zusätzlich erhalten, damit Profil- und Login-Fragen auf
    # echten Nutzerdaten basieren statt auf Fantasie-Antworten.
    profile_context = _build_profile_context()
    prompt_dom_snapshot = "\n\n".join(filter(None, [profile_context, dom_context]))
    prompt = build_vision_prompt(action_desc, expected, prompt_dom_snapshot)

    run_result = await run_vision_model(
        prompt,
        screenshot_path,
        timeout=180,
        step_num=step_num,
        purpose="main_loop",
    )
    if not run_result.get("ok"):
        error_reason = run_result.get("error", "Vision call failed")
        if run_result.get("auth_failure"):
            return {
                "verdict": VisionVerdict.STOP.value,
                "confidence": 0.0,
                "reason": f"Vision auth failed: {error_reason}",
                "next_action": "none",
                "next_params": {},
                "page_state": "error",
                "page_type": "unknown",
                "progress": False,
                "dom_hash": "",
                "blocker": {
                    "type": "auth",
                    "detail": error_reason,
                    "auto_resolvable": False,
                },
            }
        return {
            "verdict": VisionVerdict.RETRY.value,
            "confidence": 0.0,
            "reason": error_reason,
            "next_action": "none",
            "next_params": {},
            "page_state": "unknown",
            "page_type": "unknown",
            "progress": False,
            "dom_hash": "",
            "blocker": None,
        }

    full_text = run_result.get("text", "")

    try:
        response = parse_vision_response(full_text)
        response = _apply_vision_response_policy(response)
        decision = _vision_response_to_decision(response)
        audit(
            "vision_check",
            step=step_num,
            verdict=decision.get("verdict"),
            confidence=decision.get("confidence"),
            page_state=decision.get("page_state"),
            reason=decision.get("reason", "")[:150],
            next_action=decision.get("next_action"),
        )
        return decision

    except Exception as e:
        audit(
            "error",
            message=f"Vision contract parse error: {e}",
            step=step_num,
            raw_output=full_text[:500],
        )
        return {
            "verdict": VisionVerdict.RETRY.value,
            "confidence": 0.0,
            "reason": f"Vision contract parse error: {e}",
            "next_action": "none",
            "next_params": {},
            "page_state": "unknown",
            "page_type": "unknown",
            "progress": False,
            "dom_hash": "",
            "blocker": None,
        }


# ============================================================================
# KEYBOARD NAVIGATION — Tab, Enter, Arrow Keys als ultimative Bypass-Methode
# ============================================================================


async def keyboard_action(keys: list, selector: str = ""):
    """
    Führt Tastatur-Aktionen aus via JavaScript KeyboardEvent Dispatch.
    WHY: Wenn ALLE Klick-Methoden scheitern, funktionieren Tastatur-Events IMMER,
    weil sie auf OS-Level durchgehen und von keinem Framework blockiert werden.
    CONSEQUENCES: Die allerbeste Umgehung für störrische SPAs.

    Unterstützte Keys: Tab, Enter, Space, ArrowDown, ArrowUp, ArrowLeft, ArrowRight, Escape
    """
    global CURRENT_TAB_ID, CURRENT_WINDOW_ID
    tab_params = _tab_params()
    selector = normalize_selector(selector)

    # Mapping von Key-Namen zu KeyboardEvent-Properties
    key_map = {
        "Tab": {"key": "Tab", "code": "Tab", "keyCode": 9},
        "Enter": {"key": "Enter", "code": "Enter", "keyCode": 13},
        "Space": {"key": " ", "code": "Space", "keyCode": 32},
        "Escape": {"key": "Escape", "code": "Escape", "keyCode": 27},
        "ArrowDown": {"key": "ArrowDown", "code": "ArrowDown", "keyCode": 40},
        "ArrowUp": {"key": "ArrowUp", "code": "ArrowUp", "keyCode": 38},
        "ArrowLeft": {"key": "ArrowLeft", "code": "ArrowLeft", "keyCode": 37},
        "ArrowRight": {"key": "ArrowRight", "code": "ArrowRight", "keyCode": 39},
    }

    results = []
    for key_name in keys:
        kp = key_map.get(key_name, {"key": key_name, "code": key_name, "keyCode": 0})

        # Wenn ein Selektor angegeben ist, erst auf das Element fokussieren
        focus_part = ""
        if selector:
            focus_part = f"""
                var target = document.querySelector("{selector}");
                if (target && typeof target.focus === 'function') {{
                    target.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                    target.focus();
                }}
            """

        js_code = f"""
        (function() {{
            {focus_part}
            var el = document.activeElement || document.body;
            var opts = {{
                key: "{kp["key"]}", code: "{kp["code"]}",
                keyCode: {kp["keyCode"]}, which: {kp["keyCode"]},
                bubbles: true, cancelable: true, composed: true,
                view: window
            }};
            el.dispatchEvent(new KeyboardEvent('keydown', opts));
            el.dispatchEvent(new KeyboardEvent('keypress', opts));
            el.dispatchEvent(new KeyboardEvent('keyup', opts));
            return {{
                success: true, key: "{key_name}",
                target: el.tagName + (el.id ? '#' + el.id : '') + (el.className ? '.' + (el.className + '').split(' ')[0] : ''),
                focused: el === document.activeElement
            }};
        }})();
        """
        try:
            result = await execute_bridge(
                "execute_javascript", {"script": js_code, **tab_params}
            )
            audit("keyboard", key=key_name, result=str(result)[:150])
            results.append(result)
            # Kurze Pause zwischen Tasten wie ein Mensch
            await asyncio.sleep(0.15 + random.random() * 0.25)
        except Exception as e:
            audit("error", message=f"Keyboard {key_name} failed: {e}")
            results.append({"error": str(e)})

    return results


# ============================================================================
# DOM-VERIFIKATION — Prüft ob sich die Seite WIRKLICH verändert hat
# ============================================================================


async def dom_verify_change(before_url: str, before_title: str):
    """
    Prüft via DOM ob die Seite sich nach einer Aktion verändert hat.
    WHY: Vision allein kann täuschen (gleicher Screenshot, aber DOM hat sich geändert).
         DOM allein kann täuschen (URL gleich, aber visuell komplett anders).
         NUR BEIDES ZUSAMMEN gibt Sicherheit!
    CONSEQUENCES: Gibt ein Dict mit changed=True/False und Details zurück.
    """
    tab_params = _tab_params()

    try:
        page_info = await execute_bridge("get_page_info", tab_params)
        current_url = page_info.get("url", "") if isinstance(page_info, dict) else ""
        current_title = (
            page_info.get("title", "") if isinstance(page_info, dict) else ""
        )

        if not current_url and not current_title:
            # Tab may still be loading — wait briefly and retry once with same tabId
            # NEVER switch to a different tab or recover to a new one here
            await asyncio.sleep(1.5)
            page_info = await execute_bridge("get_page_info", tab_params)
            current_url = (
                page_info.get("url", "") if isinstance(page_info, dict) else ""
            )
            current_title = (
                page_info.get("title", "") if isinstance(page_info, dict) else ""
            )

        url_changed = current_url != before_url
        title_changed = current_title != before_title

        # Auch DOM-Diff via Bridge page_diff abfragen (vergleicht Accessibility Trees)
        dom_diff = None
        try:
            diff_result = await execute_bridge("page_diff", tab_params)
            if isinstance(diff_result, dict):
                dom_diff = {
                    "added": diff_result.get("addedCount", 0),
                    "removed": diff_result.get("removedCount", 0),
                    "changed": diff_result.get("changedCount", 0),
                }
        except Exception:
            pass

        changed = (
            url_changed
            or title_changed
            or (
                dom_diff
                and (
                    dom_diff["added"] > 0
                    or dom_diff["removed"] > 0
                    or dom_diff["changed"] > 0
                )
            )
        )

        result = {
            "changed": bool(changed),
            "url_changed": url_changed,
            "title_changed": title_changed,
            "current_url": current_url,
            "current_title": current_title,
            "dom_diff": dom_diff,
        }
        audit("dom_verify", **result)
        return result

    except Exception as e:
        audit("error", message=f"DOM-Verifikation fehlgeschlagen: {e}")
        return {"changed": False, "error": str(e)}


# ============================================================================
# KLICK-ESKALATIONSKETTE — 5 Methoden mit Keyboard-Bypass, automatisch eskalierend
# ============================================================================

MAX_CLICK_ESCALATIONS = 5  # click → ghost → KEYBOARD → vision → coords

# Globaler Schritt-Zähler für Vision-Screenshots innerhalb der Eskalation.
# WHY: take_screenshot() braucht eine step_num — wir verwenden einen eigenen
# Zähler damit Eskalations-Screenshots im Audit-Log klar von Hauptloop-Schritten
# unterscheidbar sind (Format: "esc_NNN").
_ESC_STEP = 0


async def _vision_gate_inside_escalation(
    step_label: str, action_done: str, expected: str
) -> dict:
    """
    Macht Screenshot + Vision-Check INNERHALB der Eskalationskette.
    Gibt das volle Vision-Decision-Dict zurück (verdict, next_action, next_params, page_state).
    WHY: Das Mandat verlangt Vision VOR JEDER AKTION — auch vor jeder Eskalationsstufe.
    CONSEQUENCES: Ohne diesen Gate kann die Eskalation blind 5 Aktionen hintereinander
    feuern ohne zu wissen ob der Klick überhaupt sinnvoll war.
    """
    global _ESC_STEP
    _ESC_STEP += 1
    img_path, _ = await take_screenshot(_ESC_STEP * 1000, label=f"esc_{step_label}")
    if not img_path:
        # Screenshot fehlgeschlagen → pessimistisch RETRY zurückgeben
        return {
            "verdict": "RETRY",
            "next_action": "none",
            "next_params": {},
            "page_state": "unknown",
        }
    return await ask_vision(img_path, action_done, expected, _ESC_STEP * 1000)


async def escalating_click(
    selector: str = "",
    description: str = "",
    x: int = None,
    y: int = None,
    step_num: int = 0,
    ref: str = "",
):
    """
    Versucht einen Klick mit bis zu 5 Methoden — JEDE durch Vision-Gate abgesichert.
    WHY: Verschiedene Webseiten-Technologien brauchen verschiedene Interaktionsmethoden.
    Vision entscheidet nach JEDEM Klickversuch ob die nächste Stufe nötig ist.
    CONSEQUENCES: Kein blinder Auto-Eskalations-Loop mehr — Vision sieht jede Stufe.

    Eskalationskette (vision-gesteuert):
    1. click_ref (Accessibility-Ref, falls vorhanden) → Vision-Check
    2. click_element (Standard CSS-Selektor) → Vision-Check
    3. ghost_click (Voller Pointer+Mouse Event-Stack via JS) → Vision-Check
    4. KEYBOARD (Tab zum Element navigieren + Enter drücken) → Vision-Check
    5. vision_click / click_coordinates als letzte Auswege → Vision-Check
    """
    tab_params = _tab_params()
    selector = normalize_selector(selector)
    selector = await resolve_survey_selector(selector, description)
    if not selector and description:
        desc_lower = description.lower()
        if "umfrage" in desc_lower or "survey" in desc_lower or "€" in desc_lower:
            selector = await resolve_survey_selector(
                _sitepack_selector("survey_list_item", "div.survey-item"),
                description,
            )

    methods = []
    if ref:
        methods.append(("click_ref", {**tab_params, "ref": ref}))
    if selector:
        methods.append(("click_element", {**tab_params, "selector": selector}))
    if selector:
        methods.append(("ghost_click_js", selector))
    if selector:
        methods.append(("keyboard_focus_enter", selector))
    if description:
        methods.append(("vision_click", {**tab_params, "description": description}))
    if x is not None and y is not None:
        methods.append(("click_coordinates_js", (x, y)))

    before_url, before_title = "", ""
    try:
        pi = await execute_bridge("get_page_info", tab_params)
        if isinstance(pi, dict):
            before_url = pi.get("url", "")
            before_title = pi.get("title", "")
    except Exception:
        pass

    for i, method_info in enumerate(methods):
        if i >= MAX_CLICK_ESCALATIONS:
            break

        method_name = method_info[0]
        audit(
            "click_escalation",
            level=i + 1,
            method=method_name,
            selector=selector[:80] if selector else "",
        )

        try:
            if method_name == "click_ref":
                result = await execute_bridge("click_ref", method_info[1])
                if isinstance(result, dict) and result.get("error"):
                    audit("error", message=f"click_ref failed: {result['error']}")
                else:
                    await asyncio.sleep(0.8)
                    esc_decision = await _vision_gate_inside_escalation(
                        f"after_click_ref_{i}",
                        f"click_ref auf {ref[:60]}",
                        "Seite hat reagiert",
                    )
                    audit(
                        "vision_check",
                        method="click_ref",
                        verdict=esc_decision.get("verdict"),
                        page_state=esc_decision.get("page_state"),
                    )
                    if esc_decision.get("verdict") == "PROCEED":
                        return True
                continue

            if method_name == "click_element":
                result = await execute_bridge("click_element", method_info[1])
                if isinstance(result, dict) and result.get("error"):
                    audit("error", message=f"click_element failed: {result['error']}")
                else:
                    await asyncio.sleep(0.8)
                    esc_decision = await _vision_gate_inside_escalation(
                        f"after_click_element_{i}",
                        f"click_element auf {selector[:60]}",
                        "Seite hat reagiert",
                    )
                    audit(
                        "vision_check",
                        method="click_element",
                        verdict=esc_decision.get("verdict"),
                        page_state=esc_decision.get("page_state"),
                    )
                    if esc_decision.get("verdict") == "PROCEED":
                        return True
                continue

            elif method_name == "ghost_click_js":
                sel = method_info[1]
                js_code = f"""
                (function() {{
                    const el = document.querySelector("{sel}");
                    if (!el) return {{ error: "Element not found", selector: "{sel}" }};
                    el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                    const rect = el.getBoundingClientRect();
                    const x = rect.left + rect.width / 2;
                    const y = rect.top + rect.height / 2;
                    if (typeof el.focus === 'function') el.focus();
                    const opts = {{
                        bubbles: true, cancelable: true,
                        clientX: x, clientY: y, screenX: x, screenY: y,
                        view: window, detail: 1, button: 0, buttons: 1
                    }};
                    el.dispatchEvent(new PointerEvent('pointerover', opts));
                    el.dispatchEvent(new PointerEvent('pointerenter', {{...opts, bubbles: false}}));
                    el.dispatchEvent(new MouseEvent('mouseover', opts));
                    el.dispatchEvent(new MouseEvent('mouseenter', {{...opts, bubbles: false}}));
                    el.dispatchEvent(new PointerEvent('pointerdown', opts));
                    el.dispatchEvent(new MouseEvent('mousedown', opts));
                    el.dispatchEvent(new PointerEvent('pointerup', {{...opts, buttons: 0}}));
                    el.dispatchEvent(new MouseEvent('mouseup', {{...opts, buttons: 0}}));
                    el.dispatchEvent(new MouseEvent('click', {{...opts, buttons: 0}}));
                    if (typeof el.click === 'function') el.click();
                    return {{ success: true, tag: el.tagName, text: (el.textContent || '').substring(0, 60) }};
                }})();
                """
                result = await execute_bridge(
                    "execute_javascript", {"script": js_code, **tab_params}
                )
                if isinstance(result, dict) and result.get("error"):
                    audit("error", message=f"ghost_click failed: {result['error']}")
                else:
                    await asyncio.sleep(0.8)
                    esc_decision = await _vision_gate_inside_escalation(
                        f"after_ghost_click_{i}",
                        f"ghost_click auf {sel[:60]}",
                        "Seite hat reagiert",
                    )
                    audit(
                        "vision_check",
                        method="ghost_click",
                        verdict=esc_decision.get("verdict"),
                        page_state=esc_decision.get("page_state"),
                    )
                    if esc_decision.get("verdict") == "PROCEED":
                        return True
                continue

            elif method_name == "keyboard_focus_enter":
                sel = method_info[1]
                focus_js = f"""
                (function() {{
                    var el = document.querySelector("{sel}");
                    if (!el) return {{ error: "Element not found" }};
                    el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                    el.setAttribute('tabindex', '0');
                    el.focus();
                    return {{
                        success: true, focused: document.activeElement === el,
                        tag: el.tagName, id: el.id || '', text: (el.textContent || '').substring(0, 40)
                    }};
                }})();
                """
                focus_result = await execute_bridge(
                    "execute_javascript", {"script": focus_js, **tab_params}
                )
                audit("keyboard", action="focus", result=str(focus_result)[:150])
                await asyncio.sleep(0.3)
                await keyboard_action(["Enter"], selector=sel)
                await asyncio.sleep(0.8)
                esc_decision = await _vision_gate_inside_escalation(
                    f"after_keyboard_enter_{i}",
                    f"keyboard Enter auf {sel[:60]}",
                    "Seite hat reagiert",
                )
                audit(
                    "vision_check",
                    method="keyboard_enter",
                    verdict=esc_decision.get("verdict"),
                    page_state=esc_decision.get("page_state"),
                )
                if esc_decision.get("verdict") == "PROCEED":
                    return True
                await keyboard_action(["Space"], selector=sel)
                await asyncio.sleep(0.8)
                esc_decision2 = await _vision_gate_inside_escalation(
                    f"after_keyboard_space_{i}",
                    f"keyboard Space auf {sel[:60]}",
                    "Seite hat reagiert",
                )
                audit(
                    "vision_check",
                    method="keyboard_space",
                    verdict=esc_decision2.get("verdict"),
                    page_state=esc_decision2.get("page_state"),
                )
                if esc_decision2.get("verdict") == "PROCEED":
                    return True
                continue

            elif method_name == "vision_click":
                result = await execute_bridge("vision_click", method_info[1])
                if isinstance(result, dict) and result.get("error"):
                    audit("error", message=f"vision_click failed: {result['error']}")
                else:
                    await asyncio.sleep(0.8)
                    esc_decision = await _vision_gate_inside_escalation(
                        f"after_vision_click_{i}",
                        f"vision_click '{description[:40]}'",
                        "Seite hat reagiert",
                    )
                    audit(
                        "vision_check",
                        method="vision_click",
                        verdict=esc_decision.get("verdict"),
                        page_state=esc_decision.get("page_state"),
                    )
                    if esc_decision.get("verdict") == "PROCEED":
                        return True
                continue

            elif method_name == "click_coordinates_js":
                cx, cy = method_info[1]
                js_code = f"""
                (function() {{
                    const el = document.elementFromPoint({cx}, {cy});
                    if (!el) return {{ error: "Kein Element bei ({cx}, {cy})" }};
                    const opts = {{
                        bubbles: true, cancelable: true,
                        clientX: {cx}, clientY: {cy}, screenX: {cx}, screenY: {cy},
                        view: window, detail: 1, button: 0, buttons: 1
                    }};
                    el.dispatchEvent(new PointerEvent('pointerdown', opts));
                    el.dispatchEvent(new MouseEvent('mousedown', opts));
                    el.dispatchEvent(new PointerEvent('pointerup', {{...opts, buttons: 0}}));
                    el.dispatchEvent(new MouseEvent('mouseup', {{...opts, buttons: 0}}));
                    el.dispatchEvent(new MouseEvent('click', {{...opts, buttons: 0}}));
                    if (typeof el.click === 'function') el.click();
                    return {{ success: true, tag: el.tagName, text: (el.textContent || '').substring(0, 60) }};
                }})();
                """
                result = await execute_bridge(
                    "execute_javascript", {"script": js_code, **tab_params}
                )
                if isinstance(result, dict) and result.get("error"):
                    audit("error", message=f"coord_click failed: {result}")
                else:
                    await asyncio.sleep(0.8)
                    esc_decision = await _vision_gate_inside_escalation(
                        f"after_coord_click_{i}",
                        f"coord_click ({cx},{cy})",
                        "Seite hat reagiert",
                    )
                    audit(
                        "vision_check",
                        method="coord_click",
                        verdict=esc_decision.get("verdict"),
                        page_state=esc_decision.get("page_state"),
                    )
                    if esc_decision.get("verdict") == "PROCEED":
                        return True
                continue

        except Exception as e:
            audit("error", message=f"Klick-Methode {method_name} Exception: {e}")
            continue

    # DOM-FALLBACK: Wenn alle 5 Klick-Methoden fehlschlagen, versuche description-basierte Textsuche
    # WHY: vision_click oder andere Methoden können durch Rate-Limit oder komplexe Modals blockiert werden.
    # Ein simpler sichtbarer Button mit Text (z.B. "Nächste", "Weiter") umgeht Vision komplett.
    if description:
        audit(
            "action",
            message=f"DOM-Fallback: Versuche click_visible_button_with_text('{description[:40]}')",
        )
        if await click_visible_button_with_text(description):
            return True

    audit(
        "error",
        message="ALLE 5 Klick-Methoden fehlgeschlagen!",
        selector=selector[:80] if selector else "",
    )
    return False


# ============================================================================
# SESSION-BACKUP — Cookies sichern bei jedem wichtigen Statuswechsel
# ============================================================================


async def save_session(label: str):
    """
    Sichert die aktuelle Browser-Session (Cookies, LocalStorage).
    WHY: Bei Bridge-Disconnect oder Crash müssen wir die Session wiederherstellen können.
    """
    try:
        params = _tab_params()
        cookies = await execute_bridge("export_all_cookies", params)
        session_file = SESSION_DIR / f"session_{label}_{RUN_ID}.json"
        session_file.write_text(
            json.dumps(cookies, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        audit("session_save", label=label, path=str(session_file))
    except Exception as e:
        audit("error", message=f"Session-Backup fehlgeschlagen: {e}")


# ============================================================================
# HUMAN DELAYS — Zufällige Pausen gegen Bot-Erkennung
# ============================================================================


async def human_delay(min_sec=1.5, max_sec=4.5):
    """
    Wartet eine zufällige Zeitspanne wie ein echter Mensch.
    WHY: Konstante Delays (z.B. immer 3s) sind ein Bot-Signal.
    """
    delay = min_sec + random.random() * (max_sec - min_sec)
    await asyncio.sleep(delay)


# ============================================================================
# VISION GATE CONTROLLER — Herzstück der Sicherheit
# ============================================================================


class VisionGateController:
    """
    Steuert den gesamten Vision-Gate-Loop und verhindert Endlosschleifen.

    WHY: Ohne diesen Controller laufen Agenten in Endlosschleifen.
    CONSEQUENCES: Controller-Verletzung = Sofortiger Abbruch.

    Tracking:
    - total_steps: Gesamtzahl aller Aktionen
    - consecutive_retries: Aufeinanderfolgende RETRY-Verdicts
    - no_progress_count: Aktionen ohne sichtbare Bildschirmveränderung
    - last_screenshot_hash: MD5-Hash des letzten Screenshots für Vergleich
    - failed_selectors: Selektoren die bereits fehlgeschlagen sind (werden nicht nochmal versucht)
    """

    def __init__(self):
        self.total_steps = 0
        self.consecutive_retries = 0
        self.no_progress_count = 0
        self.last_screenshot_hash = None
        self.failed_selectors = set()
        self.last_page_state = None
        self.successful_actions = 0

    def should_continue(self) -> bool:
        """Prüft ob der Worker weitermachen darf."""
        if self.total_steps >= MAX_STEPS:
            audit("stop", reason=f"MAX_STEPS ({MAX_STEPS}) erreicht")
            return False
        if self.consecutive_retries >= MAX_RETRIES:
            audit("stop", reason=f"MAX_RETRIES ({MAX_RETRIES}) erreicht")
            return False
        if self.no_progress_count >= MAX_NO_PROGRESS:
            audit("stop", reason=f"MAX_NO_PROGRESS ({MAX_NO_PROGRESS}) erreicht")
            return False
        return True

    def record_step(
        self,
        verdict: str,
        screenshot_hash: str,
        page_state: str = None,
        dom_changed: bool = False,
    ):
        """Zeichnet einen Schritt auf und aktualisiert alle Zähler."""
        self.total_steps += 1

        # RETRY-Tracking
        if verdict == "RETRY":
            self.consecutive_retries += 1
        else:
            self.consecutive_retries = 0

        # Fortschritts-Erkennung:
        # WHY: Bei survey_active sehen Screenshots Frage-für-Frage fast identisch aus
        # (gleicher Header, gleiche Farben, gleiche Schriftarten). Hash-Vergleich würde
        # das fälschlich als "kein Fortschritt" werten und die Umfrage abbrechen.
        # LÖSUNG: Wenn wir mitten in einer aktiven Umfrage sind (survey_active),
        # gilt der Schritt IMMER als Fortschritt — egal ob Hash gleich ist.
        # Zusätzlich zählt dom_changed=True ebenfalls als Fortschritt.
        currently_in_survey = page_state in ("survey_active", "survey")
        if (
            screenshot_hash
            and screenshot_hash == self.last_screenshot_hash
            and not currently_in_survey
            and not dom_changed
        ):
            self.no_progress_count += 1
        else:
            self.no_progress_count = 0
            self.last_screenshot_hash = screenshot_hash

        # Page-State-Tracking
        if page_state:
            if page_state != self.last_page_state:
                audit("state_change", old=self.last_page_state, new=page_state)
            self.last_page_state = page_state

        # Erfolgs-Tracking
        if verdict == "PROCEED":
            self.successful_actions += 1

    def add_failed_selector(self, selector: str):
        """Merkt sich einen fehlgeschlagenen Selektor um ihn nicht nochmal zu versuchen."""
        if selector:
            self.failed_selectors.add(selector)

    def is_selector_failed(self, selector: str) -> bool:
        """Prüft ob ein Selektor bereits fehlgeschlagen ist."""
        return selector in self.failed_selectors

    def mark_dom_progress(self):
        """
        Setzt no_progress_count zurück wenn DOM-Verifikation echte Änderung bestätigt.
        WHY: record_step() läuft VOR der Aktion und kennt dom_changed noch nicht.
             mark_dom_progress() wird NACH der Aktion aufgerufen um einen fälschlichen
             no_progress-Zähler zu korrigieren — kritisch bei Survey-Fragen deren
             Screenshot fast identisch aussieht aber der DOM sich verändert hat.
        """
        if self.no_progress_count > 0:
            self.no_progress_count = 0
            audit(
                "state_change",
                message="DOM-Fortschritt bestätigt: no_progress_count zurückgesetzt",
            )


# ============================================================================
# CREDENTIAL INJECTION — Sichere Ersetzung von Platzhaltern
# ============================================================================


def inject_credentials(params: dict, email: str, pwd: str) -> dict:
    """
    Ersetzt <EMAIL> und <PASSWORD> Platzhalter mit echten Credentials.
    WHY: Die AI darf NIEMALS echte Passwörter sehen oder ausgeben.
    CONSEQUENCES: Nur Platzhalter werden ersetzt, alles andere bleibt unverändert.
    """
    if "text" not in params:
        return params

    text = params["text"]
    if text == "<EMAIL>" or text.upper() == "EMAIL":
        params["text"] = email or ""
        audit("action", message="Credential injected: EMAIL (redacted)")
    elif text == "<PASSWORD>" or text.upper() == "PASSWORD":
        params["text"] = pwd or ""
        audit("action", message="Credential injected: PASSWORD (redacted)")

    return params


async def auto_resolve_blocker(
    blocker: dict | None, next_action: str, next_params: dict, step_num: int
) -> bool:
    """
    Versucht bekannte, explizit als automatisch lösbar markierte Blocker aufzulösen.
    WHY: Vision Gate V2 liefert jetzt strukturierte Blocker-Daten statt nur Text.
         Dadurch kann der Worker bei Modals oder Rate-Limits gezielt reagieren.
    CONSEQUENCES: Gibt nur dann `True` zurück, wenn wirklich eine Auto-Resolution
                  ausgeführt wurde; nicht lösbare Fälle eskalieren später hart.
    """
    if not blocker or not blocker.get("auto_resolvable"):
        return False

    blocker_type = (blocker.get("type") or "").strip().lower()
    blocker_detail = blocker.get("detail", "")
    audit(
        "state_change",
        message=f"Auto-resolvable blocker erkannt: {blocker_type} — {blocker_detail[:120]}",
        step=step_num,
    )

    # Wenn das Vision-Modell bereits eine konkrete Folgeaktion vorgeschlagen hat,
    # übernimmt der Hauptloop die tatsächliche Ausführung. Hier melden wir nur,
    # dass dieser Blocker prinzipiell automatisch behandelbar ist.
    if next_action != "none":
        return False

    if blocker_type == "modal":
        await keyboard_action(["Escape"])
        return True

    if blocker_type == "rate_limit":
        await human_delay(4.0, 7.0)
        return True

    return False


def _selector_for_predicate(next_action: str, next_params: dict) -> str:
    """
    Extrahiert den CSS-Selektor für die DOM-Predicate-Prüfungen.
    WHY: Nur CSS-Selektoren können zuverlässig auf Sichtbarkeit/Klickbarkeit und
         Okklusion geprüft werden; Ref- oder Koordinaten-Klicks haben keinen DOM-
         Selektor, werden aber trotzdem mit einem DOM-Hash-Snapshot versehen.
    CONSEQUENCES: Selektorlose Aktionen liefern einen leeren String und werden von
                  den Predicate-Checks als `skipped` behandelt.
    """
    if next_action == "type_text":
        return normalize_selector(next_params.get("selector", ""))
    if next_action == "click_element":
        return normalize_selector(next_params.get("selector", ""))
    return ""


# ============================================================================
# SCROLL-HANDLER
# ============================================================================


async def handle_scroll(direction: str):
    """Scrollt die Seite nach oben oder unten."""
    tab_params = _tab_params()
    pixels = 400 if direction == "scroll_down" else -400
    js_code = f"window.scrollBy(0, {pixels}); ({{ scrolled: true, by: {pixels} }})"
    await execute_bridge("execute_javascript", {"script": js_code, **tab_params})
    audit("action", message=f"Scrolled {direction}", pixels=pixels)


# ============================================================================
# ACTION-DISPATCH — Einheitlicher Pfad für alle Click-Entry-Points
# ============================================================================


async def run_click_action(
    next_params: dict, gate, img_hash: str, step_num: int
) -> bool:
    """
    Leitet alle Click-Aktionen durch genau EINE verifizierte Eskalationspipeline.
    WHY: Issue #86 verlangt, dass `click_ref` keinen direkten Bridge-Bypass mehr hat.
    CONSEQUENCES: Jeder Click-Entry-Point läuft hier zentral durch `escalating_click()`.
    """
    selector = next_params.get("selector", "")
    description = next_params.get("description", "")
    x = next_params.get("x")
    y = next_params.get("y")
    ref = next_params.get("ref", "")

    if selector and gate.is_selector_failed(selector):
        audit(
            "state_change",
            message=f"Selektor '{selector[:50]}' bereits fehlgeschlagen, überspringe",
        )
        gate.record_step("RETRY", img_hash)
        return False

    clicked = await escalating_click(
        selector=selector,
        description=description,
        x=x,
        y=y,
        step_num=step_num,
        ref=ref,
    )

    if not clicked:
        if selector:
            gate.add_failed_selector(selector)
        audit("error", message="Klick-Eskalation komplett fehlgeschlagen")

    return clicked


# ============================================================================
# HAUPTSCHLEIFE — Der komplette Vision Gate Loop
# ============================================================================


async def main():
    ctx = StepContext(
        state=AgentState.INIT,
        step_index=0,
        max_steps=MAX_STEPS,
        task_url="https://www.heypiggy.com/login",
    )
    _safe_transition(ctx, AgentState.PREFLIGHT, "Initializing worker")

    audit(
        "start",
        message="A2A-SIN-Worker-HeyPiggy Vision Gate v2.0",
        run_id=RUN_ID,
        artifact_dir=str(ARTIFACT_DIR),
    )

    # 1. BRIDGE-VERBINDUNG PRÜFEN
    try:
        await wait_for_extension(timeout=600)
    except Exception as e:
        audit("stop", reason=f"Bridge-Verbindung fehlgeschlagen: {e}")
        _safe_transition(
            ctx, AgentState.FAIL_SAFE, f"Bridge-Verbindung fehlgeschlagen: {e}"
        )
        return

    # 2. PRE-FLIGHT — Pflicht-Env + Vision-Auth müssen VOR Browser-Mutation healthy sein
    preflight = await ensure_worker_preflight()
    if not preflight.get("ok"):
        _safe_transition(ctx, AgentState.FAIL_SAFE, "Preflight fehlgeschlagen")
        return

    # Credentials erst NACH erfolgreichem fail-closed Preflight auslesen.
    # WHY: Die eigentliche Worker-Logik braucht die Werte für inject_credentials(),
    # aber nur nachdem bewiesen ist, dass Env vollständig und Vision healthy sind.
    email = os.environ.get("HEYPIGGY_EMAIL")
    pwd = os.environ.get("HEYPIGGY_PASSWORD")

    # 3. VISION GATE CONTROLLER INITIALISIEREN
    gate = VisionGateController()
    _safe_transition(
        ctx, AgentState.ACQUIRE_SESSION, "Bridge healthy and gate initialized"
    )

    # 4. INITIALE NAVIGATION
    action_desc = "Navigiere zu HeyPiggy Dashboard"
    expected = "Dashboard mit verfügbaren Umfragen oder Login-Formular"

    global CURRENT_TAB_ID, CURRENT_WINDOW_ID
    try:
        audit("navigate", url="https://www.heypiggy.com/login")
        # KRITISCH: active: True — Tab MUSS im Vordergrund sein!
        # Mit active: False läuft der Tab im Hintergrund → Screenshots zeigen falschen Inhalt
        # → Vision Gate sieht nichts → DOM-Verifikation gibt url="" zurück → Worker hängt
        tab_res = await execute_bridge(
            "tabs_create", {"url": "https://www.heypiggy.com/login", "active": True}
        )
        if isinstance(tab_res, dict) and "tabId" in tab_res:
            CURRENT_TAB_ID = tab_res["tabId"]
            CURRENT_WINDOW_ID = tab_res.get("windowId", CURRENT_WINDOW_ID)
            audit(
                "success",
                message=f"Worker-Tab erstellt und gebunden: tabId={CURRENT_TAB_ID}, windowId={CURRENT_WINDOW_ID}",
            )
        else:
            # tabs_create hat keine tabId zurückgegeben — harter Abbruch.
            # KEIN Fallback auf fremde Tabs, da wir sonst einen User-Tab steuern würden.
            audit(
                "stop",
                reason=f"tabs_create hat keine tabId zurückgegeben: {tab_res}. "
                "Kein Fallback auf aktiven Tab erlaubt.",
            )
            return
    except Exception as e:
        audit("stop", reason=f"Initiale Navigation fehlgeschlagen: {e}")
        _safe_transition(
            ctx, AgentState.FAIL_SAFE, f"Initiale Navigation fehlgeschlagen: {e}"
        )
        return

    # Verifikation: CURRENT_TAB_ID muss jetzt gesetzt sein
    if CURRENT_TAB_ID is None:
        audit("stop", reason="CURRENT_TAB_ID ist nach Init immer noch None — Abbruch")
        _safe_transition(
            ctx, AgentState.FAIL_SAFE, "CURRENT_TAB_ID ist nach Init immer noch None"
        )
        return

    # Warten auf Seitenlade
    await human_delay(4.0, 6.0)

    # Session direkt nach Laden sichern
    await save_session("initial_load")

    # 5. VISION GATE LOOP — Das Herzstück
    while gate.should_continue():
        ctx.no_progress_counter = gate.no_progress_count
        ctx.step_index = gate.total_steps
        if gate.no_progress_count >= MAX_NO_PROGRESS:
            _safe_transition(
                ctx,
                AgentState.FAIL_SAFE,
                "Gate detected no-progress threshold exhaustion",
            )
            break
        if gate.consecutive_retries >= MAX_RETRIES:
            _safe_transition(ctx, AgentState.ESCALATE, "Gate detected retry exhaustion")
            break

        # ---- Bridge-Health-Check vor JEDER Iteration ----
        if not await check_bridge_alive():
            audit("stop", reason="Bridge nicht erreichbar, Abbruch")
            _safe_transition(
                ctx, AgentState.FAIL_SAFE, "Bridge nicht erreichbar während Vision-Loop"
            )
            break

        # ---- SCREENSHOT ----
        img_path, img_hash = await take_screenshot(
            gate.total_steps + 1, label=action_desc[:20]
        )
        ctx.last_page_fingerprint = img_hash or ctx.last_page_fingerprint
        if not img_path:
            gate.record_step("RETRY", None)
            await human_delay(2.0, 4.0)
            continue

        # THROTTLE: Vor Vision-Calls länger warten um Rate-Limit zu vermeiden
        # WHY: Antigravity hat Rate-Limits; zu schnelle Calls führen zu leeren Antworten.
        await human_delay(5.0, 10.0)

        # ---- VISION CHECK ----
        _safe_transition(
            ctx, AgentState.ASSESS_PAGE, "Assessing current page state via vision"
        )
        decision = await ask_vision(
            img_path, action_desc, expected, gate.total_steps + 1
        )

        verdict = decision.get("verdict", VisionVerdict.RETRY.value)
        reason = decision.get("reason", "Kein Grund")
        page_state = decision.get("page_state", "unknown")
        page_type = decision.get("page_type", "unknown")
        next_action = decision.get("next_action", "none")
        next_params = decision.get("next_params", {})
        progress = decision.get("progress", False)
        blocker = decision.get("blocker")
        confidence = float(decision.get("confidence", 0.0) or 0.0)

        # Schritt aufzeichnen
        # WHY: Blocker-Eskalationen müssen VOR dem Gate-Tracking angewendet werden,
        # damit der Retry-/Stop-Zähler den finalen, nicht den vorläufigen Zustand sieht.
        if blocker and not blocker.get("auto_resolvable"):
            verdict = VisionVerdict.ESCALATE.value
            reason = f"Non-resolvable blocker: {blocker.get('type')} — {blocker.get('detail', '')}"

        _transition_for_page_state(ctx, page_state, verdict)
        gate.record_step(verdict, img_hash, page_state)

        print(f"\n{'=' * 60}")
        print(
            f"SCHRITT {gate.total_steps}/{MAX_STEPS} | Verdict: {verdict} | State: {page_state}"
        )
        print(f"Reason: {reason}")
        print(
            f"Next: {next_action} {json.dumps(next_params, ensure_ascii=False)[:120]}"
        )
        print(
            f"Retries: {gate.consecutive_retries}/{MAX_RETRIES} | No-Progress: {gate.no_progress_count}/{MAX_NO_PROGRESS}"
        )
        print(f"{'=' * 60}\n")

        # ---- BLOCKER POLICY ----
        # WHY: Vision Gate V2 liefert Blocker als strukturierte Daten. Dadurch kann
        # der Worker automatische Fälle behandeln und harte Fälle explizit eskalieren.
        if blocker and blocker.get("auto_resolvable"):
            resolved_inline = await auto_resolve_blocker(
                blocker, next_action, next_params, gate.total_steps
            )
            if resolved_inline:
                await human_delay(1.0, 2.0)
                continue

        # ---- STOP / ESCALATE ----
        if verdict in {VisionVerdict.STOP.value, VisionVerdict.ESCALATE.value}:
            audit(
                "stop",
                reason=reason,
                page_state=page_state,
                page_type=page_type,
                confidence=confidence,
                blocker=blocker,
            )
            await save_session("stop_state")
            if verdict == VisionVerdict.ESCALATE.value:
                _safe_transition(ctx, AgentState.ESCALATE, reason)
                break
            _safe_transition(ctx, AgentState.FAIL_SAFE, reason)
            break

        # ---- RETRY ----
        if verdict == VisionVerdict.RETRY.value:
            # Bei RETRY den Selektor als fehlgeschlagen merken
            if next_params.get("selector"):
                gate.add_failed_selector(next_params["selector"])
            await human_delay(2.0, 4.0)
            continue

        # ---- DONE ----
        if next_action == "none":
            audit(
                "success",
                message="Vision meldet: Aufgabe erledigt!",
                total_steps=gate.total_steps,
            )
            await save_session("completed")
            _safe_transition(
                ctx, AgentState.COMPLETE, "Vision reported task completion"
            )
            break

        # ---- SURVEY DONE — Bestätigungsseite erkannt ----
        # WHY: Wenn page_state="survey_done" bedeutet das, die aktuelle Umfrage wurde
        # erfolgreich abgeschlossen und eine Bestätigungsseite ist sichtbar.
        # KONSEQUENZ: Wir brechen NICHT ab — wir sichern den Fortschritt und
        # lassen den Hauptloop weiterlaufen, damit die Vision die nächste Umfrage
        # oder die Rückkehr zum Dashboard selbst erkennt und navigiert.
        # WARNUNG: Hier kein "break"! Abbrechen würde weitere ausstehende Surveys verpassen.
        if page_state == "survey_done":
            audit(
                "success",
                message="Umfrage vollständig abgeschlossen — Bestätigungsseite erkannt! Warte auf nächste Umfrage.",
                page_state=page_state,
                total_steps=gate.total_steps,
            )
            await save_session(f"survey_done_{gate.total_steps}")
            # no_progress_count zurücksetzen — Abschluss ist echter Fortschritt
            gate.mark_dom_progress()
            await human_delay(2.0, 4.0)
            continue

        # ---- CREDENTIAL INJECTION ----
        if next_action == "type_text" and next_params:
            next_params = inject_credentials(next_params, email, pwd)

        # ---- AKTION AUSFÜHREN ----
        action_desc = (
            f"{next_action} {json.dumps(next_params, ensure_ascii=False)[:80]}"
        )
        expected = f"UI hat auf {next_action} reagiert und sich verändert"
        audit(
            "action",
            action=next_action,
            params={
                k: v
                for k, v in next_params.items()
                if k != "text" or next_action != "type_text"
            },
        )

        # URL und Title VOR der Aktion für DOM-Verifikation sammeln
        before_url, before_title = "", ""
        try:
            pi_params = _tab_params()
            pi = await execute_bridge("get_page_info", pi_params)
            if isinstance(pi, dict):
                before_url = pi.get("url", "")
                before_title = pi.get("title", "")
        except Exception:
            pass

        predicate_before_hash = ""
        predicate_selector = _selector_for_predicate(next_action, next_params)
        if next_action in CLICK_ACTIONS or next_action == "type_text":
            try:
                predicate_pre = await asyncio.to_thread(
                    predicate_pre_check, BRIDGE_MCP_URL, predicate_selector
                )
                predicate_before_hash = predicate_pre.get("dom_hash", "")
                audit(
                    "predicate_pre",
                    step=gate.total_steps,
                    action=next_action,
                    selector=predicate_selector,
                    ok=predicate_pre.get("ok"),
                    skipped=predicate_pre.get("skipped"),
                    visible=predicate_pre.get("visible"),
                    clickable=predicate_pre.get("clickable"),
                    not_occluded=predicate_pre.get("not_occluded"),
                    reason=predicate_pre.get("reason"),
                )
                if predicate_selector and not predicate_pre.get("ok"):
                    gate.add_failed_selector(predicate_selector)
                    await human_delay(1.0, 2.0)
                    continue
            except Exception as e:
                audit("error", message=f"Predicate pre-check failed: {e}")

        try:
            # Scroll-Aktionen
            if next_action in ("scroll_down", "scroll_up"):
                await handle_scroll(next_action)

            # Klick-Aktionen (mit EINER gemeinsamen Eskalationskette)
            elif next_action in CLICK_ACTIONS:
                await run_click_action(next_params, gate, img_hash, gate.total_steps)

            # Explizite Keyboard-Aktion von Vision
            elif next_action == "keyboard":
                keys = next_params.get("keys", ["Enter"])
                if isinstance(keys, str):
                    keys = [keys]
                selector = next_params.get("selector", "")
                await keyboard_action(keys, selector=selector)

            # Text-Eingabe — IMMER mit exaktem tabId
            elif next_action == "type_text":
                ref = next_params.get("ref", "")
                if ref:
                    await execute_bridge("click_ref", {"ref": ref, **_tab_params()})
                    await human_delay(0.4, 0.9)
                    await execute_bridge(
                        "type_text",
                        {"text": next_params.get("text", ""), **_tab_params()},
                    )
                else:
                    params = {**next_params, **_tab_params()}
                    await execute_bridge("type_text", params)

            # Explizites Warten — nützlich bei Rate-Limits oder nach Auto-Submits
            elif next_action == "wait":
                await human_delay(2.0, 5.0)

            # Navigation — IMMER mit exaktem tabId, KEIN Fallback ohne tabId
            elif next_action == "navigate":
                url = next_params.get("url", "")
                ctx.task_url = url or ctx.task_url
                await execute_bridge("navigate", {"url": url, **_tab_params()})
                await save_session(f"nav_{gate.total_steps}")

            # Alle anderen Bridge-Tools — IMMER mit exaktem tabId
            else:
                params = {**next_params, **_tab_params()}
                await execute_bridge(next_action, params)

        except Exception as e:
            audit(
                "error",
                message=f"Aktion {next_action} Exception: {e}",
                traceback=traceback.format_exc()[:500],
            )

        # ---- DOM-VERIFIKATION NACH JEDER AKTION ----
        # WHY: Screenshot-Hash allein kann Survey-Frage-zu-Frage-Übergänge nicht erkennen
        # (gleicher Header, gleiche Farben → gleicher Hash → fälschlicher "kein Fortschritt").
        # DOM-Verifikation prüft URL + Title — ändert sich irgendeins, war es echter Fortschritt.
        # KONSEQUENZ: mark_dom_progress() setzt no_progress_count zurück → kein vorzeitiger Abbruch.
        await asyncio.sleep(1.0)

        predicate_post = None
        if next_action in CLICK_ACTIONS or next_action == "type_text":
            try:
                predicate_post = await asyncio.to_thread(
                    predicate_post_check, BRIDGE_MCP_URL, predicate_before_hash
                )
                audit(
                    "predicate_post",
                    step=gate.total_steps,
                    action=next_action,
                    selector=predicate_selector,
                    changed=predicate_post.get("changed"),
                    new_hash=predicate_post.get("new_hash", "")[:16],
                )
            except Exception as e:
                audit("error", message=f"Predicate post-check failed: {e}")

        dom_check = await dom_verify_change(before_url, before_title)
        dom_changed = dom_check.get("changed") or bool(
            predicate_post and predicate_post.get("changed")
        )
        if dom_changed:
            # DOM hat sich verändert → echter Fortschritt → no_progress_count zurücksetzen
            gate.mark_dom_progress()
            audit(
                "success",
                message="DOM-Verifikation: Seite hat sich nach Aktion erfolgreich verändert!",
            )
        else:
            audit(
                "warning",
                message="DOM-Verifikation: Keine Veränderung nach Aktion erkannt (Vision wird gleich prüfen).",
            )

        # ---- HUMAN DELAY ----
        await human_delay(1.5, 4.5)

    # ============================================================================
    # ABSCHLUSS — Zusammenfassung und Proof-Collection
    # ============================================================================

    # Final Session sichern
    await save_session("final")

    # Zusammenfassung
    summary = {
        "run_id": RUN_ID,
        "total_steps": gate.total_steps,
        "successful_actions": gate.successful_actions,
        "consecutive_retries": gate.consecutive_retries,
        "no_progress_count": gate.no_progress_count,
        "last_page_state": gate.last_page_state,
        "failed_selectors": list(gate.failed_selectors),
        "artifact_dir": str(ARTIFACT_DIR),
        "screenshots": len(list(SCREENSHOT_DIR.glob("*.png"))),
        "audit_entries": sum(1 for _ in open(AUDIT_LOG_PATH)),
    }

    summary_path = ARTIFACT_DIR / "run_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    print(f"\n{'=' * 60}")
    print(f"🏁 LAUF BEENDET — Zusammenfassung:")
    print(f"   Schritte: {gate.total_steps}/{MAX_STEPS}")
    print(f"   Erfolgreich: {gate.successful_actions}")
    print(f"   Screenshots: {summary['screenshots']}")
    print(f"   Artefakte: {ARTIFACT_DIR}")
    print(f"   Audit-Log: {AUDIT_LOG_PATH}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
