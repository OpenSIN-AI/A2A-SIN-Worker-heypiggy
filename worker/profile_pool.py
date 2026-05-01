"""ProfilePool — SQLite-backed account registry for multi-account survey automation."""
from __future__ import annotations
import json, sqlite3, os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(os.environ.get("ACCOUNTS_DB", os.path.expanduser("~/.heypiggy/accounts.db")))


class ProfilePool:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS accounts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                label       TEXT NOT NULL,
                email       TEXT NOT NULL,
                password    TEXT NOT NULL,
                profile_dir TEXT,
                proxy       TEXT DEFAULT '',
                is_active   INTEGER DEFAULT 1,
                eur_earned  REAL DEFAULT 0.0,
                surveys_done INTEGER DEFAULT 0,
                last_run    TEXT,
                created_at  TEXT DEFAULT (datetime('now')),
                updated_at  TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS profile_health (
                account_id  INTEGER PRIMARY KEY,
                status      TEXT DEFAULT 'unknown',
                last_health TEXT,
                ban_detected INTEGER DEFAULT 0,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            );
        """)
        self._conn.commit()

    def create(self, label: str, email: str, password: str, proxy: str = "") -> int:
        profile_dir = str(Path.home() / ".heypiggy" / f"profiles/{label}")
        cur = self._conn.execute(
            "INSERT INTO accounts (label, email, password, profile_dir, proxy) VALUES (?, ?, ?, ?, ?)",
            (label, email, password, profile_dir, proxy),
        )
        self._conn.commit()
        return cur.lastrowid

    def list_active(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM accounts WHERE is_active = 1 ORDER BY surveys_done ASC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get(self, account_id: int) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
        return dict(row) if row else None

    def record_survey(self, account_id: int, eur: float):
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE accounts SET eur_earned = eur_earned + ?, surveys_done = surveys_done + 1, last_run = ?, updated_at = ? WHERE id = ?",
            (eur, now, now, account_id),
        )
        self._conn.commit()

    def set_status(self, account_id: int, status: str):
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT OR REPLACE INTO profile_health (account_id, status, last_health) VALUES (?, ?, ?)",
            (account_id, status, now),
        )
        self._conn.commit()

    def mark_ban(self, account_id: int):
        self._conn.execute(
            "INSERT OR REPLACE INTO profile_health (account_id, status, last_health, ban_detected) VALUES (?, 'banned', datetime('now'), 1)",
            (account_id,),
        )
        self._conn.execute("UPDATE accounts SET is_active = 0 WHERE id = ?", (account_id,))
        self._conn.commit()

    def deactivate(self, account_id: int):
        self._conn.execute("UPDATE accounts SET is_active = 0, updated_at = datetime('now') WHERE id = ?", (account_id,))
        self._conn.commit()

    def summary(self) -> dict[str, Any]:
        active = self._conn.execute(
            "SELECT COUNT(*) as cnt, SUM(eur_earned) as total, SUM(surveys_done) as surveys FROM accounts WHERE is_active = 1"
        ).fetchone()
        banned = self._conn.execute("SELECT COUNT(*) as cnt FROM profile_health WHERE ban_detected = 1").fetchone()
        all_earned = self._conn.execute("SELECT SUM(eur_earned) as total FROM accounts").fetchone()
        return {
            "active_accounts": active["cnt"] or 0,
            "total_earned": round(active["total"] or 0.0, 2),
            "total_all_time": round(all_earned["total"] or 0.0, 2),
            "total_surveys": active["surveys"] or 0,
            "banned_accounts": banned["cnt"] or 0,
        }

    def close(self):
        self._conn.close()
