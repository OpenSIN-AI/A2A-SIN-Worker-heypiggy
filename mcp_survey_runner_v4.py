#!/usr/bin/env python3
import json, subprocess, base64, urllib.request, re, os, sys, time
from io import BytesIO
from PIL import Image

CF_TOKEN   = os.environ.get("CF_TOKEN", "")
CF_ACCT    = os.environ.get("CF_ACCT", "4621434bea0a1efc1ceff2a3f670e0c9")
NVIDIA_KEY = os.environ.get("NVIDIA_API_KEY", "")
CF_URL     = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCT}/ai/run/@cf/meta/llama-4-scout-17b-16e-instruct"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
DRY_RUN    = '--dry-run' in sys.argv
ONE_SHOT   = '--one-shot' in sys.argv
_BOT_PID   = 54971

_WID_CACHE = None

def find_bot_window() -> tuple[int, int]:
    global _WID_CACHE
    if _WID_CACHE: return _BOT_PID, _WID_CACHE
    r = subprocess.run(['cua-driver', 'call', 'list_windows'],
                       capture_output=True, text=True, timeout=10)
    try:
        data = json.loads(r.stdout)
        windows = data.get('structuredContent', data).get('windows', [])
        for w in windows:
            title = (w.get('title') or '').lower()
            if 'heypiggy' in title and w.get('pid') != 2253:
                _WID_CACHE = w['window_id']
                return w['pid'], _WID_CACHE
        for w in windows:
            if w.get('pid') == _BOT_PID:
                _WID_CACHE = w['window_id']
                return _BOT_PID, _WID_CACHE
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

UI_TOP_EXCLUSION = 150
UI_BOTTOM_EXCLUSION = 50
UI_SIDE_MARGIN = 100

def validate_click_coordinates(x: int, y: int, img: Image.Image) -> tuple[int, int] | None:
    W, H = img.size
    in_content_area = (
        x >= UI_SIDE_MARGIN and x <= W - UI_SIDE_MARGIN
        and y >= UI_TOP_EXCLUSION and y <= H - UI_BOTTOM_EXCLUSION
    )
    return (x, y) if in_content_area else None

def cua_call(tool: str, args: dict | None = None) -> dict:
    cmd = ['cua-driver', 'call', tool]
    if args: cmd.append(json.dumps(args))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try: return json.loads(result.stdout)
    except: return {}

def cua_screenshot_bytes() -> bytes:
    subprocess.run(['cua-driver', 'call', 'screenshot', '--image-out', '/tmp/_cs.png'],
                   capture_output=True, timeout=15)
    with open('/tmp/_cs.png', 'rb') as f:
        return f.read()

def cua_click_element(pid: int, element_id: int) -> bool:
    resp = cua_call('click_element', {'pid': pid, 'element_id': element_id})
    return 'posted' in json.dumps(resp).lower()

def cua_get_window_state(pid: int, wid: int) -> dict:
    return cua_call('get_window_state', {'pid': pid, 'window_id': wid})

def get_ax_elements(pid: int, wid: int) -> list[dict]:
    state = cua_get_window_state(pid, wid)
    sc = state.get('structuredContent', state)
    markdown = sc.get('tree_markdown', '')
    elements = []
    pattern = re.compile(r'-\s*\[(\d+)\]\s*AX(\w+)\s*(?:"([^"]*)")?')
    for m in pattern.finditer(markdown):
        el_id = int(m.group(1))
        role = m.group(2)
        text = (m.group(3) or '').strip()
        clickable = role in ('Button', 'Link', 'RadioButton', 'CheckBox')
        elements.append({
            'id': el_id,
            'role': role,
            'text': text[:50],
            'clickable': clickable
        })
    return elements

def click_ax_element_by_text(elements: list[dict], target_text: str, pid: int) -> bool:
    target_lower = target_text.lower()
    for el in elements:
        if el['clickable'] and target_lower in el['text'].lower():
            print(f"   🎯 AX-Click: [{el['id']}] {el['role']} \"{el['text']}\"")
            if not DRY_RUN:
                return cua_click_element(pid, el['id'])
            else:
                print("     ⚠️ DRY-RUN: Kein Klick")
                return True
    return False

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

def ask_vision_text(image: Image.Image, prompt: str) -> str:
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

def detect_page_state(img: Image.Image, pid: int, wid: int) -> tuple[str, object]:
    from panel_overrides import detect_panel
    url = ''
    try:
        state = cua_get_window_state(pid, wid)
        sc = state.get('structuredContent', state)
        url = sc.get('url', '')
    except: pass
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

def build_prompt(state: str, panel=None) -> tuple[str, str]:
    if state in ('dashboard', 'login'):
        base = 'Find the FIRST survey card with EUR reward on this dashboard. Click it.'
        action = 'survey_click'
    elif state in ('screener', 'question', 'attention'):
        base = 'Read the question. Find the BEST matching answer option that a thoughtful person would choose. Click it.'
        action = 'answer_click'
    elif state == 'open_ended':
        base = 'Find the text input field. Click it.'
        action = 'text_input'
    elif state in ('matrix', 'slider'):
        base = 'Find any clickable option (radio button, checkbox, draggable). Click it.'
        action = 'answer_click'
    elif state in ('survey_end', 'dq'):
        base = 'NO ACTION NEEDED'
        action = 'noop'
    else:
        base = 'Find the Next / Weiter / Submit / Continue button. Click it.'
        action = 'next_click'
    if panel:
        from panel_overrides import build_panel_prompt_block
        panel_block = build_panel_prompt_block(panel, '')
        if panel_block:
            base = f"{panel_block}\n\n{base}"
    return base, action

def extract_earnings(img: Image.Image) -> float:
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
        print(f"🤖 Survey Runner v4.0 (AX-Tree Direct Click)")
        print(f"   Bot-Chrome: PID={self.pid} wid={self.wid}")
        if DRY_RUN: print(f"   ⚠️ DRY-RUN: Kein Klick\n")

        if not self.wid:
            print("❌ Kein Bot-Chrome Fenster!")
            return

        print("📸 Screenshot...")
        png = cua_screenshot_bytes()
        img = Image.open(BytesIO(png)).convert('RGB')
        state, panel = detect_page_state(img, self.pid, self.wid)
        print(f"   Page-State: {state} | Panel: {panel.name if panel else 'None'}")

        max_rounds = 15 if not ONE_SHOT else 1
        for runde in range(1, max_rounds + 1):
            print(f"\n=== Runde {runde}/{max_rounds} ===")

            if runde > 1:
                png = cua_screenshot_bytes()
                img = Image.open(BytesIO(png)).convert('RGB')
                state, panel = detect_page_state(img, self.pid, self.wid)
                print(f"   State: {state} | Panel: {panel.name if panel else 'None'}")

            if state == 'noop':
                print(f"   🏁 Survey beendet (state={state})")
                break

            prompt, action_type = build_prompt(state, panel)

            if prompt == 'NO ACTION NEEDED':
                print(f"   🏁 Keine Aktion noetig")
                break

            print(f"   🔍 AX-Tree Elements suchen ({action_type})...")
            ax_elements = get_ax_elements(self.pid, self.wid)

            clicked = False
            if action_type == 'survey_click':
                clicked = click_ax_element_by_text(ax_elements, 'EUR', self.pid)
            elif action_type == 'answer_click':
                clicked = click_ax_element_by_text(ax_elements, 'Weiter', self.pid)
                if not clicked:
                    clicked = click_ax_element_by_text(ax_elements, 'Next', self.pid)
                if not clicked:
                    clicked = click_ax_element_by_text(ax_elements, 'Submit', self.pid)
                if not clicked:
                    clicked = click_ax_element_by_text(ax_elements, 'Continue', self.pid)
            elif action_type == 'next_click':
                clicked = click_ax_element_by_text(ax_elements, 'Weiter', self.pid)
                if not clicked:
                    clicked = click_ax_element_by_text(ax_elements, 'Next', self.pid)
            elif action_type == 'text_input':
                clicked = click_ax_element_by_text(ax_elements, 'textarea', self.pid)

            if not clicked:
                print(f"   ⚠️ Keine AX-Element gefunden — Vision Fallback...")
                from mcp_survey_runner import ask_vision
                coords = ask_vision(img, prompt)
                if coords:
                    x, y = coords
                    valid = validate_click_coordinates(x, y, img)
                    if valid:
                        print(f"  🎯 ({x},{y}) → {action_type.replace('_',' ')} (Vision)")
                        if not DRY_RUN:
                            from mcp_survey_runner import cua_click
                            ok = cua_click(x, y, self.pid, self.wid)
                            print(f"     {'✅ Geklickt' if ok else '❌ Fehler'}")
                            self.stats["clicks"] += 1
                    else:
                        print(f"  🎯 ({x},{y}) → INVALID (UI-Bereich)")
                else:
                    print(f"   ⚠️ Nichts gefunden")

            self.stats["steps"] += 1
            time.sleep(3)

            if not ONE_SHOT:
                png2 = cua_screenshot_bytes()
                img2 = Image.open(BytesIO(png2)).convert('RGB')
                state2, panel2 = detect_page_state(img2, self.pid, self.wid)
                print(f"   → State nach Klick: {state2} | Panel: {panel2.name if panel2 else 'None'}")

                if state2 in ('survey_end', 'dq', 'noop'):
                    print(f"   🏁 Survey beendet (state={state2})")
                    self.stats["surveys"] += 1
                    img_eur = Image.open(BytesIO(cua_screenshot_bytes())).convert('RGB')
                    eur = extract_earnings(img_eur)
                    self.stats["earnings_eur"] += eur
                    print(f"   💰 EUR: +{eur:.2f} (total: {self.stats['earnings_eur']:.2f})")
                    break
                elif state2 == 'dashboard' and runde > 1:
                    print(f"   🏁 Zurueck auf Dashboard")
                    break
                elif state2 in ('screener', 'question', 'attention', 'open_ended', 'matrix', 'slider'):
                    print(f"   ➡️ Naechste Frage")
                    state = state2
                else:
                    print(f"   ➡️ Weiter (state={state2})")
                    state = state2
                time.sleep(1)

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

if __name__ == "__main__":
    runner = SurveyRunner()
    runner.run()
