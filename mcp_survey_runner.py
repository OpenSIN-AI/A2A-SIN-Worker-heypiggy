#!/usr/bin/env python3
"""
Survey automation using computer-use-mcp (MCP protocol via stdio).

Replaces: Bridge Extension + screencapture + cliclick + osascript
With: ONE MCP server (npx computer-use-mcp) via stdin/stdout JSON-RPC

Usage:
    python3 mcp_survey_runner.py
"""

import asyncio
import base64
import json
import os
import subprocess
import sys
import urllib.request

# Config
NVIDIA_KEY = os.environ.get(
    "NVIDIA_API_KEY", "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"
)
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
VISION_MODEL = "meta/llama-3.2-90b-vision-instruct"  # Better coords than 11B


class MCPSurveyRunner:
    def __init__(self):
        self.proc = None

    async def start(self):
        """Start MCP server as persistent subprocess."""
        self.proc = await asyncio.create_subprocess_exec(
            "npx", "-y", "computer-use-mcp",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        # Read initial MCP handshake (if any)
        await asyncio.sleep(1)

    async def stop(self):
        if self.proc:
            self.proc.terminate()
            await self.proc.wait()

    async def _call(self, method: str, params: dict) -> dict:
        """Send JSON-RPC call to MCP server, return result."""
        req = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
        payload = json.dumps(req) + "\n"
        self.proc.stdin.write(payload.encode())
        await self.proc.stdin.drain()

        # Read response — may contain large base64 images, use read() with buffer
        response_data = b""
        while True:
            chunk = await asyncio.wait_for(
                self.proc.stdout.read(65536), timeout=30
            )
            if not chunk:
                break
            response_data += chunk
            try:
                return json.loads(response_data.decode())
            except json.JSONDecodeError:
                continue
        return {"error": "no response"}

    async def screenshot(self) -> bytes:
        """Take screenshot, return PNG bytes."""
        resp = await self._call("tools/call", {
            "name": "computer",
            "arguments": {"action": "get_screenshot"},
        })
        for item in resp.get("result", {}).get("content", []):
            if item["type"] == "image":
                return base64.b64decode(item["data"])
        return b""

    async def click(self, x: int, y: int):
        """Move mouse to (x,y) and left click."""
        await self._call("tools/call", {
            "name": "computer",
            "arguments": {"action": "mouse_move", "coordinate": [x, y]},
        })
        await asyncio.sleep(0.3)
        await self._call("tools/call", {
            "name": "computer",
            "arguments": {"action": "left_click"},
        })

    async def vision_find(self, png_bytes: bytes, prompt: str) -> tuple[int, int] | None:
        """Use NVIDIA Vision to find coordinates of target."""
        img_b64 = base64.b64encode(png_bytes).decode()
        # Resize if > 200KB
        if len(img_b64) > 200000:
            # Quick resize via PIL if available, else send as-is
            try:
                from io import BytesIO
                from PIL import Image
                img = Image.open(BytesIO(png_bytes))
                img.thumbnail((512, 512))
                buf = BytesIO()
                img.save(buf, "PNG")
                img_b64 = base64.b64encode(buf.getvalue()).decode()
            except ImportError:
                pass

        payload = {
            "model": VISION_MODEL,
            "messages": [{
                "role": "system",
                "content": "Reply ONLY with two numbers separated by space: X Y. Nothing else.",
            }, {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                ],
            }],
            "max_tokens": 15,
        }

        req = urllib.request.Request(
            NVIDIA_URL,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {NVIDIA_KEY}",
                "Content-Type": "application/json",
            },
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=60).read())
        text = resp["choices"][0]["message"]["content"].strip()
        parts = text.replace(",", " ").split()
        if len(parts) >= 2:
            try:
                return int(parts[0]), int(parts[1])
            except ValueError:
                pass
        return None

    async def run_survey(self):
        """Main survey loop."""
        await self.start()
        try:
            print("🚀 Survey Runner gestartet")
            await asyncio.sleep(2)

            # Step 1: Screenshot
            print("📸 Screenshot...")
            png = await self.screenshot()
            print(f"   Bild: {len(png)} bytes")

            # Step 2: Find survey
            coords = await self.vision_find(png, "center of first survey card")
            if coords:
                print(f"🎯 Survey bei {coords}")
                await self.click(coords[0], coords[1])
                print("✅ Geklickt!")
                await asyncio.sleep(3)

                # Step 3: Verify
                png2 = await self.screenshot()
                coords2 = await self.vision_find(
                    png2, "center of Next or Weiter button"
                )
                if coords2:
                    print(f"🎯 Next bei {coords2}")
                    await self.click(coords2[0], coords2[1])
                    print("✅ Next geklickt!")

        finally:
            await self.stop()


if __name__ == "__main__":
    asyncio.run(MCPSurveyRunner().run_survey())
