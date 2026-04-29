#!/usr/bin/env python3
"""
OpenSIN Survey Runner v3.2 — cua-driver powered, dry-run, page-state detection

Architektur:
  cua-driver (click/screenshot/type via SkyLight — KEIN Cursor-Sprung)
  OCR-First Grid + SoM (Vision-Prompting)
  Cloudflare Llama 4 Scout / NVIDIA Mistral 675B (Backup)

Usage:
  python3 mcp_survey_runner.py              # Normaler Survey-Loop
  python3 mcp_survey_runner.py --dry-run     # Nur GUI + Vision, kein Klick
  python3 mcp_survey_runner.py --one-shot    # Nur EINEN Survey-Klick (Debug)
"""

import json, subprocess, base64, urllib.request, re, os, sys, time
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from panel_overrides import detect_panel, build_panel_prompt_block

# ── Config ──────────────────────────────────────────────────────────────────
CF_TOKEN   = os.environ.get("CF_TOKEN", "")
CF_ACCT    = os.environ.get("CF_ACCT", "4621434bea0a1efc1ceff2a3f670e0c9")
NVIDIA_KEY = os.environ.get("NVIDIA_API_KEY", "")
CF_URL     = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCT}/ai/run/@cf/meta/llama-4-scout-17b-16e-instruct"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
DRY_RUN    = '--dry-run' in sys.argv
ONE_SHOT   = '--one-shot' in sys.argv
_BOT_PID   = 54971

# ── Chrome PID + window_id ─────────────────────────────────────────────────
_WID_CACHE = None

def find_bot_window() -> tuple[int, int]:
    """Finde PID + window_id des Bot-Chrome-Tabs mit HeyPiggy.
    Sucht zuerst nach 'heypiggy' im Titel. Falls nicht gefunden:
    Nimmt das erste Fenster von PID _BOT_PID (46109). Niemals PID 2253.
    """
    global _WID_CACHE
    if _WID_CACHE: return _BOT_PID, _WID_CACHE

    r = subprocess.run(['cua-driver', 'call', 'list_windows'],
                       capture_output=True, text=True, timeout=10)
    try:
        data = json.loads(r.stdout)
        windows = data.get('structuredContent', data).get('windows', [])
        # 1. Durchgang: HeyPiggy im Titel
        for w in windows:
            title = (w.get('title') or '').lower()
            if 'heypiggy' in title and w.get('pid') != 2253:
                _WID_CACHE = w['window_id']
                return w['pid'], _WID_CACHE
        # 2. Durchgang: HeyPiggy egal welche PID (bevorzugt != 2253)
        best, best_pid = None, 0
        for w in windows:
            title = (w.get('title') or '').lower()
            if 'heypiggy' in title:
                if w['pid'] != 2253 and w['pid'] != best_pid:
                    best, best_pid = w, w['pid']
                elif not best:
                    best = w
        if best:
            _WID_CACHE = best['window_id']
            return best['pid'], _WID_CACHE
        # 3. Durchgang: Bot-Chrome Fenster (PID 46109) ohne Title
        for w in windows:
            if w.get('pid') == _BOT_PID:
                _WID_CACHE = w['window_id']
                return _BOT_PID, _WID_CACHE
        # 4. Fallback: höchste Chrome PID (letzter gestarteter Prozess)
        chrome_windows = [w for w in windows if w.get('app_name') == 'Google Chrome']
        if chrome_windows:
            by_pid = sorted(chrome_windows, key=lambda w: -w['pid'])
            best = by_pid[0]
            _WID_CACHE = best['window_id']
            return best['pid'], _WID_CACHE
    except (json.JSONDecodeError, KeyError, IndexError):
        pass
    return _BOT_PID, 0


def get_pid_wid() -> tuple[int, int]:
    return find_bot_window()

def get_current_url(pid: int, wid: int) -> str:
    try:
        r = subprocess.run(
            ['cua-driver', 'call', 'get_window_state', '--pid', str(pid), '--window-id', str(wid)],
            capture_output=True, text=True, timeout=10
        )
        data = json.loads(r.stdout)
        return data.get('structuredContent', data).get('url', '')
    except:
        return ''


# ── Grid-Overlay (OCR-First + SoM) ─────────────────────────────────────────
GRID_SPACING = 20
_FONTS = {}
def _get_font(size: int):
    if size not in _FONTS:
        try: _FONTS[size] = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', size)
        except: _FONTS[size] = ImageFont.load_default()
    return _FONTS[size]


def draw_grid(image: Image.Image, som_elements: list | None = None) -> Image.Image:
    """OCR-First Grid + Set-of-Mark (SoM) Overlay."""
    W, H = image.width, image.height
    overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, 'RGBA')
    f8 = _get_font(8); f10 = _get_font(10)

    for x in range(0, W, GRID_SPACING):
        draw.rectangle([x, 0, x+GRID_SPACING, H], outline=(255,60,60,5), width=0)
    for y in range(0, H, GRID_SPACING):
        draw.rectangle([0, y, W, y+GRID_SPACING], outline=(255,60,60,5), width=0)
    for x in range(0, W, 100):
        draw.line([(x,0),(x,H)], fill=(255,60,60,16), width=1)
    for y in range(0, H, 100):
        draw.line([(0,y),(W,y)], fill=(255,60,60,16), width=1)
    for y in range(0, H, 40):
        for x in range(0, W, 40):
            coord = f"{x},{y}"
            bb = draw.textbbox((0,0), coord, font=f8)
            tw, th = bb[2]-bb[0], bb[3]-bb[1]
            draw.rectangle([x+2, y+2, x+tw+5, y+th+5], fill=(0,0,0,130))
            draw.text((x+3, y+3), coord, fill=(255,200,100,155), font=f8)
    for y in range(0, H, 100):
        for x in range(0, W, 100):
            coord = f"\u25c6{x},{y}\u25c6"
            bb = draw.textbbox((0,0), coord, font=f10)
            tw, th = bb[2]-bb[0], bb[3]-bb[1]
            draw.rectangle([x+3, y+3, x+tw+6, y+th+6], fill=(0,0,0,180))
            draw.text((x+5, y+5), coord, fill=(255,220,120,210), font=f10)

    if som_elements:
        for idx, el in enumerate(som_elements):
            som_id = idx + 1
            x, y, w, h = el['x'], el['y'], el['w'], el['h']
            color = (0, 255, 128, 140) if el.get('tag','') in ('BUTTON','A','INPUT','SELECT') else (0, 200, 255, 120)
            draw.rectangle([x, y, x+w, y+h], outline=color, width=2)
            label = str(som_id)
            bb = draw.textbbox((0,0), label, font=f10)
            lw, lh = bb[2]-bb[0]+6, bb[3]-bb[1]+4
            lx = max(0, x-lw-2); ly = max(0, y-2)
            draw.rectangle([lx, ly, lx+lw, ly+lh], fill=(0,0,0,200))
            draw.rectangle([lx, ly, lx+lw, ly+lh], outline=color[:3]+(200,), width=1)
            draw.text((lx+3, ly+2), label, fill=(255,255,255,240), font=f10)

    result = image.convert('RGBA')
    result.paste(overlay, (0,0), overlay)
    return result


# ── cua-driver CLI Wrapper ─────────────────────────────────────────────────

def cua_call(tool: str, args: dict | None = None, quiet: bool = False) -> dict:
    """Rufe cua-driver Tool auf. KEIN Cursor-Sprung."""
    cmd = ['cua-driver', 'call', tool, '--raw']
    if args: cmd.append(json.dumps(args))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try: return json.loads(result.stdout)
    except: return {"raw_stdout": result.stdout[:200]}


def cua_screenshot_bytes() -> bytes:
    """Screenshot via cua-driver, OHNE Log-Spam. Nur PNG-Bytes."""
    subprocess.run(['cua-driver', 'call', 'screenshot', '--image-out', '/tmp/_cs.png'],
                   capture_output=True, timeout=15)
    with open('/tmp/_cs.png', 'rb') as f:
        return f.read()


def cua_click(x: int, y: int, pid: int | None = None, wid: int | None = None) -> bool:
    """Klick via cua-driver an Bildschirm-Koordinaten. Cursor bleibt stehen."""
    if pid is None or wid is None: pid, wid = get_pid_wid()
    resp = cua_call('click', {"pid": pid, "window_id": wid, "x": x, "y": y})
    return 'posted' in json.dumps(resp).lower()


def cua_scroll(pid: int | None = None, wid: int | None = None):
    """Scroll Down."""
    if pid is None or wid is None: pid, wid = get_pid_wid()
    cua_call('scroll', {"pid": pid, "window_id": wid, "direction": "down"})


def cua_get_ax_elements(pid: int | None = None, wid: int | None = None) -> list[dict]:
    """Extrahiere interaktive Elemente via Accessibility-Tree.
    Ersetzt JS-basiertes SoM (blockiert auf Chrome 147).
    Nutzt get_window_state → tree_markdown → regex.
    Liefert 50-300 Elemente mit [element_index, text, x, y, w, h].
    """
    if pid is None or wid is None: pid, wid = get_pid_wid()
    resp = cua_call('get_window_state', {"pid": pid, "window_id": wid})
    sc = resp.get('structuredContent', resp)
    markdown = sc.get('tree_markdown', '')
    if not markdown:
        return []
    elements = []
    pattern = re.compile(
        r'\[element_index\s+(\d+)\]\s*'
        r'(?:"([^"]*)"\s*)?'
        r'\[(\d+),(\d+),(\d+),(\d+)\]'
    )
    for m in pattern.finditer(markdown):
        elements.append({
            'element_index': int(m.group(1)),
            'text': (m.group(2) or '').strip()[:30],
            'x': int(m.group(3)), 'y': int(m.group(4)),
            'w': int(m.group(5)), 'h': int(m.group(6)),
        })
    return elements


# ── Grid-Screenshot (OCR + optional AX-SoM) ────────────────────────────────

def grid_screenshot(with_som: bool = False) -> tuple[Image.Image, int, int]:
    """Screenshot → OCR-Grid. Optional mit AX-Tree SoM Boxen.
    with_som=True ruft cua_get_ax_elements() auf und zeichnet Boxen.
    """
    png = cua_screenshot_bytes()
    img = Image.open(BytesIO(png)).convert('RGBA')
    pid, wid = get_pid_wid()

    som_elements = None
    som_count = 0
    if with_som:
        ax = cua_get_ax_elements(pid, wid)
        if ax:
            # Nur interaktive Elemente (Buttons, Links) behalten
            som_elements = [e for e in ax if e.get('w', 0) > 10 and e.get('h', 0) > 10]
            som_count = len(som_elements)

    img_grid = draw_grid(img, som_elements)

    W, H = img_grid.size
    f8 = _get_font(8)
    final = Image.new('RGBA', (W, H+26), (15,15,20,255))
    ld = ImageDraw.Draw(final)
    final.paste(img_grid, (0,0))
    ld.rectangle([0,H,W,H+26], fill=(15,15,20,250))
    label = f'cua-driver PID {pid} wid {wid}'
    if som_count: label += f' | AX-SoM {som_count} Elemente'
    if DRY_RUN: label += ' | DRY-RUN (kein Klick)'
    ld.text((3,H+4), label, fill=(255,190,100), font=f8)
    return final, pid, wid


# ── Vision (Cloudflare / NVIDIA) ───────────────────────────────────────────

def ask_vision(image: Image.Image, prompt: str) -> tuple[int,int] | None:
    buf = BytesIO(); image.convert('RGB').save(buf, 'JPEG', quality=50)
    full_prompt = f"Grid overlay visible. {prompt} Reply ONLY with format COORD=X,Y. Nothing else."
    text = ask_vision_text(image, full_prompt)
    if text:
        return _extract_coord(text)
    return None


def ask_vision_text(image: Image.Image, prompt: str) -> str:
    """Vision befragen → Rohtext (keine Koordinaten-Parsing)."""
    buf = BytesIO(); image.convert('RGB').save(buf, 'JPEG', quality=50)
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    data = json.dumps({
        'model': 'mistralai/mistral-large-3-675b-instruct-2512',
        'messages': [{'role':'user','content':[
            {'type':'text','text':prompt},
            {'type':'image_url','image_url':{'url':f'data:image/jpeg;base64,{img_b64}'}}
        ]}],'max_tokens':60
    }).encode()
    req = urllib.request.Request(NVIDIA_URL, data=data,
        headers={'Authorization':f'Bearer {NVIDIA_KEY}','Content-Type':'application/json'})
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=60).read())
        return resp['choices'][0]['message']['content']
    except: return ""


def _ask_cloudflare(img_b64: str, prompt: str) -> tuple[int,int] | None:
    """Llama 4 Scout via Cloudflare."""
    data = json.dumps({'messages':[{'role':'user','content':[
        {'type':'text','text':f'Grid overlay visible. {prompt} Reply: COORD=X,Y. Nothing else.'},
        {'type':'image_url','image_url':{'url':f'data:image/jpeg;base64,{img_b64}'}}
    ]}],'max_tokens':30}).encode()
    req = urllib.request.Request(CF_URL, data=data,
        headers={'Authorization':f'Bearer {CF_TOKEN}','Content-Type':'application/json'})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=35).read())
        text = r['result']['response']
        return _extract_coord(text)
    except: return None


def _ask_nvidia(img_b64: str, prompt: str) -> tuple[int,int] | None:
    """Mistral 675B via NVIDIA."""
    data = json.dumps({
        'model': 'mistralai/mistral-large-3-675b-instruct-2512',
        'messages': [{'role':'user','content':[
            {'type':'text','text':f'Grid overlay visible. {prompt} Reply: COORD=X,Y'},
            {'type':'image_url','image_url':{'url':f'data:image/jpeg;base64,{img_b64}'}}
        ]}],'max_tokens':30
    }).encode()
    req = urllib.request.Request(NVIDIA_URL, data=data,
        headers={'Authorization':f'Bearer {NVIDIA_KEY}','Content-Type':'application/json'})
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=60).read())
        text = r['choices'][0]['message']['content']
        return _extract_coord(text)
    except: return None


def _extract_coord(text: str) -> tuple[int,int] | None:
    """Extrahiere erstes Zahlenpaar aus Text."""
    m = re.search(r'COORD\s*[=:]\s*(\d+)\s*[,;]\s*(\d+)', text, re.I)
    if not m:
        xm = re.search(r'X\s*=\s*(\d+)', text, re.I)
        ym = re.search(r'Y\s*=\s*(\d+)', text, re.I)
        if xm and ym: m = (xm.group(1), ym.group(1))
    if not m:
        pairs = re.findall(r'(\d+)\s*[,;]\s*(\d+)', text)
        if pairs: m = pairs[0]
    if m:
        if isinstance(m, tuple): return int(m[0]), int(m[1])
        return int(m.group(1)), int(m.group(2))
    return None


# ── Page-State Detection ───────────────────────────────────────────────────

PAGE_STATES = {
    'dashboard':    'dashboard with survey cards',
    'survey_start': 'survey welcome or start page',
    'screener':     'screener / filter question about demographics',
    'question':     'survey question with answer options',
    'attention':    'attention check (select a specific answer)',
    'open_ended':   'open-ended text question (textarea)',
    'matrix':       'matrix / grid / table of radio buttons',
    'slider':       'slider / range / scale question',
    'survey_end':   'survey complete / thank you page',
    'dq':           'disqualified / quota full page',
    'login':        'login page (email/password)',
    'other':        'something else',
}

def detect_page_state(img: Image.Image, pid: int, wid: int) -> tuple[str, object]:
    url = get_current_url(pid, wid)
    panel = detect_panel(url, '')
    
    prompt = (
        'Identify the current page state from this list. '
        'Reply ONLY with the state name, nothing else.\n'
        'States: dashboard, screener, question, attention, '
        'open_ended, matrix, slider, survey_end, dq, login, other'
    )
    ans = ask_vision_text(img, prompt).strip().lower()
    best, best_len = 'other', 999
    for state in PAGE_STATES:
        if state in ans and len(state) < best_len:
            best, best_len = state, len(state)
    return best, panel


# ── Action Planner ─────────────────────────────────────────────────────────

def build_prompt(state: str, panel=None) -> tuple[str, str]:
    if state in ('dashboard', 'login'):
        base = 'Find the FIRST survey card with EUR reward on this dashboard. Reply: COORD=X,Y'
        action = 'survey_click'
    elif state in ('screener', 'question', 'attention'):
        base = 'Read the question. Find the BEST matching answer option that a thoughtful person would choose. Reply: COORD=X,Y'
        action = 'answer_click'
    elif state == 'open_ended':
        base = 'Find the text input field. Reply: COORD=X,Y'
        action = 'text_input'
    elif state in ('matrix', 'slider'):
        base = 'Find any clickable option (radio button, checkbox, draggable). Reply: COORD=X,Y'
        action = 'answer_click'
    elif state in ('survey_end', 'dq'):
        base = 'NO ACTION NEEDED'
        action = 'noop'
    else:
        base = 'Find the Next / Weiter / Submit / Continue button. Reply: COORD=X,Y'
        action = 'next_click'
    
    if panel:
        panel_block = build_panel_prompt_block(panel, '')
        if panel_block:
            base = f"{panel_block}\n\n{base}"
    
    return base, action


# ── Survey Runner ──────────────────────────────────────────────────────────

def extract_earnings(img: Image.Image) -> float:
    """Extrahiere EUR-Betrag aus Screenshot via Vision.
    Wird nach survey_end/dq State aufgerufen.
    Gibt 0.0 zurueck wenn nichts gefunden.
    """
    prompt = 'Find the EUR amount earned or reward on this page. Reply ONLY: EUR=1.23 or EUR=0'
    ans = ask_vision_text(img, prompt)
    m = re.search(r'EUR\s*=\s*([\d.]+)', ans, re.I)
    if m: return float(m.group(1))
    return 0.0


class SurveyRunner:
    def __init__(self):
        self.stats = {"surveys": 0, "steps": 0, "clicks": 0, "dry_run": 0, "earnings_eur": 0.0}
        self.pid, self.wid = get_pid_wid()

    def run(self):
        print(f"🤖 Survey Runner v3.2")
        print(f"   Bot-Chrome: PID={self.pid} wid={self.wid}")
        print(f"   Dein Cursor bleibt wo er ist.")
        if DRY_RUN: print(f"   ⚠️ DRY-RUN: Vision wird ausgefuehrt, KEIN Klick\n")

        # Pruefe ob wir ueberhaupt ein Fenster haben
        if not self.wid:
            print("❌ Kein Bot-Chrome Fenster gefunden!")
            print("   Starte: open -na 'Google Chrome' --args --user-data-dir=/tmp/heypiggy-bot")
            return

        print("📸 Screenshot + Grid...")
        img, _, _ = grid_screenshot()
        state, panel = detect_page_state(img, self.pid, self.wid)
        print(f"   Page-State: {state} | Panel: {panel.name if panel else 'None'}")

        # Survey-Loop
        max_rounds = 15 if not ONE_SHOT else 1
        for runde in range(1, max_rounds + 1):
            print(f"\n=== Runde {runde}/{max_rounds} ===")

            # State erkennen + Prompt bauen
            if runde > 1:
                img, _, _ = grid_screenshot()
                state, panel = detect_page_state(img, self.pid, self.wid)
                print(f"   State: {state} | Panel: {panel.name if panel else 'None'}")

            if state == 'noop':
                print(f"   🏁 Survey beendet (state={state})")
                break

            prompt, action_type = build_prompt(state, panel)

            if prompt == 'NO ACTION NEEDED':
                print(f"   🏁 Keine Aktion noetig")
                break

            # Vision
            print(f"   👁️ Vision ({state})...")
            coords = ask_vision(img, prompt)

            if not coords:
                print(f"   ⚠️ Keine Koordinate — versuche direkten Next-Versuch")
                coords = ask_vision(img, 'Find the Next/Weiter/Submit button. Reply: COORD=X,Y')

            if coords:
                x, y = coords
                print(f"  🎯 ({x},{y}) → {action_type.replace('_',' ')}")

                if DRY_RUN:
                    print(f"     ⚠️ DRY-RUN: Kein Klick")
                    self.stats["dry_run"] += 1
                else:
                    ok = cua_click(x, y, self.pid, self.wid)
                    print(f"     {'✅ Geklickt (Cursor frei)' if ok else '❌ Fehler'}")
                    self.stats["clicks"] += 1

                self.stats["steps"] += 1
                time.sleep(3)

                # Nach Klick: neuen Screenshot + State-Pruefung
                if not ONE_SHOT:
                    img2, _, _ = grid_screenshot()
                    state2, panel2 = detect_page_state(img2, self.pid, self.wid)
                    print(f"   → State nach Klick: {state2} | Panel: {panel2.name if panel2 else 'None'}")

                    if state2 in ('survey_end', 'dq', 'noop'):
                        print(f"   🏁 Survey beendet (state={state2})")
                        self.stats["surveys"] += 1
                        # EUR-Tracking
                        img_eur, _, _ = grid_screenshot()
                        eur = extract_earnings(img_eur)
                        self.stats["earnings_eur"] += eur
                        print(f"   💰 EUR: +{eur:.2f} (total: {self.stats['earnings_eur']:.2f})")
                        break
                    elif state2 == 'dashboard' and runde > 1:
                        print(f"   🏁 Zurueck auf Dashboard — naechster Survey?")
                        break
                    elif state2 in ('screener', 'question', 'attention', 'open_ended', 'matrix', 'slider'):
                        print(f"   ➡️ Naechste Frage")
                    else:
                        print(f"   ➡️ Weiter (state={state2})")
                    time.sleep(1)
            else:
                print(f"   ⚠️ Vision konnte nichts finden")
                cua_scroll(self.pid, self.wid)
                time.sleep(1)
                img, _, _ = grid_screenshot()
                state, panel = detect_page_state(img, self.pid, self.wid)
                if state in ('survey_end', 'dq', 'noop'):
                    print(f"   🏁 Survey beendet")
                    self.stats["surveys"] += 1
                    img_eur, _, _ = grid_screenshot()
                    eur = extract_earnings(img_eur)
                    self.stats["earnings_eur"] += eur
                    print(f"   💰 EUR: +{eur:.2f} (total: {self.stats['earnings_eur']:.2f})")
                    break

        # run_summary speichern
        summary = {
            "earnings_eur": round(self.stats["earnings_eur"], 2),
            "surveys_completed": self.stats["surveys"],
            "steps": self.stats["steps"],
            "clicks": self.stats["clicks"],
            "dry_run": DRY_RUN,
        }
        run_id = f"run_{int(time.time())}"
        os.makedirs(f"/tmp/heypiggy_{run_id}", exist_ok=True)
        with open(f"/tmp/heypiggy_{run_id}/run_summary.json", "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\n📊 Stats: {self.stats}")
        print(f"   run_summary: /tmp/heypiggy_{run_id}/run_summary.json")
        if DRY_RUN:
            print(f"   (Dry-Run: {self.stats['dry_run']} Aktionen waeren geklickt worden)")


def usage():
    print(__doc__.strip())
    print(f"\nFlags:")
    print(f"  --dry-run     Screenshot + Grid + Vision, KEIN Klick")
    print(f"  --one-shot    Nur EINEN Survey-Klick (Debug)")


if __name__ == "__main__":
    if '--help' in sys.argv or '-h' in sys.argv:
        usage()
        sys.exit(0)
    runner = SurveyRunner()
    runner.run()