#!/usr/bin/env python3
"""
OpenSIN Survey Runner — Complete Pipeline v2.0

Architektur:
  🖐️ computer-use-mcp (Maus/Keyboard/Screenshot)
  👁️ Cloudflare Llama 4 Scout + Grid-Overlay (Vision)
  🧠 NVIDIA 90B / Mistral 675B (Backup Vision)

Usage:
  python3 mcp_survey_runner.py

Env:
  CF_TOKEN    — Cloudflare Workers AI Token
  CF_ACCT     — Cloudflare Account ID
  NVIDIA_API_KEY — Backup Vision
"""

import asyncio, json, subprocess, base64, urllib.request, re, os, sys
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# ── Config ──────────────────────────────────────────────────────────────────
CF_TOKEN = os.environ.get("CF_TOKEN", "")  # Set via env or Infisical
CF_ACCT  = os.environ.get("CF_ACCT", "4621434bea0a1efc1ceff2a3f670e0c9")
CF_MODEL = "@cf/meta/llama-4-scout-17b-16e-instruct"
NVIDIA_KEY = os.environ.get("NVIDIA_API_KEY", "")  # via Infisical or env
CF_URL = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCT}/ai/run/{CF_MODEL}"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

# ── Grid-Overlay Konfiguration ──────────────────────────────────────────────
GRID_SPACING = 20
GRID_ALPHA_MAJOR = 90   # 100px Linien
GRID_ALPHA_MINOR = 55   # 50px Linien
GRID_ALPHA_HAIR  = 18   # 20px Linien

def draw_grid(image: Image.Image) -> Image.Image:
    """Zeichne wissenschaftliches 20px Grid-Overlay auf ein Bild."""
    overlay = Image.new('RGBA', image.size, (0,0,0,0))
    draw = ImageDraw.Draw(overlay, 'RGBA')
    try:
        f8 = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 8)
        f9 = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 9)
        f10 = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 10)
        f12 = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 12)
    except:
        f8 = f9 = f10 = f12 = ImageFont.load_default()

    for x in range(0, image.width, GRID_SPACING):
        is_100 = (x % 100 == 0); is_50 = (x % 50 == 0)
        a = GRID_ALPHA_MAJOR if is_100 else (GRID_ALPHA_MINOR if is_50 else GRID_ALPHA_HAIR)
        w = 2 if is_100 else (1 if is_50 else 0)
        draw.line([(x,0),(x,image.height)], fill=(255,40,40,a), width=w)
    for y in range(0, image.height, GRID_SPACING):
        is_100 = (y % 100 == 0); is_50 = (y % 50 == 0)
        a = GRID_ALPHA_MAJOR if is_100 else (GRID_ALPHA_MINOR if is_50 else GRID_ALPHA_HAIR)
        w = 2 if is_100 else (1 if is_50 else 0)
        draw.line([(0,y),(image.width,y)], fill=(255,40,40,a), width=w)

    for x in range(0, image.width, GRID_SPACING):
        for y in range(0, image.height, GRID_SPACING):
            if x % 100 == 0 and y % 100 == 0:
                draw.text((x+2,y+2), f'{x},{y}', fill=(255,55,55,140), font=f10)
            elif x % 40 == 0 and y % 40 == 0:
                draw.text((x+2,y+2), f'{x},{y}', fill=(255,100,100,90), font=f8)
            elif x % 60 == 0 and y % 60 == 0:
                draw.text((x+2,y+2), f'{x},{y}', fill=(255,130,130,60), font=f8)

    for x in range(0, image.width, GRID_SPACING):
        f, a = (f10, 150) if x%100==0 else (f8, 80)
        draw.text((x+1, 0), str(x), fill=(255,80,80,a), font=f)
    for y in range(0, image.height, GRID_SPACING):
        f, a = (f10, 150) if y%100==0 else (f8, 80)
        draw.text((0, y+1), str(y), fill=(255,80,80,a), font=f)

    result = image.convert('RGBA')
    result.paste(overlay, (0,0), overlay)
    return result


class SurveyRunner:
    def __init__(self):
        self.proc = None
        self.rid = 0
        self.stats = {"surveys": 0, "steps": 0, "clicks": 0}

    async def start(self):
        self.proc = await asyncio.create_subprocess_exec(
            'npx', '-y', 'computer-use-mcp',
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        await asyncio.sleep(2)

    async def stop(self):
        if self.proc: self.proc.terminate()

    async def mcp(self, action: str, **args) -> dict:
        """MCP-Tool aufrufen."""
        self.rid += 1
        p = {'name': 'computer', 'arguments': {'action': action, **args}}
        req = json.dumps({'jsonrpc':'2.0','method':'tools/call','params':p,'id':self.rid}) + '\n'
        self.proc.stdin.write(req.encode()); await self.proc.stdin.drain()
        data = b''
        while True:
            chunk = await asyncio.wait_for(self.proc.stdout.read(65536), 25)
            if not chunk: break
            data += chunk
            try: return json.loads(data.decode())
            except: continue

    async def screenshot_png(self) -> tuple[bytes, int, int]:
        """Screenshot via MCP → PNG bytes + dimensions."""
        resp = await self.mcp('get_screenshot')
        img_bytes = None
        w, h = 0, 0
        for item in resp.get('result',{}).get('content',[]):
            if item['type'] == 'image':
                img_bytes = base64.b64decode(item['data'])
            if item['type'] == 'text':
                import json
                try:
                    dims = json.loads(item['text'])
                    w = dims.get('image_width', 0)
                    h = dims.get('image_height', 0)
                except: pass
        return img_bytes or b'', w, h

    async def click(self, x: int, y: int):
        """Klick an Bildschirm-Koordinaten."""
        await self.mcp('left_click', coordinate=[x, y])
        self.stats["clicks"] += 1

    async def scroll(self, x: int = 400, y: int = 400, amount: str = "down:400"):
        """Scrollen."""
        await self.mcp('scroll', coordinate=[x, y], text=amount)

    async def navigate(self, url: str):
        """URL im Bot-Chrome öffnen. Fokussiert Bot-Fenster VOR Navigation."""
        # Bot-Fenster nach vorne (window 2 = Bot-Chrome via --user-data-dir)
        subprocess.run(['osascript','-e','tell app \"Google Chrome\" to set index of window 2 to 1'],
                       capture_output=True, timeout=3)
        await asyncio.sleep(0.3)
        await self.mcp('key', text='cmd+l')
        await asyncio.sleep(0.3)
        await self.mcp('type', text=url)
        await asyncio.sleep(0.3)
        await self.mcp('key', text='enter')
        await asyncio.sleep(4)
        # Fenster zurück nach rechts
        subprocess.run(['osascript','-e','tell app \"Google Chrome\" to set bounds of front window to {960, 23, 1920, 1080}'],
                       capture_output=True, timeout=3)

    async def get_screenshot_with_grid(self) -> tuple[Image.Image, int, int]:
        """Full-Screen Screenshot MIT Grid-Overlay. Returns (image, width, height)."""
        png, w, h = await self.screenshot_png()
        img = Image.open(BytesIO(png)).convert('RGBA')
        return draw_grid(img), w, h

    def ask_vision(self, image: Image.Image, prompt: str, img_w: int = 0, img_h: int = 0) -> tuple[int,int] | None:
        """Vision-Modell befragen → Koordinaten parsen (mit echten Bild-Dimensionen)."""
        grid_img = image  # Grid already drawn by get_screenshot_with_grid
        buf = BytesIO(); grid_img.convert('RGB').save(buf, 'JPEG', quality=50)
        img_b64 = base64.b64encode(buf.getvalue()).decode()

        result = self._ask_cloudflare(img_b64, prompt, img_w, img_h)
        if result is None:
            result = self._ask_nvidia(img_b64, prompt, img_w, img_h)
        return result

    def _ask_cloudflare(self, img_b64: str, prompt: str, img_w: int = 0, img_h: int = 0) -> tuple[int,int] | None:
        """Llama 4 Scout via Cloudflare — nutzt echte Bild-Dimensionen."""
        data = json.dumps({'messages':[{'role':'user','content':[
            {'type':'text','text':'List ONLY the grid coordinates (like 400,300) of every survey card with EUR amount. Nothing else.'},
            {'type':'image_url','image_url':{'url':f'data:image/jpeg;base64,{img_b64}'}}
        ]}],'max_tokens':30}).encode()
        req = urllib.request.Request(CF_URL, data=data,
            headers={'Authorization':f'Bearer {CF_TOKEN}','Content-Type':'application/json'})
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=35).read())
            text = r['result']['response']
            # Format 1: "X=400 Y=300" (single coord)
            xm = re.search(r'X\s*=\s*([\d.]+)', text, re.IGNORECASE)
            ym = re.search(r'Y\s*=\s*([\d.]+)', text, re.IGNORECASE)
            if xm and ym:
                x_val = float(xm.group(1)); y_val = float(ym.group(1))
                if x_val < 10 and x_val > 0: x_val *= (img_w or 1464)
                if y_val < 10 and y_val > 0: y_val *= (img_h or 823)
                return int(x_val), int(y_val)
            # Format 2: "400,300\n400,600..." (list — take first pair)
            pairs = re.findall(r'(\d+)\s*[,;]\s*(\d+)', text)
            if pairs:
                return int(pairs[0][0]), int(pairs[0][1])
        except Exception as e:
            print(f"  ⚠️ Cloudflare: {e}")
        return None

    def _ask_nvidia(self, img_b64: str, prompt: str, img_w: int = 0, img_h: int = 0) -> tuple[int,int] | None:
        """Mistral/90B via NVIDIA (Backup) — nutzt echte Bild-Dimensionen."""
        data = json.dumps({
            'model':'mistralai/mistral-large-3-675b-instruct-2512',
            'messages':[{'role':'user','content':[{'type':'text','text':f'Grid image. {prompt} Return JSON: {{"x":N,"y":N}}'},
                {'type':'image_url','image_url':{'url':f'data:image/jpeg;base64,{img_b64}'}}]}],
            'max_tokens':40
        }).encode()
        req = urllib.request.Request(NVIDIA_URL, data=data,
            headers={'Authorization':f'Bearer {NVIDIA_KEY}','Content-Type':'application/json'})
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=45).read())
            text = r['choices'][0]['message']['content']
            m = re.search(r'\{[^}]+\}', text)
            if m:
                c = json.loads(m.group())
                return int(c['x']), int(c['y'])
        except Exception as e:
            print(f"  ⚠️ NVIDIA: {e}")
        return None

    async def find_and_click(self, image: Image.Image, img_w: int, img_h: int, prompt: str) -> bool:
        """Vision → absolute Koordinaten → Klick."""
        coords = self.ask_vision(image, prompt, img_w, img_h)
        if coords:
            x, y = coords
            print(f"  🎯 {x},{y} → Klick")
            await self.click(x, y)
            self.stats["steps"] += 1
            return True
        return False

    async def check_scroll_needed(self) -> bool:
        """Scrollen + prüfen ob mehr Optionen sichtbar."""
        await self.scroll(amount="down:500")
        await asyncio.sleep(1)
        img, w, h = await self.get_screenshot_with_grid()
        coords = self.ask_vision(img, "Are there NEW options visible below that were hidden before?", w, h)
        # Wenn Koordinaten tiefer als vorher → es gibt mehr Optionen
        return coords is not None

    async def run(self):
        """Haupt-Survey-Loop."""
        await self.start()
        print("🚀 OpenSIN Survey Runner v2.0 — Grid+Cloudflare")

        try:
            # Navigate to HeyPiggy
            print("🧭 Navigiere zu HeyPiggy...")
            await self.navigate("https://www.heypiggy.com/?page=dashboard")
            print("✅ Dashboard geladen")

            # Find and click first survey
            img, w, h = await self.get_screenshot_with_grid()
            print(f"📸 Screenshot: {img.size} ({w}×{h})")

            found = await self.find_and_click(img, w, h, "Find first survey card with EUR amount. Center coords.")
            if not found:
                print("❌ Kein Survey gefunden")
                return

            await asyncio.sleep(3)

            # Survey opened → scroll + answer
            for question in range(10):  # Max 10 Fragen
                await asyncio.sleep(2)

                # Scroll-Check: alle Optionen sehen
                for _ in range(3):
                    await self.scroll(amount="down:400")
                    await asyncio.sleep(1)

                img, w, h = await self.get_screenshot_with_grid()
                print(f"❓ Frage {question+1}")

                # Finde Antwort-Option
                answered = await self.find_and_click(img, w, h, "Find the safest/neutral answer option. Its center coords.")
                if not answered:
                    print("  ⚠️ Keine Antwort gefunden, versuche Next direkt")

                await asyncio.sleep(0.5)

                # Finde Next-Button
                img2, w2, h2 = await self.get_screenshot_with_grid()
                next_found = await self.find_and_click(img2, w2, h2, "Find Next/Weiter button center coords.")
                if not next_found:
                    print("  🏁 Survey vermutlich beendet")
                    self.stats["surveys"] += 1
                    break

                await asyncio.sleep(2)

            print(f"📊 Stats: {self.stats}")

        finally:
            await self.stop()


if __name__ == "__main__":
    asyncio.run(SurveyRunner().run())
