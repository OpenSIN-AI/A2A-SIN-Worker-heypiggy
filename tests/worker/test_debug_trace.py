"""Tests for worker.debug_trace."""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Iterator

import pytest


@pytest.fixture
def enabled_trace(monkeypatch, tmp_path) -> Iterator[object]:
    """Reload the module with the feature flag on and a tmp dump dir."""
    monkeypatch.setenv("WORKER_DEBUG_TRACE", "1")
    monkeypatch.setenv("WORKER_DEBUG_DUMP_DIR", str(tmp_path))
    # Force a fresh import so TRACE_ENABLED reflects the env.
    if "worker.debug_trace" in sys.modules:
        del sys.modules["worker.debug_trace"]
    module = importlib.import_module("worker.debug_trace")
    # Reset the singleton so tests don't leak state into each other.
    module._singleton = None  # type: ignore[attr-defined]
    yield module
    module._singleton = None  # type: ignore[attr-defined]


@pytest.fixture
def disabled_trace(monkeypatch) -> Iterator[object]:
    monkeypatch.delenv("WORKER_DEBUG_TRACE", raising=False)
    if "worker.debug_trace" in sys.modules:
        del sys.modules["worker.debug_trace"]
    module = importlib.import_module("worker.debug_trace")
    module._singleton = None  # type: ignore[attr-defined]
    yield module
    module._singleton = None  # type: ignore[attr-defined]


class TestFeatureFlag:
    def test_default_disabled_when_env_missing(self, disabled_trace) -> None:
        assert disabled_trace.TRACE_ENABLED is False

    def test_record_is_noop_when_disabled(self, disabled_trace) -> None:
        buf = disabled_trace.get_trace()
        buf.record(method="click", params={"ref": "x"}, result={"ok": True}, duration_ms=10, ok=True)
        assert buf.size() == 0

    def test_dump_returns_none_when_disabled(self, disabled_trace) -> None:
        path = disabled_trace.dump_on_vision_cap(attempts=7)
        assert path is None

    def test_flag_accepts_truthy_values(self, monkeypatch) -> None:
        for val in ("1", "true", "TRUE", "yes", "on"):
            monkeypatch.setenv("WORKER_DEBUG_TRACE", val)
            if "worker.debug_trace" in sys.modules:
                del sys.modules["worker.debug_trace"]
            mod = importlib.import_module("worker.debug_trace")
            assert mod.TRACE_ENABLED is True, val

    def test_flag_rejects_other_values(self, monkeypatch) -> None:
        for val in ("0", "false", "no", "off", "", "maybe"):
            monkeypatch.setenv("WORKER_DEBUG_TRACE", val)
            if "worker.debug_trace" in sys.modules:
                del sys.modules["worker.debug_trace"]
            mod = importlib.import_module("worker.debug_trace")
            assert mod.TRACE_ENABLED is False, val


class TestRecording:
    def test_records_basic_call(self, enabled_trace) -> None:
        buf = enabled_trace.get_trace()
        buf.record(
            method="click_element",
            params={"ref": "btn-1"},
            result={"ok": True, "url": "https://example.com"},
            duration_ms=42.3,
            ok=True,
        )
        assert buf.size() == 1
        recs = list(buf.recent(5))
        assert recs[0].data["method"] == "click_element"
        assert recs[0].data["ok"] is True
        assert recs[0].data["duration_ms"] == 42.3

    def test_ring_buffer_caps_at_maxlen(self, enabled_trace) -> None:
        buf = enabled_trace.TraceBuffer(max_records=5)
        for i in range(12):
            buf.record(
                method=f"m{i}",
                params={},
                result=None,
                duration_ms=1,
                ok=True,
            )
        assert buf.size() == 5
        # Oldest evicted, most recent kept.
        methods = [r.data["method"] for r in buf.recent(10)]
        assert methods == ["m7", "m8", "m9", "m10", "m11"]
        assert buf.dropped() == 7

    def test_recent_returns_oldest_first(self, enabled_trace) -> None:
        buf = enabled_trace.get_trace()
        for i in range(5):
            buf.record(method=f"m{i}", params={}, result=None, duration_ms=1, ok=True)
        recs = list(buf.recent(3))
        assert [r.data["method"] for r in recs] == ["m2", "m3", "m4"]

    def test_clear_resets_state(self, enabled_trace) -> None:
        buf = enabled_trace.get_trace()
        buf.record(method="a", params={}, result=None, duration_ms=1, ok=True)
        buf.clear()
        assert buf.size() == 0
        assert buf.dropped() == 0


class TestRedaction:
    def test_strips_cookie_keys(self, enabled_trace) -> None:
        buf = enabled_trace.get_trace()
        buf.record(
            method="set_cookies",
            params={"cookies": [{"name": "sid", "value": "deadbeef"}], "tabId": 3},
            result=None,
            duration_ms=1,
            ok=True,
        )
        rec = list(buf.recent(1))[0]
        assert rec.data["params"]["cookies"] == "<redacted>"
        # non-sensitive fields preserved
        assert rec.data["params"]["tabId"] == 3

    def test_strips_bearer_and_password(self, enabled_trace) -> None:
        buf = enabled_trace.get_trace()
        buf.record(
            method="http.fetch",
            params={
                "headers": {"Authorization": "Bearer xyz"},
                "body": {"password": "hunter2", "email": "a@b.c"},
            },
            result=None,
            duration_ms=1,
            ok=True,
        )
        rec = list(buf.recent(1))[0]
        assert rec.data["params"]["headers"]["Authorization"] == "<redacted>"
        assert rec.data["params"]["body"]["password"] == "<redacted>"
        assert rec.data["params"]["body"]["email"] == "a@b.c"

    def test_trims_large_blob_fields(self, enabled_trace) -> None:
        big = "x" * 5000
        buf = enabled_trace.get_trace()
        buf.record(
            method="execute_javascript",
            params={"script": big},
            result=None,
            duration_ms=1,
            ok=True,
        )
        rec = list(buf.recent(1))[0]
        assert rec.data["params"]["script"].startswith("x" * 50)
        assert "..." in rec.data["params"]["script"]
        assert len(rec.data["params"]["script"]) < 500

    def test_trims_long_strings(self, enabled_trace) -> None:
        long = "a" * 1000
        buf = enabled_trace.get_trace()
        buf.record(
            method="something",
            params={"note": long},
            result=None,
            duration_ms=1,
            ok=True,
        )
        rec = list(buf.recent(1))[0]
        assert len(rec.data["params"]["note"]) < 500

    def test_bounded_recursion(self, enabled_trace) -> None:
        nested: dict = {"a": {}}
        cur = nested["a"]
        for _ in range(30):
            cur["x"] = {}
            cur = cur["x"]
        buf = enabled_trace.get_trace()
        buf.record(method="m", params=nested, result=None, duration_ms=1, ok=True)
        # Should not hang or raise; depth limit kicks in.
        assert buf.size() == 1


class TestResultPreview:
    def test_dict_result_keeps_keys_and_known_fields(self, enabled_trace) -> None:
        buf = enabled_trace.get_trace()
        buf.record(
            method="click",
            params={},
            result={"ok": False, "error": "stale ref", "url": "https://x/y", "extra": 123},
            duration_ms=1,
            ok=False,
        )
        rec = list(buf.recent(1))[0]
        preview = rec.data["result_preview"]
        assert preview["ok"] is False
        assert preview["error"] == "stale ref"
        assert preview["url"] == "https://x/y"
        assert "extra" in preview["keys"]

    def test_list_result_reports_length(self, enabled_trace) -> None:
        buf = enabled_trace.get_trace()
        buf.record(method="m", params={}, result=[1, 2, 3], duration_ms=1, ok=True)
        rec = list(buf.recent(1))[0]
        assert rec.data["result_preview"] == {"type": "list", "len": 3}


class TestDump:
    def test_dump_writes_json_file(self, enabled_trace, tmp_path) -> None:
        buf = enabled_trace.get_trace()
        for i in range(3):
            buf.record(method=f"m{i}", params={"i": i}, result=None, duration_ms=1, ok=True)
        path = buf.dump(reason="unit_test", directory=str(tmp_path))
        assert path is not None
        file = Path(path)
        assert file.exists()
        payload = json.loads(file.read_text())
        assert payload["reason"] == "unit_test"
        assert payload["total_in_buffer"] == 3
        assert len(payload["records"]) == 3

    def test_dump_reason_slugs_special_chars(self, enabled_trace, tmp_path) -> None:
        buf = enabled_trace.get_trace()
        buf.record(method="m", params={}, result=None, duration_ms=1, ok=True)
        path = buf.dump(reason="vision/retry cap: 7", directory=str(tmp_path))
        assert path is not None
        # Filename must not contain slash or colon
        name = Path(path).name
        assert "/" not in name
        assert ":" not in name
        assert " " not in name

    def test_dump_on_vision_cap_uses_singleton(self, enabled_trace, tmp_path) -> None:
        enabled_trace.get_trace().record(
            method="m", params={}, result=None, duration_ms=1, ok=True
        )
        path = enabled_trace.dump_on_vision_cap(attempts=7, last_error="RETRY vision")
        assert path is not None
        assert "vision_retry_cap_attempts_7" in Path(path).name

    def test_dump_never_raises(self, enabled_trace, monkeypatch) -> None:
        buf = enabled_trace.get_trace()
        buf.record(method="m", params={}, result=None, duration_ms=1, ok=True)
        # Point at an unwritable path. Must return None, never raise.
        result = buf.dump(reason="r", directory="/proc/no-such-thing-definitely/subdir")
        assert result is None


class TestSingleton:
    def test_get_trace_returns_same_instance(self, enabled_trace) -> None:
        a = enabled_trace.get_trace()
        b = enabled_trace.get_trace()
        assert a is b
