"""Tests für ProfilePool — Multi-Account Account Registry."""
from __future__ import annotations
import pytest
from pathlib import Path
from worker.profile_pool import ProfilePool


@pytest.fixture
def pool(tmp_path: Path) -> ProfilePool:
    return ProfilePool(db_path=tmp_path / "test_accounts.db")


class TestProfilePool:
    def test_create_account(self, pool: ProfilePool):
        aid = pool.create("test-user", "test@example.com", "secret123")
        assert aid == 1

    def test_get_account(self, pool: ProfilePool):
        aid = pool.create("test-user", "test@example.com", "secret123")
        account = pool.get(aid)
        assert account is not None
        assert account["label"] == "test-user"
        assert account["email"] == "test@example.com"
        assert account["is_active"] == 1

    def test_get_nonexistent(self, pool: ProfilePool):
        assert pool.get(999) is None

    def test_list_active_returns_active_only(self, pool: ProfilePool):
        a1 = pool.create("active-user", "a@x.com", "pw")
        a2 = pool.create("banned-user", "b@x.com", "pw")
        pool.deactivate(a2)
        active = pool.list_active()
        assert len(active) == 1
        assert active[0]["id"] == a1

    def test_record_survey(self, pool: ProfilePool):
        aid = pool.create("test-user", "test@example.com", "secret123")
        pool.record_survey(aid, 1.50)
        pool.record_survey(aid, 0.75)
        account = pool.get(aid)
        assert account["eur_earned"] == 2.25
        assert account["surveys_done"] == 2
        assert account["last_run"] is not None

    def test_ban_account(self, pool: ProfilePool):
        aid = pool.create("test-user", "test@example.com", "secret123")
        pool.mark_ban(aid)
        account = pool.get(aid)
        assert account["is_active"] == 0
        health = pool._conn.execute(
            "SELECT * FROM profile_health WHERE account_id = ?", (aid,)
        ).fetchone()
        assert health["status"] == "banned"
        assert health["ban_detected"] == 1

    def test_summary(self, pool: ProfilePool):
        a1 = pool.create("user-1", "a@x.com", "pw")
        a2 = pool.create("user-2", "b@x.com", "pw")
        pool.record_survey(a1, 2.00)
        pool.record_survey(a2, 1.50)
        pool.mark_ban(a2)
        summary = pool.summary()
        assert summary["active_accounts"] == 1
        assert summary["total_earned"] == 2.00
        assert summary["total_all_time"] == 3.50
        assert summary["total_surveys"] == 1
        assert summary["banned_accounts"] == 1

    def test_proxy_field(self, pool: ProfilePool):
        aid = pool.create("proxied-user", "p@x.com", "pw", proxy="socks5://127.0.0.1:9050")
        account = pool.get(aid)
        assert account["proxy"] == "socks5://127.0.0.1:9050"

    def test_deactivate(self, pool: ProfilePool):
        aid = pool.create("test-user", "test@example.com", "secret123")
        pool.deactivate(aid)
        account = pool.get(aid)
        assert account["is_active"] == 0

    def test_created_at_set(self, pool: ProfilePool):
        aid = pool.create("test-user", "test@example.com", "secret123")
        account = pool.get(aid)
        assert account["created_at"] is not None
        assert len(account["created_at"]) > 5
