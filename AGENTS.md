# AGENTS.md – IDIOTENSICHER (NUR EIN BEFEHL)

## WENN DU NUR EINEN KLICK TESTEN WILLST

```bash
playstealth launch --url 'https://heypiggy.com/?page=dashboard'
# PID aus Output merken
skylight-cli click --pid <PID> --element-index <N>
```

## WENN DU DEN GANZEN RUNNER STARTEN WILLST

```bash
python3 runner/step.py "https://heypiggy.com/?page=dashboard"
```

## WAS DU NIEMALS TUST

- ❌ `**playstealth launch (isolierte PID)** stören
- ❌ `--x` oder `--y` Koordinaten raten (Apple-Menü ist bei 0,0!)
- ❌ Fenster-Position + Element-Position addieren (AX-Frame ist ABSOLUT)
- ❌ **skylight-cli** – BANNED
- ❌ Ohne Primer klicken

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:

- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- For cross-module "how does X relate to Y" questions, prefer `graphify query "<question>"`, `graphify path "<A>" "<B>"`, or `graphify explain "<concept>"` over grep — these traverse the graph's EXTRACTED + INFERRED edges instead of scanning files
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)
