"""Chat conversation/message persistence store (SQLite, lock-guarded).

Dipakai oleh mobile API `/api/v1/chat/*` agar percakapan tersimpan
lintas restart. Scope storage = per `account_id` dari `AuthContext`
(bootstrap = "bootstrap").

Schema:
- `chat_conversations(id, account_id, title, created_at,
   last_message_at, message_count)`
- `chat_messages(id, conversation_id, role, text, created_at)`
"""

from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_conversations (
    id              TEXT PRIMARY KEY,
    account_id      TEXT NOT NULL,
    title           TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL,
    last_message_at TEXT NOT NULL,
    message_count   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_chat_conv_acc
    ON chat_conversations(account_id, last_message_at DESC);

CREATE TABLE IF NOT EXISTS chat_messages (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role            TEXT NOT NULL,
    text            TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chat_msg_conv
    ON chat_messages(conversation_id, created_at);
"""


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _new_conv_id() -> str:
    return f"conv_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"


def _new_msg_id() -> str:
    return f"msg_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"


def _title_from(text: str, *, max_len: int = 60) -> str:
    """Derive a conversation title from the first user message."""
    cleaned = " ".join((text or "").split())
    return cleaned[:max_len].rstrip() if cleaned else "Percakapan baru"


def _preview(text: str, *, max_len: int = 80) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


class ChatHistoryStore:
    """SQLite-backed conversations + messages, scoped per account_id."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._lock = threading.RLock()

    @classmethod
    def connect(cls, path: Path) -> "ChatHistoryStore":
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

    # ── Conversations ────────────────────────────────────────────────
    def _conversation_belongs(self, conversation_id: str, account_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM chat_conversations WHERE id = ? AND account_id = ?",
            (conversation_id, account_id),
        ).fetchone()
        return row is not None

    def ensure_conversation(
        self,
        *,
        account_id: str,
        conversation_id: str | None,
        seed_title_text: str,
    ) -> str:
        """Return a valid conversation_id for ``account_id``.

        If ``conversation_id`` is given AND owned by this account, reuse it;
        otherwise create a new one with title derived from ``seed_title_text``.
        """
        if not account_id:
            raise ValueError("account_id wajib.")
        with self._lock:
            if conversation_id and self._conversation_belongs(
                conversation_id, account_id
            ):
                return conversation_id
            new_id = _new_conv_id()
            now = _now_iso()
            self._conn.execute(
                "INSERT INTO chat_conversations"
                "(id, account_id, title, created_at, last_message_at, message_count) "
                "VALUES (?,?,?,?,?,0)",
                (new_id, account_id, _title_from(seed_title_text), now, now),
            )
            self._conn.commit()
            return new_id

    def append_message(
        self,
        *,
        conversation_id: str,
        role: str,
        text: str,
    ) -> dict[str, Any]:
        """Append a turn; bump conversation last_message_at + message_count."""
        if role not in ("user", "assistant"):
            raise ValueError(f"role tidak valid: {role!r}")
        msg_id = _new_msg_id()
        now = _now_iso()
        with self._lock:
            self._conn.execute(
                "INSERT INTO chat_messages"
                "(id, conversation_id, role, text, created_at) "
                "VALUES (?,?,?,?,?)",
                (msg_id, conversation_id, role, text, now),
            )
            self._conn.execute(
                "UPDATE chat_conversations "
                "SET last_message_at = ?, message_count = message_count + 1 "
                "WHERE id = ?",
                (now, conversation_id),
            )
            self._conn.commit()
        return {
            "id": msg_id,
            "conversation_id": conversation_id,
            "role": role,
            "text": text,
            "created_at": now,
        }

    def list_conversations(
        self, *, account_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """List conversations owned by ``account_id`` sorted by last_message_at desc."""
        with self._lock:
            convs = self._conn.execute(
                "SELECT id, title, created_at, last_message_at, message_count "
                "FROM chat_conversations WHERE account_id = ? "
                "ORDER BY last_message_at DESC LIMIT ?",
                (account_id, max(1, int(limit))),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for c in convs:
            with self._lock:
                last = self._conn.execute(
                    "SELECT text FROM chat_messages WHERE conversation_id = ? "
                    "ORDER BY created_at DESC LIMIT 1",
                    (c["id"],),
                ).fetchone()
            preview = _preview(last["text"]) if last else ""
            out.append({
                "id": c["id"],
                "title": c["title"] or "Percakapan baru",
                "last_message_at": c["last_message_at"],
                "message_count": int(c["message_count"] or 0),
                "preview": preview,
            })
        return out

    def get_messages(
        self, *, conversation_id: str, account_id: str
    ) -> list[dict[str, Any]] | None:
        """Return ordered messages, or None if conversation isn't owned by account."""
        with self._lock:
            if not self._conversation_belongs(conversation_id, account_id):
                return None
            rows = self._conn.execute(
                "SELECT id, role, text, created_at FROM chat_messages "
                "WHERE conversation_id = ? ORDER BY created_at ASC, id ASC",
                (conversation_id,),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "role": r["role"],
                "content": {"type": "text", "text": r["text"]},
                "timestamp": r["created_at"],
            }
            for r in rows
        ]
