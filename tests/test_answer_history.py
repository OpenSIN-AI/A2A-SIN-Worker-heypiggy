from __future__ import annotations

from pathlib import Path
import time

from answer_history import (
    clear_history,
    get_failed_options,
    get_prior_answer,
    load_history,
    record_failure,
    record_success,
    save_history,
)


def test_record_success_and_failure_roundtrip(tmp_path: Path) -> None:
    history_path = tmp_path / "answer_history.json"

    record_success("Wie alt sind Sie?", "25-34", path=history_path)
    record_failure("Wie alt sind Sie?", "18-24", path=history_path)

    prior = get_prior_answer("Wie alt sind Sie?", path=history_path)
    assert prior is not None
    assert prior["answer"] == "25-34"
    assert "18-24" in prior["failed_options"]

    failed = get_failed_options("Wie alt sind Sie?", path=history_path)
    assert failed == ["18-24"]


def test_load_and_save_history_roundtrip(tmp_path: Path) -> None:
    history_path = tmp_path / "answer_history.json"
    payload = {
        "wie alt sind sie?": {
            "successful_answer": "25-34",
            "failed_options": ["18-24"],
            "timestamp": time.time(),
            "panel": "HeyPiggy",
            "question_type": "single_choice",
        }
    }

    save_history(payload, path=history_path)
    loaded = load_history(path=history_path)

    assert loaded == payload


def test_clear_history_removes_file(tmp_path: Path) -> None:
    history_path = tmp_path / "answer_history.json"
    save_history(
        {
            "foo": {
                "successful_answer": "bar",
                "failed_options": [],
                "timestamp": time.time(),
            }
        },
        path=history_path,
    )

    assert history_path.exists()
    clear_history(path=history_path)
    assert not history_path.exists()
