# CMD 04: computer-use-mcp — All-in-One Desktop Control

**Quelle:** domdomegg/computer-use-mcp (Adam Jones), MIT-Lizenz
**URL:** https://github.com/domdomegg/computer-use-mcp
**npm:** `npx -y computer-use-mcp`
**Technologie:** nut.js (cross-platform Maus/Keyboard/Screenshot)

## Ersetzt ALLE unsere alten Tools:

| Aktion          | Altes Tool            | computer-use-mcp              |
| --------------- | --------------------- | ----------------------------- |
| Screenshot      | `screencapture -x`    | `get_screenshot` → base64 PNG |
| Maus bewegen    | `cliclick m:X,Y`      | `mouse_move [x,y]`            |
| Linksklick      | `cliclick c:X,Y`      | `left_click [x,y]`            |
| Rechtsklick     | —                     | `right_click [x,y]`           |
| Doppelklick     | —                     | `double_click [x,y]`          |
| Text tippen     | `osascript keystroke` | `type "text"`                 |
| Tastenkombi     | `osascript keystroke` | `key "ctrl+c"`                |
| Scrollen        | —                     | `scroll "down:500"`           |
| Cursor-Position | —                     | `get_cursor_position`         |

## Protokoll: MCP (Model Context Protocol)

- JSON-RPC 2.0 über stdin/stdout
- Server startet: `npx -y computer-use-mcp` (keine Installation, npx lädt on-the-fly)
- Befehl senden: `echo '{"jsonrpc":"2.0","method":"tools/call","params":{...},"id":1}' | npx -y computer-use-mcp`

## Verfügbare Aktionen:

```json
{
  "action": "get_screenshot"        // Screenshot als base64 PNG + Dimensionen
  "action": "mouse_move",           // Maus zu (x,y) bewegen
  "action": "left_click",           // Linksklick (optional mit coordinate)
  "action": "right_click",          // Rechtsklick
  "action": "double_click",         // Doppelklick
  "action": "left_click_drag",      // Klick+Ziehen
  "action": "scroll",               // Scrollen ("up"/"down"/"left"/"right":N)
  "action": "key",                  // Taste drücken ("ctrl+c", "enter")
  "action": "type",                 // Text tippen
  "action": "get_cursor_position"   // Aktuelle Mausposition
}
```

## Integration in Survey-Loop:

```python
# mcp_survey_runner.py
runner = MCPSurveyRunner()
await runner.start()

# Screenshot → Vision → Click → Verify
png = await runner.screenshot()
coords = await runner.vision_find(png, "center of first survey card")
await runner.click(coords[0], coords[1])
```
