import pytest
import sys
from agent_state_machine import (
    AgentState, StepContext, step_context_advance,
    fail_safe, escalate, IllegalTransitionError
)

def test_init_to_acquire_session():
    ctx = StepContext(state=AgentState.INIT)
    step_context_advance(ctx, AgentState.PREFLIGHT, "preflight ok")
    assert ctx.state == AgentState.PREFLIGHT
    step_context_advance(ctx, AgentState.ACQUIRE_SESSION, "acquire session ok")
    assert ctx.state == AgentState.ACQUIRE_SESSION

def test_authenticate_to_select_task():
    ctx = StepContext(state=AgentState.AUTHENTICATE)
    step_context_advance(ctx, AgentState.ONBOARD, "auth ok")
    assert ctx.state == AgentState.ONBOARD
    step_context_advance(ctx, AgentState.DISCOVER_WORK, "onboard ok")
    assert ctx.state == AgentState.DISCOVER_WORK
    step_context_advance(ctx, AgentState.SELECT_TASK, "work discovered")
    assert ctx.state == AgentState.SELECT_TASK

def test_execute_to_complete():
    ctx = StepContext(state=AgentState.EXECUTE_TASK_LOOP)
    step_context_advance(ctx, AgentState.VALIDATE_OUTCOME, "executed")
    assert ctx.state == AgentState.VALIDATE_OUTCOME
    step_context_advance(ctx, AgentState.RECORD_RESULT, "validated")
    assert ctx.state == AgentState.RECORD_RESULT
    step_context_advance(ctx, AgentState.COMPLETE, "recorded")
    assert ctx.state == AgentState.COMPLETE

def test_no_progress_fail_safe(monkeypatch):
    ctx = StepContext(state=AgentState.EXECUTE_TASK_LOOP)
    ctx.no_progress_counter = 15
    
    exited = False
    def mock_exit(code):
        nonlocal exited
        exited = True
        assert code == 0
        
    monkeypatch.setattr(sys, 'exit', mock_exit)
    
    if ctx.no_progress_counter >= 15:
        fail_safe(ctx, "no progress limit reached")
        
    assert exited
    assert ctx.state == AgentState.FAIL_SAFE

def test_escalate(monkeypatch):
    ctx = StepContext(state=AgentState.ASSESS_PAGE)
    
    exited = False
    def mock_exit(code):
        nonlocal exited
        exited = True
        assert code == 1
        
    monkeypatch.setattr(sys, 'exit', mock_exit)
    
    escalate(ctx, "retry exhausted", Exception("timeout"))
        
    assert exited
    assert ctx.state == AgentState.ESCALATE

def test_illegal_transition():
    ctx = StepContext(state=AgentState.INIT)
    with pytest.raises(IllegalTransitionError):
        step_context_advance(ctx, AgentState.COMPLETE, "invalid jump")

