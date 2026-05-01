"""canary_runner.py — Live EUR Canary (SOTA #170)."""
from __future__ import annotations
import json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

CANARY_DIR = Path("/tmp/heypiggy-canary")
STEALTH_RUNNER = Path(os.environ.get("STEALTH_RUNNER_PATH", str(Path.home() / "dev/stealth-runner")))

def setup() -> Path:
    CANARY_DIR.mkdir(parents=True, exist_ok=True)
    run_dir = CANARY_DIR / f"canary_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir

def run_survey(run_dir: Path) -> dict:
    results = {"timestamp": datetime.now(timezone.utc).isoformat(), "phases": {}, "eur_earned": 0.0}
    script = STEALTH_RUNNER / "main.py"
    if script.exists():
        cmd = ["python3", str(script), "https://heypiggy.com/?page=dashboard"]
    else:
        cmd = ["playstealth", "launch", "--url", "https://heypiggy.com/?page=dashboard", "--json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        results["phases"]["survey_run"] = {"exit_code": proc.returncode, "stdout": proc.stdout[-2000:], "stderr": proc.stderr[-1000:]}
    except subprocess.TimeoutExpired:
        results["phases"]["survey_run"] = {"error": "timeout 300s"}
    except FileNotFoundError:
        results["phases"]["survey_run"] = {"error": "runner not found"}
    return results

def main():
    run_dir = setup()
    print(f"🚀 Canary: {run_dir.name}")
    results = run_survey(run_dir)
    (run_dir / "report.json").write_text(json.dumps(results, indent=2, default=str))
    eur = results.get("eur_earned", 0)
    print(f"{'💰' if eur > 0 else '❌'} EUR = {eur:.2f} | Report: {run_dir}/report.json")

if __name__ == "__main__":
    main()
