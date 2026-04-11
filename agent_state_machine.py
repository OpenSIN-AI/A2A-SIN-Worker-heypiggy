import enum
import json
import uuid
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

class AgentState(enum.Enum):
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
    pass

@dataclass
class StepContext:
    state: AgentState = AgentState.INIT
    step_index: int = 0
    max_steps: int = 120
    no_progress_counter: int = 0
    last_page_fingerprint: str = ""
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_url: Optional[str] = None
    earnings_so_far: float = 0.0

# Transition table defining valid next states per state
TRANSITIONS: Dict[AgentState, List[AgentState]] = {
    AgentState.INIT: [AgentState.PREFLIGHT, AgentState.FAIL_SAFE, AgentState.ESCALATE],
    AgentState.PREFLIGHT: [AgentState.ACQUIRE_SESSION, AgentState.FAIL_SAFE, AgentState.ESCALATE],
    AgentState.ACQUIRE_SESSION: [AgentState.ASSESS_PAGE, AgentState.FAIL_SAFE, AgentState.ESCALATE],
    AgentState.ASSESS_PAGE: [
        AgentState.RESOLVE_BLOCKERS, AgentState.AUTHENTICATE, AgentState.ONBOARD,
        AgentState.DISCOVER_WORK, AgentState.EXECUTE_TASK_LOOP, AgentState.FAIL_SAFE, AgentState.ESCALATE
    ],
    AgentState.RESOLVE_BLOCKERS: [AgentState.ASSESS_PAGE, AgentState.FAIL_SAFE, AgentState.ESCALATE],
    AgentState.AUTHENTICATE: [AgentState.ONBOARD, AgentState.DISCOVER_WORK, AgentState.ASSESS_PAGE, AgentState.FAIL_SAFE, AgentState.ESCALATE],
    AgentState.ONBOARD: [AgentState.DISCOVER_WORK, AgentState.ASSESS_PAGE, AgentState.FAIL_SAFE, AgentState.ESCALATE],
    AgentState.DISCOVER_WORK: [AgentState.SELECT_TASK, AgentState.ASSESS_PAGE, AgentState.COMPLETE, AgentState.FAIL_SAFE, AgentState.ESCALATE],
    AgentState.SELECT_TASK: [AgentState.ENTER_TASK, AgentState.ASSESS_PAGE, AgentState.FAIL_SAFE, AgentState.ESCALATE],
    AgentState.ENTER_TASK: [AgentState.EXECUTE_TASK_LOOP, AgentState.ASSESS_PAGE, AgentState.FAIL_SAFE, AgentState.ESCALATE],
    AgentState.EXECUTE_TASK_LOOP: [
        AgentState.VALIDATE_OUTCOME, AgentState.EXECUTE_TASK_LOOP,
        AgentState.ASSESS_PAGE, AgentState.FAIL_SAFE, AgentState.ESCALATE
    ],
    AgentState.VALIDATE_OUTCOME: [AgentState.RECORD_RESULT, AgentState.ASSESS_PAGE, AgentState.FAIL_SAFE, AgentState.ESCALATE],
    AgentState.RECORD_RESULT: [AgentState.COMPLETE, AgentState.DISCOVER_WORK, AgentState.ASSESS_PAGE, AgentState.FAIL_SAFE, AgentState.ESCALATE],
    AgentState.COMPLETE: [AgentState.FAIL_SAFE, AgentState.ESCALATE], # Terminal unless escalated
    AgentState.FAIL_SAFE: [AgentState.ESCALATE], # Terminal, only escalation possible
    AgentState.ESCALATE: [] # Terminal
}

def step_context_advance(ctx: StepContext, new_state: AgentState, reason: str) -> None:
    """
    Validates transition, logs to structured JSON, raises IllegalTransitionError if invalid.
    """
    allowed_next = TRANSITIONS.get(ctx.state, [])
    if new_state not in allowed_next:
        raise IllegalTransitionError(f"Cannot transition from {ctx.state.name} to {new_state.name}")
    
    # Log the state change
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": ctx.run_id,
        "from_state": ctx.state.name,
        "to_state": new_state.name,
        "reason": reason,
        "step_index": ctx.step_index
    }
    print(f"[STATE MACHINE] {json.dumps(log_entry)}")
    
    ctx.state = new_state
    ctx.step_index += 1

def fail_safe(ctx: StepContext, reason: str) -> None:
    """
    Log reason, save ctx to checkpoint.json, print summary, exit cleanly.
    """
    print(f"[FAIL_SAFE] {reason}")
    try:
        step_context_advance(ctx, AgentState.FAIL_SAFE, reason)
    except IllegalTransitionError:
        ctx.state = AgentState.FAIL_SAFE
    
    checkpoint_file = Path(f"/tmp/heypiggy_run_{ctx.run_id}_checkpoint.json")
    try:
        with open(checkpoint_file, "w") as f:
            json.dump({
                "state": ctx.state.name,
                "step_index": ctx.step_index,
                "max_steps": ctx.max_steps,
                "no_progress_counter": ctx.no_progress_counter,
                "last_page_fingerprint": ctx.last_page_fingerprint,
                "run_id": ctx.run_id,
                "task_url": ctx.task_url,
                "earnings_so_far": ctx.earnings_so_far,
                "reason": reason
            }, f, indent=2)
        print(f"[FAIL_SAFE] Context saved to {checkpoint_file}")
    except Exception as e:
        print(f"[FAIL_SAFE] Failed to write checkpoint: {e}")
        
    print(f"[FAIL_SAFE] Exiting cleanly.")
    sys.exit(0)

def escalate(ctx: StepContext, reason: str, exception: Optional[Exception] = None) -> None:
    """
    Same as fail_safe but also prints ESCALATE to stderr, exit 1.
    """
    print(f"[ESCALATE] {reason}", file=sys.stderr)
    if exception:
        print(f"[ESCALATE] Exception: {exception}", file=sys.stderr)
        
    try:
        step_context_advance(ctx, AgentState.ESCALATE, reason)
    except IllegalTransitionError:
        ctx.state = AgentState.ESCALATE
        
    checkpoint_file = Path(f"/tmp/heypiggy_run_{ctx.run_id}_checkpoint.json")
    try:
        with open(checkpoint_file, "w") as f:
            json.dump({
                "state": ctx.state.name,
                "step_index": ctx.step_index,
                "run_id": ctx.run_id,
                "reason": reason,
                "exception": str(exception) if exception else None
            }, f, indent=2)
    except Exception:
        pass
        
    print(f"[ESCALATE] Exiting with error.", file=sys.stderr)
    sys.exit(1)

