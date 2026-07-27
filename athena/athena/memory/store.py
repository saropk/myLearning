"""SQLite store — phase 1 slice.

Phase 1 needs exactly one table: `settings` (bearer token, valve level, last_session_end).
The message/embedding/fact/provenance/audit tables land in phases 4 and 5; `SCHEMA_VERSION`
is here so those migrations have something to step from.

Security invariant 8: the database directory is chmod 700.
"""

from __future__ import annotations

import secrets
import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class Store:
    """Thin synchronous wrapper around the settings table.

    Phase 1 writes are tiny and rare (token once, valve/state on change), so a plain
    synchronous connection is honest here. If a later phase makes writes hot, move to a
    thread executor rather than sprinkling threads now.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Security invariant 8 — enforced on every open, not just first run.
        self.db_path.parent.chmod(0o700)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self.set("schema_version", str(SCHEMA_VERSION))

    # --- settings -----------------------------------------------------------------
    def get(self, key: str, default: str | None = None) -> str | None:
        row = self._conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default

    def set(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self._conn.commit()

    # --- derived helpers ----------------------------------------------------------
    def ensure_token(self) -> str:
        """Random per-install bearer token, generated on first run and persisted."""
        token = self.get("api_token")
        if not token:
            token = secrets.token_urlsafe(32)
            self.set("api_token", token)
        return token

    def valve_level(self, default: int) -> int:
        raw = self.get("valve_level")
        if raw is None:
            self.set("valve_level", str(default))
            return default
        try:
            level = int(raw)
        except ValueError:
            return default
        return level if 0 <= level <= 3 else default

    def set_valve_level(self, level: int) -> None:
        if not 0 <= level <= 3:
            raise ValueError("valve level must be 0-3")
        self.set("valve_level", str(level))

    def close(self) -> None:
        self._conn.close()
