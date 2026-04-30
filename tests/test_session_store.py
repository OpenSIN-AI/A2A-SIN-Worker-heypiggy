import json
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

import session_store


@pytest.mark.asyncio
async def test_restore_session_injects_cookie_url(tmp_path: Path):
    cache = tmp_path / "session_cache.json"
    cache.write_text(
        json.dumps(
            {
                "saved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "domains": {
                    "heypiggy.com": {
                        "cookies": [
                            {
                                "name": "session",
                                "value": "abc123",
                                "domain": ".heypiggy.com",
                                "path": "/",
                                "secure": True,
                                "hostOnly": True,
                            }
                        ]
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    execute_bridge = AsyncMock(return_value={"ok": True})

    result = await session_store.restore_session(
        execute_bridge,
        {"tabId": 7},
        "https://www.heypiggy.com/login",
        cache_path=cache,
    )

    assert result["restored"] is True
    assert result["cookies_set"] == 1
    execute_bridge.assert_awaited()

    method, params = execute_bridge.await_args_list[0].args
    assert method == "set_cookie"
    assert params["url"] == "https://www.heypiggy.com/"
    assert "hostOnly" not in params


@pytest.mark.asyncio
async def test_dump_and_restore_include_answer_history(tmp_path: Path, monkeypatch):
    cache = tmp_path / "session_cache.json"
    answer_history_payload = {
        "wie alt sind sie?": {
            "successful_answer": "25-34",
            "failed_options": ["18-24"],
            "timestamp": 123.0,
            "panel": "HeyPiggy",
            "question_type": "single_choice",
        }
    }

    monkeypatch.setattr(session_store, "_answer_load_history", lambda: answer_history_payload)
    execute_bridge = AsyncMock(return_value=[])

    dump_result = await session_store.dump_session(
        execute_bridge,
        {"tabId": 7},
        cache_path=cache,
    )

    assert dump_result["path"] == str(cache)
    written = json.loads(cache.read_text(encoding="utf-8"))
    assert written["answer_history"] == answer_history_payload

    saved = {}

    def fake_save(data):
        saved.update(data)

    monkeypatch.setattr(session_store, "_answer_save_history", fake_save)

    restore_cache = tmp_path / "restore_cache.json"
    restore_cache.write_text(
        json.dumps(
            {
                "saved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "domains": {"heypiggy.com": {}},
                "answer_history": answer_history_payload,
            }
        ),
        encoding="utf-8",
    )

    restore_result = await session_store.restore_session(
        AsyncMock(return_value={"ok": True}),
        {"tabId": 7},
        "https://www.heypiggy.com/login",
        cache_path=restore_cache,
    )

    assert restore_result["restored"] is True
    assert saved == answer_history_payload
