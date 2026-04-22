#!/usr/bin/env python3
# ================================================================================
# DATEI: playstealth_cli.py
# PROJEKT: A2A-SIN-Worker-heyPiggy
# ZWECK: Kleine Playwright+Stealth CLI für reproduzierbare Survey-Clicks
# ================================================================================

"""PlayStealth CLI.

Why: Wir wollen eine kleine, stabile Oberfläche für genau die Dinge, die
in Playwright wirklich funktionieren:

* HeyPiggy Seite öffnen
* Survey-Liste sichtbar machen
* genau eine Survey-Kachel anklicken

Alles andere bleibt bewusst draußen.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from collections.abc import Sequence

from playstealth_actions.answer_survey import run as answer_survey_run
from playstealth_actions.click_survey import run as click_survey_run
from playstealth_actions.inspect_survey import run as inspect_survey_run
from playstealth_actions.open_list import run as open_list_run
from playstealth_actions.state_store import load_state, state_path
from playstealth_actions.tool_registry import list_tools
from playstealth_actions.tool_manifest import format_manifest
from playstealth_actions.resume_survey import run as resume_survey_run
from playstealth_actions.run_survey import run as run_survey_run


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="playstealth", description="Playwright+Stealth helper CLI"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    open_cmd = sub.add_parser("open-list", help="Open HeyPiggy and show the survey list")
    open_cmd.add_argument(
        "--timeout-seconds", type=int, default=300, help="How long to wait for manual login"
    )

    click_cmd = sub.add_parser("click-survey", help="Click one survey card")
    click_cmd.add_argument(
        "--timeout-seconds", type=int, default=300, help="How long to wait for manual login"
    )
    click_cmd.add_argument("--index", type=int, default=0, help="Survey card index after scoring")

    inspect_cmd = sub.add_parser(
        "inspect-survey", help="Open one survey and print modal/question details"
    )
    inspect_cmd.add_argument(
        "--timeout-seconds", type=int, default=300, help="How long to wait for manual login"
    )
    inspect_cmd.add_argument("--index", type=int, default=0, help="Survey card index after scoring")

    answer_cmd = sub.add_parser(
        "answer-survey", help="Pick one answer in the survey modal and continue"
    )
    answer_cmd.add_argument(
        "--timeout-seconds", type=int, default=300, help="How long to wait for manual login"
    )
    answer_cmd.add_argument("--index", type=int, default=0, help="Survey card index after scoring")
    answer_cmd.add_argument("--option-index", type=int, default=0, help="Answer option index")

    run_cmd = sub.add_parser(
        "run-survey", help="Open one survey and try to advance through modal questions"
    )
    run_cmd.add_argument(
        "--timeout-seconds", type=int, default=300, help="How long to wait for manual login"
    )
    run_cmd.add_argument("--index", type=int, default=0, help="Survey card index after scoring")
    run_cmd.add_argument(
        "--max-steps", type=int, default=20, help="Maximum survey-modal steps to attempt"
    )

    resume_cmd = sub.add_parser(
        "resume-survey", help="Resume from the last saved PlayStealth state"
    )
    resume_cmd.add_argument(
        "--timeout-seconds", type=int, default=300, help="How long to wait for manual login"
    )
    resume_cmd.add_argument(
        "--max-steps", type=int, default=20, help="Maximum survey-modal steps to attempt"
    )

    sub.add_parser("tools", help="Print the PlayStealth tool registry")
    sub.add_parser("manifest", help="Print the PlayStealth tool manifest")
    sub.add_parser("state", help="Print the persisted PlayStealth state")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    if args.command == "open-list":
        return asyncio.run(open_list_run(args.timeout_seconds))
    if args.command == "click-survey":
        return asyncio.run(click_survey_run(args.timeout_seconds, args.index))
    if args.command == "inspect-survey":
        return asyncio.run(inspect_survey_run(args.timeout_seconds, args.index))
    if args.command == "answer-survey":
        return asyncio.run(answer_survey_run(args.timeout_seconds, args.index, args.option_index))
    if args.command == "run-survey":
        return asyncio.run(run_survey_run(args.timeout_seconds, args.index, args.max_steps))
    if args.command == "resume-survey":
        return asyncio.run(resume_survey_run(args.timeout_seconds, args.max_steps))
    if args.command == "tools":
        for tool in list_tools():
            print(f"{tool.name:20} {tool.status:10} {tool.module:40} {tool.purpose}")
        return 0
    if args.command == "manifest":
        print(format_manifest())
        return 0
    if args.command == "state":
        print(f"state_path: {state_path()}")
        print(load_state())
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
