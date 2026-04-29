"""Persistent memory store for Codi — user context, session history, repo knowledge."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_memory (
    user_id     INTEGER PRIMARY KEY,
    notes       TEXT    NOT NULL DEFAULT '',
    updated_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS session_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    repo_path   TEXT    NOT NULL DEFAULT '',
    role        TEXT    NOT NULL DEFAULT 'general',
    summary     TEXT    NOT NULL,
    created_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sh_user ON session_history(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS repo_knowledge (
    repo_path   TEXT PRIMARY KEY,
    summary     TEXT NOT NULL DEFAULT '',
    conventions TEXT NOT NULL DEFAULT '',
    updated_at  TEXT NOT NULL
);
"""

_MAX_HISTORY_ROWS = 20   # rows kept per user in DB
_INJECT_HISTORY  = 8    # rows injected into prompt


class MemoryStore:
    """Thread-safe SQLite-backed memory for Codi."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._path = db_path
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ------------------------------------------------------------------
    # User memory
    # ------------------------------------------------------------------

    def get_user_notes(self, user_id: int) -> str:
        row = self._conn.execute(
            "SELECT notes FROM user_memory WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row["notes"] if row else ""

    def append_user_note(self, user_id: int, note: str) -> None:
        note = note.strip()
        if not note:
            return
        now = _now()
        existing = self.get_user_notes(user_id)
        lines = [l for l in existing.splitlines() if l.strip()]
        lines.append(f"- {note}")
        merged = "\n".join(lines[-20:])  # keep last 20 notes
        self._conn.execute(
            """
            INSERT INTO user_memory(user_id, notes, updated_at) VALUES(?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET notes = excluded.notes, updated_at = excluded.updated_at
            """,
            (user_id, merged, now),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Session history
    # ------------------------------------------------------------------

    def save_session_summary(
        self,
        user_id: int,
        repo_path: str,
        role: str,
        summary: str,
    ) -> None:
        summary = summary.strip()
        if not summary:
            return
        now = _now()
        self._conn.execute(
            "INSERT INTO session_history(user_id, repo_path, role, summary, created_at) VALUES(?,?,?,?,?)",
            (user_id, repo_path, role, summary, now),
        )
        # Trim to keep only the most recent rows per user
        self._conn.execute(
            """
            DELETE FROM session_history
            WHERE user_id = ? AND id NOT IN (
                SELECT id FROM session_history WHERE user_id = ?
                ORDER BY created_at DESC LIMIT ?
            )
            """,
            (user_id, user_id, _MAX_HISTORY_ROWS),
        )
        self._conn.commit()

    def get_recent_history(self, user_id: int, repo_path: str = "") -> str:
        """Return formatted history injected into prompts."""
        if repo_path:
            rows = self._conn.execute(
                """
                SELECT role, summary, created_at FROM session_history
                WHERE user_id = ? AND repo_path = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (user_id, repo_path, _INJECT_HISTORY),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT role, summary, created_at FROM session_history
                WHERE user_id = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (user_id, _INJECT_HISTORY),
            ).fetchall()
        if not rows:
            return ""
        lines = []
        for r in reversed(rows):
            date = r["created_at"][:10]
            lines.append(f"[{date}][{r['role']}] {r['summary']}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Repo knowledge
    # ------------------------------------------------------------------

    def get_repo_knowledge(self, repo_path: str) -> tuple[str, str]:
        """Return (summary, conventions) for a repo."""
        row = self._conn.execute(
            "SELECT summary, conventions FROM repo_knowledge WHERE repo_path = ?", (repo_path,)
        ).fetchone()
        if not row:
            return "", ""
        return row["summary"], row["conventions"]

    def save_repo_knowledge(self, repo_path: str, summary: str, conventions: str) -> None:
        now = _now()
        self._conn.execute(
            """
            INSERT INTO repo_knowledge(repo_path, summary, conventions, updated_at) VALUES(?,?,?,?)
            ON CONFLICT(repo_path) DO UPDATE SET
                summary = excluded.summary,
                conventions = excluded.conventions,
                updated_at = excluded.updated_at
            """,
            (repo_path, summary.strip(), conventions.strip(), now),
        )
        self._conn.commit()

    def invalidate_repo(self, repo_path: str) -> None:
        self._conn.execute("DELETE FROM repo_knowledge WHERE repo_path = ?", (repo_path,))
        self._conn.commit()

    # ------------------------------------------------------------------
    # Export / import (for migration)
    # ------------------------------------------------------------------

    def export_all(self) -> dict:
        data: dict = {"version": 1, "exported_at": _now(), "tables": {}}
        for table in ("user_memory", "session_history", "repo_knowledge"):
            rows = self._conn.execute(f"SELECT * FROM {table}").fetchall()
            data["tables"][table] = [dict(r) for r in rows]
        return data

    def import_all(self, data: dict, *, overwrite: bool = False) -> dict[str, int]:
        tables = data.get("tables", {})
        counts: dict[str, int] = {}
        for table, rows in tables.items():
            if not rows:
                counts[table] = 0
                continue
            if overwrite:
                self._conn.execute(f"DELETE FROM {table}")
            cols = ", ".join(rows[0].keys())
            placeholders = ", ".join("?" for _ in rows[0])
            conflict = "OR IGNORE" if not overwrite else "OR REPLACE"
            stmt = f"INSERT {conflict} INTO {table}({cols}) VALUES({placeholders})"
            self._conn.executemany(stmt, [list(r.values()) for r in rows])
            counts[table] = len(rows)
        self._conn.commit()
        return counts

    def close(self) -> None:
        self._conn.close()


def build_memory_context(
    store: MemoryStore,
    user_id: int,
    repo_path: str = "",
) -> str:
    """Build the memory block injected into prompts."""
    parts: list[str] = []

    notes = store.get_user_notes(user_id)
    if notes:
        parts.append(f"User context:\n{notes}")

    history = store.get_recent_history(user_id, repo_path)
    if history:
        label = f"Recent work on {repo_path}:" if repo_path else "Recent work:"
        parts.append(f"{label}\n{history}")

    if repo_path:
        repo_summary, conventions = store.get_repo_knowledge(repo_path)
        if repo_summary:
            parts.append(f"Repo knowledge ({repo_path}):\n{repo_summary}")
        if conventions:
            parts.append(f"Repo conventions:\n{conventions}")

    return "\n\n".join(parts)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
