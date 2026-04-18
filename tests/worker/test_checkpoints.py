from __future__ import annotations

import json
from pathlib import Path

import pytest

from worker.checkpoints import (
    AgentState,
    TRANSITION_TABLE,
    StepContext,
    archive_run_bundle,
    checkpoint_path,
    clear_checkpoint,
    escalate,
    fail_safe,
    find_latest_checkpoint,
    IllegalTransitionError,
    list_recent_archives,
    load_checkpoint,
    save_checkpoint,
    step_context_advance,
)


def test_save_and_load_checkpoint_roundtrip(tmp_path: Path) -> None:
    path = checkpoint_path(tmp_path / "heypiggy_run_run-1")
    ctx = StepContext(
        run_id="run-1",
        state=AgentState.EXECUTE_TASK_LOOP,
        step_index=10,
        task_url="https://heypiggy.com/survey/abc",
        no_progress_counter=2,
        last_page_fingerprint="hash123",
    )

    save_checkpoint(ctx, path)
    loaded = load_checkpoint(path)

    assert loaded is not None
    assert loaded.run_id == "run-1"
    assert loaded.state == AgentState.EXECUTE_TASK_LOOP
    assert loaded.step_index == 10
    assert loaded.task_url is not None
    assert loaded.task_url.endswith("/abc")


def test_step_context_advance_updates_and_persists(tmp_path: Path) -> None:
    path = checkpoint_path(tmp_path / "heypiggy_run_run-1")
    ctx = StepContext(run_id="run-1", state=AgentState.INIT)

    updated = step_context_advance(
        ctx,
        path,
        state=AgentState.PREFLIGHT,
        reason="preflight ok",
    )
    updated = step_context_advance(
        updated,
        path,
        state=AgentState.EXECUTE_TASK_LOOP,
        reason="start loop",
        step_index=12,
        task_url="https://heypiggy.com/survey/xyz",
        no_progress_counter=1,
        last_page_fingerprint="hash456",
    )

    assert updated.state == AgentState.EXECUTE_TASK_LOOP
    assert updated.step_index == 12
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["task_url"].endswith("/xyz")


def test_transition_table_has_fail_safe_and_escalate_terminal_states() -> None:
    assert TRANSITION_TABLE[AgentState.COMPLETE] == ()
    assert TRANSITION_TABLE[AgentState.FAIL_SAFE] == ()
    assert TRANSITION_TABLE[AgentState.ESCALATE] == ()


def test_illegal_transition_raises(tmp_path: Path) -> None:
    path = checkpoint_path(tmp_path / "heypiggy_run_run-1")
    ctx = StepContext(run_id="run-1", state=AgentState.INIT)

    with pytest.raises(IllegalTransitionError):
        step_context_advance(ctx, path, state=AgentState.COMPLETE, reason="skip ahead")


def test_load_checkpoint_returns_none_when_stale(tmp_path: Path) -> None:
    path = checkpoint_path(tmp_path / "heypiggy_run_run-1")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "state": "EXECUTE_TASK_LOOP",
                "step_index": 3,
                "saved_at": "2000-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    assert load_checkpoint(path) is None


def test_find_latest_checkpoint_returns_newest_fresh_checkpoint(tmp_path: Path) -> None:
    older = checkpoint_path(tmp_path / "heypiggy_run_old")
    newer = checkpoint_path(tmp_path / "heypiggy_run_new")
    save_checkpoint(StepContext(run_id="old", state=AgentState.INIT), older)
    save_checkpoint(StepContext(run_id="new", state=AgentState.INIT), newer)

    found = find_latest_checkpoint(tmp_path)

    assert found is not None
    path, checkpoint = found
    assert path == newer
    assert checkpoint.run_id == "new"


def test_clear_checkpoint_deletes_file(tmp_path: Path) -> None:
    path = checkpoint_path(tmp_path / "heypiggy_run_run-1")
    save_checkpoint(StepContext(run_id="run-1", state=AgentState.INIT), path)

    clear_checkpoint(path)

    assert not path.exists()


def test_archive_run_bundle_moves_artifacts_to_archive(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "heypiggy_run_run-1"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "run_summary.json").write_text("{}", encoding="utf-8")

    archived = archive_run_bundle(artifact_dir, "run-1", base_dir=tmp_path)

    assert archived.exists()
    assert archived.parent == tmp_path / "runs" / "archive"
    assert not artifact_dir.exists()


def test_fail_safe_writes_checkpoint_and_returns_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkpoint_file = checkpoint_path(tmp_path / "heypiggy_run_run-1")
    ctx = StepContext(run_id="run-1", state=AgentState.EXECUTE_TASK_LOOP)
    monkeypatch.setattr("worker.checkpoints._close_heypiggy_tabs", lambda: None)

    rc = fail_safe(ctx, checkpoint_file, "max steps reached")

    assert rc == 0
    saved = load_checkpoint(checkpoint_file)
    assert saved is not None
    assert saved.state == AgentState.FAIL_SAFE


def test_escalate_writes_dump_and_returns_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkpoint_file = checkpoint_path(tmp_path / "heypiggy_run_run-1")
    artifact_dir = tmp_path / "heypiggy_run_run-1"
    artifact_dir.mkdir(parents=True)
    ctx = StepContext(run_id="run-1", state=AgentState.EXECUTE_TASK_LOOP)
    monkeypatch.setattr("worker.checkpoints._send_telegram_alert", lambda *args, **kwargs: None)

    rc = escalate(ctx, checkpoint_file, artifact_dir, "retries exhausted")

    assert rc == 1
    saved = load_checkpoint(checkpoint_file)
    assert saved is not None
    assert saved.state == AgentState.ESCALATE
    assert (artifact_dir / "escalation_dump.json").exists()


def test_list_recent_archives_reads_summary_data(tmp_path: Path) -> None:
    archive_root = tmp_path / "runs" / "archive" / "run-1"
    archive_root.mkdir(parents=True)
    (archive_root / "run_summary.json").write_text(
        json.dumps({"earnings": 4.25, "duration_seconds": 120.0}),
        encoding="utf-8",
    )

    runs = list_recent_archives(tmp_path)

    assert len(runs) == 1
    assert runs[0].run_id == "run-1"
    assert runs[0].earnings == 4.25
    assert runs[0].duration_seconds == 120.0
