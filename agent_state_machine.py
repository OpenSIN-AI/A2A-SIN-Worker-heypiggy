#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Typed finite state machine for the OpenSIN HeyPiggy worker.

WHY THIS MODULE EXISTS:
- The worker used to move through a mostly linear script with ad-hoc branching.
- That shape makes it hard to prove which phase the worker is currently in.
- It also makes fail-safe handling, escalation, and checkpointing inconsistent.

WHAT THIS MODULE PROVIDES:
- A strongly typed `AgentState` enum for every major worker phase.
- A `StepContext` dataclass that carries the live FSM metadata.
- A strict transition table that blocks invalid state jumps.
- Shared fail-safe and escalation helpers that always checkpoint context.

CONSEQUENCES:
- The worker can now reason about its own phase explicitly.
- Invalid phase jumps fail loudly instead of silently corrupting control flow.
- Debugging and recovery become easier because every transition is logged as JSON.
"""

from __future__ import annotations

import enum
import json
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Final


# WHY: A stable checkpoint filename makes it trivial for operators, tests, and
# recovery tooling to know where the latest context snapshot will be written.
CHECKPOINT_PATH: Final[Path] = Path("checkpoint.json")


class AgentState(enum.Enum):
    """
    Typed list of all allowed high-level worker phases.

    WHY THIS ENUM EXISTS:
    - Stringly typed phases are easy to mistype and hard to validate.
    - An enum gives us one canonical vocabulary for orchestration, tests,
      structured logging, and future recovery tooling.

    CONSEQUENCES:
    - Every transition is explicit and machine-checkable.
    - Tests can assert exact states instead of brittle free-form strings.
    """

    INIT = "INIT"
    PREFLIGHT = "PREFLIGHT"
    ACQUIRE_SESSION = "ACQUIRE_SESSION"
    ASSESS_PAGE = "ASSESS_PAGE"
    RESOLVE_BLOCKERS = "RESOLVE_BLOCKERS"
    AUTHENTICATE = "AUTHENTICATE"
    ONBOARD = "ONBOARD"
    DISCOVER_WORK = "DISCOVER_WORK"
    SELECT_TASK = "SELECT_TASK"
    ENTER_TASK = "ENTER_TASK"
    EXECUTE_TASK_LOOP = "EXECUTE_TASK_LOOP"
    VALIDATE_OUTCOME = "VALIDATE_OUTCOME"
    RECORD_RESULT = "RECORD_RESULT"
    COMPLETE = "COMPLETE"
    FAIL_SAFE = "FAIL_SAFE"
    ESCALATE = "ESCALATE"


class IllegalTransitionError(Exception):
    """
    Raised when the caller attempts a state jump not permitted by the FSM.

    WHY THIS CUSTOM EXCEPTION EXISTS:
    - A domain-specific exception makes illegal control-flow bugs obvious.
    - Catchers can distinguish FSM violations from unrelated runtime failures.
    """


@dataclass
class StepContext:
    """
    Runtime context that travels together with the worker FSM.

    WHY THESE FIELDS EXIST:
    - `state` tells us the current phase.
    - `step_index` counts successful transitions so operators can reason about
      progress and loop length.
    - `max_steps` gives the controller a hard safety ceiling.
    - `no_progress_counter` tracks repeated iterations with no visible progress.
    - `last_page_fingerprint` lets the worker compare current vs previous page.
    - `run_id` provides a globally unique execution identifier.
    - `task_url` remembers which survey/task is currently being processed.
    - `earnings_so_far` stores accumulated outcome value for reporting.

    CONSEQUENCES:
    - The worker can checkpoint enough data to recover or debug meaningfully.
    - Tests can build minimal contexts while still exercising real behavior.
    """

    state: AgentState
    step_index: int
    max_steps: int = 120
    no_progress_counter: int = 0
    last_page_fingerprint: str = ""
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_url: str | None = None
    earnings_so_far: float = 0.0


# WHY: Keeping the transition table as module-level data makes the legal phase
# graph visible, testable, and reusable from multiple worker entry points.
TRANSITION_TABLE: dict[AgentState, list[AgentState]] = {
    AgentState.INIT: [
        AgentState.PREFLIGHT,
        AgentState.FAIL_SAFE,
        AgentState.ESCALATE,
    ],
    AgentState.PREFLIGHT: [
        AgentState.ACQUIRE_SESSION,
        AgentState.FAIL_SAFE,
        AgentState.ESCALATE,
    ],
    AgentState.ACQUIRE_SESSION: [
        AgentState.ASSESS_PAGE,
        AgentState.FAIL_SAFE,
        AgentState.ESCALATE,
    ],
    AgentState.ASSESS_PAGE: [
        AgentState.RESOLVE_BLOCKERS,
        AgentState.AUTHENTICATE,
        AgentState.ONBOARD,
        AgentState.DISCOVER_WORK,
        AgentState.SELECT_TASK,
        AgentState.ENTER_TASK,
        AgentState.EXECUTE_TASK_LOOP,
        AgentState.VALIDATE_OUTCOME,
        AgentState.RECORD_RESULT,
        AgentState.COMPLETE,
        AgentState.FAIL_SAFE,
        AgentState.ESCALATE,
    ],
    AgentState.RESOLVE_BLOCKERS: [
        AgentState.ASSESS_PAGE,
        AgentState.FAIL_SAFE,
        AgentState.ESCALATE,
    ],
    AgentState.AUTHENTICATE: [
        AgentState.ONBOARD,
        AgentState.DISCOVER_WORK,
        AgentState.ASSESS_PAGE,
        AgentState.FAIL_SAFE,
        AgentState.ESCALATE,
    ],
    AgentState.ONBOARD: [
        AgentState.DISCOVER_WORK,
        AgentState.ASSESS_PAGE,
        AgentState.FAIL_SAFE,
        AgentState.ESCALATE,
    ],
    AgentState.DISCOVER_WORK: [
        AgentState.SELECT_TASK,
        AgentState.COMPLETE,
        AgentState.ASSESS_PAGE,
        AgentState.FAIL_SAFE,
        AgentState.ESCALATE,
    ],
    AgentState.SELECT_TASK: [
        AgentState.ENTER_TASK,
        AgentState.ASSESS_PAGE,
        AgentState.FAIL_SAFE,
        AgentState.ESCALATE,
    ],
    AgentState.ENTER_TASK: [
        AgentState.EXECUTE_TASK_LOOP,
        AgentState.ASSESS_PAGE,
        AgentState.FAIL_SAFE,
        AgentState.ESCALATE,
    ],
    AgentState.EXECUTE_TASK_LOOP: [
        AgentState.EXECUTE_TASK_LOOP,
        AgentState.VALIDATE_OUTCOME,
        AgentState.ASSESS_PAGE,
        AgentState.FAIL_SAFE,
        AgentState.ESCALATE,
    ],
    AgentState.VALIDATE_OUTCOME: [
        AgentState.RECORD_RESULT,
        AgentState.ASSESS_PAGE,
        AgentState.FAIL_SAFE,
        AgentState.ESCALATE,
    ],
    AgentState.RECORD_RESULT: [
        AgentState.COMPLETE,
        AgentState.DISCOVER_WORK,
        AgentState.ASSESS_PAGE,
        AgentState.FAIL_SAFE,
        AgentState.ESCALATE,
    ],
    AgentState.COMPLETE: [
        AgentState.FAIL_SAFE,
        AgentState.ESCALATE,
    ],
    AgentState.FAIL_SAFE: [
        AgentState.ESCALATE,
    ],
    AgentState.ESCALATE: [],
}


def _context_to_json_dict(ctx: StepContext) -> dict[str, object]:
    """
    Convert the dataclass into JSON-safe primitives.

    WHY THIS HELPER EXISTS:
    - `asdict()` keeps the conversion logic centralized.
    - The enum must be serialized as its readable name instead of a Python object.

    CONSEQUENCES:
    - Checkpoints and logs become deterministic and easy to inspect.
    """

    payload = asdict(ctx)
    payload["state"] = ctx.state.name
    return payload


def _write_checkpoint(ctx: StepContext, reason: str, exception: Exception | None = None) -> Path:
    """
    Persist the current FSM context to `checkpoint.json`.

    WHY THIS HELPER EXISTS:
    - Both fail-safe and escalation must checkpoint identically.
    - Centralizing the write logic avoids drift between the two exit paths.

    CONSEQUENCES:
    - Operators can always inspect one canonical recovery file.
    """

    checkpoint_payload = {
        **_context_to_json_dict(ctx),
        "reason": reason,
        "exception": repr(exception) if exception is not None else None,
        "checkpoint_timestamp": datetime.now(timezone.utc).isoformat(),
    }
    CHECKPOINT_PATH.write_text(
        json.dumps(checkpoint_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return CHECKPOINT_PATH


def _log_transition(ctx: StepContext, previous_state: AgentState, new_state: AgentState, reason: str) -> None:
    """
    Emit one structured JSON log entry for a successful transition.

    WHY THIS HELPER EXISTS:
    - Transition logging must be consistent across all callers.
    - JSON logs are easier to ingest into audit tooling than free-form text.

    CONSEQUENCES:
    - Every accepted state change can be correlated by `run_id` and step index.
    """

    log_entry = {
        "event": "state_transition",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": ctx.run_id,
        "step_index": ctx.step_index,
        "from_state": previous_state.name,
        "to_state": new_state.name,
        "reason": reason,
        "task_url": ctx.task_url,
        "no_progress_counter": ctx.no_progress_counter,
        "earnings_so_far": ctx.earnings_so_far,
    }
    print(json.dumps(log_entry, ensure_ascii=False))


def step_context_advance(ctx: StepContext, new_state: AgentState, reason: str) -> StepContext:
    """
    Validate and perform one FSM transition.

    WHY THIS FUNCTION EXISTS:
    - Callers should never mutate `ctx.state` directly because that bypasses the
      legal transition rules and destroys our audit trail.
    - This helper is the single gatekeeper for all normal phase changes.

    CONSEQUENCES:
    - Illegal transitions raise `IllegalTransitionError` immediately.
    - Successful transitions increment the step index and emit structured JSON.
    """

    previous_state = ctx.state
    allowed_next_states = TRANSITION_TABLE.get(previous_state, [])
    if new_state not in allowed_next_states:
        allowed_names = [state.name for state in allowed_next_states]
        raise IllegalTransitionError(
            f"Illegal transition {previous_state.name} -> {new_state.name}. "
            f"Allowed: {allowed_names}"
        )

    _log_transition(ctx, previous_state, new_state, reason)
    ctx.state = new_state
    ctx.step_index += 1
    return ctx


def fail_safe(ctx: StepContext, reason: str) -> None:
    """
    Enter the fail-safe terminal path, checkpoint context, and exit cleanly.

    WHY THIS FUNCTION EXISTS:
    - Some situations are recoverable enough that we want a controlled stop
      instead of a hard crash.
    - We still need a checkpoint and a clear human-readable summary.

    CONSEQUENCES:
    - The process exits with code `0` after persisting the latest context.
    - If the caller was not already in `FAIL_SAFE`, we try to advance into it.
    """

    if ctx.state != AgentState.FAIL_SAFE:
        step_context_advance(ctx, AgentState.FAIL_SAFE, reason)

    checkpoint_path = _write_checkpoint(ctx, reason)
    summary = {
        "event": "fail_safe",
        "run_id": ctx.run_id,
        "state": ctx.state.name,
        "step_index": ctx.step_index,
        "reason": reason,
        "checkpoint": str(checkpoint_path),
    }
    print(json.dumps(summary, ensure_ascii=False))
    raise SystemExit(0)


def escalate(ctx: StepContext, reason: str, exception: Exception | None = None) -> None:
    """
    Enter the escalation terminal path, checkpoint context, and exit with error.

    WHY THIS FUNCTION EXISTS:
    - Retry exhaustion or unrecoverable contradictions must be surfaced loudly.
    - Operators need both stderr visibility and an on-disk checkpoint snapshot.

    CONSEQUENCES:
    - The process exits with code `1` after printing `ESCALATE` to stderr.
    - The optional exception is preserved in the checkpoint for later debugging.
    """

    if ctx.state != AgentState.ESCALATE:
        step_context_advance(ctx, AgentState.ESCALATE, reason)

    checkpoint_path = _write_checkpoint(ctx, reason, exception=exception)
    escalation_summary = {
        "event": "escalate",
        "run_id": ctx.run_id,
        "state": ctx.state.name,
        "step_index": ctx.step_index,
        "reason": reason,
        "exception": repr(exception) if exception is not None else None,
        "checkpoint": str(checkpoint_path),
    }
    print("ESCALATE", file=sys.stderr)
    print(json.dumps(escalation_summary, ensure_ascii=False), file=sys.stderr)
    raise SystemExit(1)
