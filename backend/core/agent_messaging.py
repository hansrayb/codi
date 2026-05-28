"""Agent-to-agent messaging store (SQLite, lock-guarded).

Dipakai untuk peer messaging antar Claude Code agent di mesin berbeda
(laptop, server, dst). Codi backend host store; tiap agent akses via
HTTP `/api/agent/*` atau MCP tool.

Schema:
- `agent_messages`: id, sender, recipient, content, thread_id, status,
  created_at, read_at.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender TEXT NOT NULL,
    recipient TEXT NOT NULL,
    content TEXT NOT NULL,
    thread_id TEXT,
    status TEXT NOT NULL DEFAULT 'unread',
    created_at TEXT NOT NULL,
    read_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_msg_recipient ON agent_messages(recipient, status);
CREATE INDEX IF NOT EXISTS idx_msg_thread ON agent_messages(thread_id);
"""


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


class AgentMessagingStore:
    """SQLite-backed inbox/outbox per agent."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._lock = threading.RLock()

    @classmethod
    def connect(cls, path: Path) -> "AgentMessagingStore":
        path = Path(path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.executescript(_SCHEMA)
        conn.commit()
        return cls(conn)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ── Send ────────────────────────────────────────────────
    def send(
        self,
        *,
        sender: str,
        recipient: str,
        content: str,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        if not sender or not recipient:
            raise ValueError("sender + recipient wajib.")
        if not content.strip():
            raise ValueError("content tak boleh kosong.")
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO agent_messages(sender, recipient, content, thread_id, status, created_at) "
                "VALUES (?,?,?,?,'unread',?)",
                (sender, recipient, content, thread_id, _now_iso()),
            )
            self._conn.commit()
            msg_id = cur.lastrowid
        return {
            "id": msg_id,
            "sender": sender,
            "recipient": recipient,
            "content": content,
            "thread_id": thread_id,
            "status": "unread",
        }

    # ── Inbox (read) ────────────────────────────────────────
    def inbox(
        self,
        recipient: str,
        *,
        mark_read: bool = True,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM agent_messages "
                "WHERE recipient = ? AND status = 'unread' "
                "ORDER BY id ASC LIMIT ?",
                (recipient, limit),
            ).fetchall()
            messages = [self._row_to_dict(r) for r in rows]
            if mark_read and messages:
                ids = [m["id"] for m in messages]
                self._conn.executemany(
                    "UPDATE agent_messages SET status='read', read_at=? WHERE id=?",
                    [(_now_iso(), i) for i in ids],
                )
                self._conn.commit()
        return messages

    def history(
        self,
        *,
        thread_id: str | None = None,
        peer_a: str | None = None,
        peer_b: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Riwayat thread atau pairwise (peer_a ↔ peer_b)."""
        with self._lock:
            if thread_id:
                rows = self._conn.execute(
                    "SELECT * FROM agent_messages WHERE thread_id = ? "
                    "ORDER BY id ASC LIMIT ?",
                    (thread_id, limit),
                ).fetchall()
            elif peer_a and peer_b:
                rows = self._conn.execute(
                    "SELECT * FROM agent_messages "
                    "WHERE (sender=? AND recipient=?) OR (sender=? AND recipient=?) "
                    "ORDER BY id ASC LIMIT ?",
                    (peer_a, peer_b, peer_b, peer_a, limit),
                ).fetchall()
            else:
                rows = []
        return [self._row_to_dict(r) for r in rows]

    # ── Wait for reply (poll-based) ─────────────────────────
    def wait_reply(
        self,
        *,
        recipient: str,
        thread_id: str | None = None,
        since_id: int = 0,
        timeout_seconds: int = 60,
        poll_interval: float = 1.0,
    ) -> dict[str, Any] | None:
        """Blocking poll: tunggu pesan baru untuk `recipient` (opsional di
        thread_id), > since_id. Return msg dict atau None kalau timeout."""
        deadline = time.monotonic() + timeout_seconds
        while True:
            with self._lock:
                if thread_id:
                    row = self._conn.execute(
                        "SELECT * FROM agent_messages "
                        "WHERE recipient=? AND thread_id=? AND id>? "
                        "ORDER BY id ASC LIMIT 1",
                        (recipient, thread_id, since_id),
                    ).fetchone()
                else:
                    row = self._conn.execute(
                        "SELECT * FROM agent_messages "
                        "WHERE recipient=? AND id>? "
                        "ORDER BY id ASC LIMIT 1",
                        (recipient, since_id),
                    ).fetchone()
                if row:
                    self._conn.execute(
                        "UPDATE agent_messages SET status='read', read_at=? WHERE id=?",
                        (_now_iso(), row["id"]),
                    )
                    self._conn.commit()
                    return self._row_to_dict(row)
            if time.monotonic() >= deadline:
                return None
            time.sleep(poll_interval)

    # ── Threads / agents listing ────────────────────────────
    def list_threads(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT thread_id, MAX(id) AS last_id, COUNT(*) AS n, "
                "MAX(created_at) AS last_at "
                "FROM agent_messages WHERE thread_id IS NOT NULL "
                "GROUP BY thread_id ORDER BY last_id DESC"
            ).fetchall()
        return [
            {
                "thread_id": r["thread_id"],
                "messages": r["n"],
                "last_id": r["last_id"],
                "last_at": r["last_at"],
            }
            for r in rows
        ]

    def list_agents(self) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT sender AS a FROM agent_messages "
                "UNION SELECT DISTINCT recipient FROM agent_messages "
                "ORDER BY a"
            ).fetchall()
        return [r["a"] for r in rows]

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "sender": row["sender"],
            "recipient": row["recipient"],
            "content": row["content"],
            "thread_id": row["thread_id"],
            "status": row["status"],
            "created_at": row["created_at"],
            "read_at": row["read_at"],
        }
