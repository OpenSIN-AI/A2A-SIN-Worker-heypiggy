#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for the typed OpenSIN worker state machine.

WHY THESE TESTS EXIST:
- The FSM is a safety primitive, so the legal paths must be executable and the
  illegal paths must fail loudly.
- Terminal helpers must checkpoint and exit deterministically because the worker
  depends on them for safe shutdown behavior.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_state_machine import (
    AgentState,
    IllegalTransitionError,
    StepContext,
    escalate,
    fail_safe,
    step_context_advance,
)


# WHY: The production dataclass requires explicit `state` and `step_index`, so
# this helper keeps the tests concise while still creating realistic contexts.
def make_context(state: AgentState) -> StepContext:
    """Create a minimal but realistic FSM context for tests."""

    return StepContext(state=state, step_index=0)


# WHY: Terminal helpers always write `checkpoint.json` into the current working
# directory. Running the tests inside a temp directory keeps the repository clean.
@pytest.fixture
def isolated_checkpoint_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run checkpoint-producing tests inside an isolated temporary directory."""

    monkeypatch.chdir(tmp_path)
    return tmp_path


# WHY: Repeated assertions against the checkpoint format should stay centralized
# so every terminal-path test validates the same artifact structure consistently.
def read_checkpoint(tmp_dir: Path) -> dict[str, object]:
    """Load the checkpoint written by fail-safe or escalation helpers."""

    checkpoint_path = tmp_dir / "checkpoint.json"
    assert checkpoint_path.exists(), "checkpoint.json was not written"
    return json.loads(checkpoint_path.read_text(encoding="utf-8"))


# WHY: This verifies the worker can move through the earliest bootstrap stages
# without being blocked by the transition table.
def test_init_prefight_acquire_session_happy_path() -> None:
    """INIT -> PREFLIGHT -> ACQUIRE_SESSION should be legal."""

    ctx = make_context(AgentState.INIT)
    step_context_advance(ctx, AgentState.PREFLIGHT, "preflight start")
    step_context_advance(ctx, AgentState.ACQUIRE_SESSION, "session acquisition start")

    assert ctx.state == AgentState.ACQUIRE_SESSION
    assert ctx.step_index == 2


# WHY: This covers the middle-of-flow account and task discovery progression the
# worker needs before it can actually enter a survey.
def test_authenticate_onboard_discover_select_happy_path() -> None:
    """AUTHENTICATE -> ONBOARD -> DISCOVER_WORK -> SELECT_TASK should be legal."""

    ctx = make_context(AgentState.AUTHENTICATE)
    step_context_advance(ctx, AgentState.ONBOARD, "credentials accepted")
    step_context_advance(ctx, AgentState.DISCOVER_WORK, "onboarding complete")
    step_context_advance(ctx, AgentState.SELECT_TASK, "tasks visible")

    assert ctx.state == AgentState.SELECT_TASK
    assert ctx.step_index == 3


# WHY: This confirms the worker can progress from active execution to final
# completion through the required validation and recording phases.
def test_execute_validate_record_complete_happy_path() -> None:
    """EXECUTE_TASK_LOOP -> VALIDATE_OUTCOME -> RECORD_RESULT -> COMPLETE should be legal."""

    ctx = make_context(AgentState.EXECUTE_TASK_LOOP)
    step_context_advance(ctx, AgentState.VALIDATE_OUTCOME, "task loop finished")
    step_context_advance(ctx, AgentState.RECORD_RESULT, "outcome validated")
    step_context_advance(ctx, AgentState.COMPLETE, "result persisted")

    assert ctx.state == AgentState.COMPLETE
    assert ctx.step_index == 3


# WHY: The no-progress threshold is a hard safety stop. This test proves that a
# stuck worker can always transition into FAIL_SAFE and emit a checkpoint.
def test_any_state_to_fail_safe_when_no_progress_threshold_reached(
    isolated_checkpoint_dir: Path,
) -> None:
    """Any state should be able to fail-safe once no-progress reaches the limit."""

    ctx = make_context(AgentState.EXECUTE_TASK_LOOP)
    ctx.no_progress_counter = 15

    with pytest.raises(SystemExit) as exit_info:
        if ctx.no_progress_counter >= 15:
            fail_safe(ctx, "no progress threshold reached")

    assert exit_info.value.code == 0
    assert ctx.state == AgentState.FAIL_SAFE

    checkpoint = read_checkpoint(isolated_checkpoint_dir)
    assert checkpoint["state"] == "FAIL_SAFE"
    assert checkpoint["reason"] == "no progress threshold reached"


# WHY: Retry exhaustion is the canonical escalation case. The test proves that
# escalation is callable, writes a checkpoint, and exits with a failure code.
def test_any_state_to_escalate_when_retry_exhaustion_is_detected(
    isolated_checkpoint_dir: Path,
) -> None:
    """Any state should be able to escalate after retry exhaustion."""

    ctx = make_context(AgentState.ASSESS_PAGE)

    with pytest.raises(SystemExit) as exit_info:
        escalate(ctx, "retry exhaustion simulated", exception=RuntimeError("timeout"))

    assert exit_info.value.code == 1
    assert ctx.state == AgentState.ESCALATE

    checkpoint = read_checkpoint(isolated_checkpoint_dir)
    assert checkpoint["state"] == "ESCALATE"
    assert checkpoint["reason"] == "retry exhaustion simulated"
    assert "RuntimeError('timeout')" in str(checkpoint["exception"])


# WHY: The entire point of the FSM is to reject impossible jumps. This test
# protects against accidental loosening of the transition table.
def test_invalid_transition_raises_illegal_transition_error() -> None:
    """A disallowed state jump should raise IllegalTransitionError."""

    ctx = make_context(AgentState.INIT)

    with pytest.raises(IllegalTransitionError):
        step_context_advance(ctx, AgentState.COMPLETE, "illegal shortcut")
