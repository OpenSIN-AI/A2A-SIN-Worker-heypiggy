"""canary_runner.py — Automated EUR Canary on heypiggy.com."""
from __future__ import annotations
import json, os, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

CANARY_DIR = Path("/tmp/heypiggy-canary")
SCREEN_FOLLOW_DIR = CANARY_DIR / "recordings"
AUDIT_DIR = CANARY_DIR / "audit"
STEALTH_RUNNER = os.environ.get("STEALTH_RUNNER_PATH", os.path.expanduser("~/dev/stealth-runner"))


def setup():
    CANARY_DIR.mkdir(parents=True, exist_ok=True)
    SCREEN_FOLLOW_DIR.mkdir(exist_ok=True)
    AUDIT_DIR.mkdir(exist_ok=True)
    return CANARY_DIR / f"canary_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"


def run_pipeline(run_dir: Path) -> dict:
    results = {"timestamp": datetime.now(timezone.utc).isoformat(), "phases": {}, "eur_earned": 0.0}

    # Phase 1: Check environment
    results["phases"]["env_check"] = {
        "skylight": bool(subprocess.run(["which", "skylight-cli"], capture_output=True).returncode == 0),
        "playstealth": bool(subprocess.run(["which", "playstealth"], capture_output=True).returncode == 0),
        "unmask": bool(subprocess.run(["which", "unmask"], capture_output=True).returncode == 0),
        "screen_follow": bool(subprocess.run(["which", "screen-follow"], capture_output=True).returncode == 0),
    }

    # Phase 2: Start recording
    rec_proc = subprocess.Popen(
        ["screen-follow", "record", "--video", "--out", str(SCREEN_FOLLOW_DIR)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    results["phases"]["recording"] = {"pid": rec_proc.pid}

    # Phase 3: Run stealth-runner survey
    try:
        sr_result = subprocess.run(
            ["python3", "-m", "runner.state_machine", "https://www.heypiggy.com/"],
            capture_output=True, text=True, timeout=300,
            cwd=STEALTH_RUNNER,
            env={**os.environ, "VISION_FREE_PATH": "1"},
        )
        results["phases"]["survey_run"] = {
            "exit_code": sr_result.returncode,
            "stdout": sr_result.stdout[-2000:],
            "stderr": sr_result.stderr[-2000:],
        }
    except subprocess.TimeoutExpired:
        results["phases"]["survey_run"] = {"error": "timeout after 300s"}
    except Exception as e:
        results["phases"]["survey_run"] = {"error": str(e)}

    # Phase 4: Stop recording
    subprocess.run(["screen-follow", "stop"], capture_output=True, timeout=10)
    results["phases"]["recording"]["stopped"] = True

    # Phase 5: Try to extract earnings
    try:
        audit_logs = list(Path(AUDIT_DIR).glob("*.jsonl"))
        if audit_logs:
            log = audit_logs[-1].read_text()
            if "earnings_eur" in log:
                for line in log.strip().split("\n"):
                    try:
                        data = json.loads(line)
                        eur = data.get("earnings_eur", data.get("context", {}).get("earnings_eur", 0))
                        if eur:
                            results["eur_earned"] = float(eur)
                    except (json.JSONDecodeError, ValueError):
                        pass
    except Exception as e:
        results["phases"]["earnings_extract"] = {"error": str(e)}

    return results


def main():
    run_dir = setup()
    print(f"🚀 Canary Run: {run_dir.name}")
    print(f"   Dir: {run_dir}")

    results = run_pipeline(run_dir)

    report_path = run_dir / "report.json"
    report_path.write_text(json.dumps(results, indent=2, default=str))

    eur = results.get("eur_earned", 0)
    status = "✅ EUR > 0" if eur > 0 else "❌ EUR = 0"
    print(f"\n{status}")
    print(f"   Earnings: {eur:.2f} EUR")
    print(f"   Report: {report_path}")

    if eur > 0:
        print(f"🎉 EARNED {eur:.2f} EUR! Check screenshot dir: {SCREEN_FOLLOW_DIR}")


if __name__ == "__main__":
    main()
