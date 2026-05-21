"""Dashboard chat session store: maps a dashboard session_id to a Claude CLI
thread id (claude_session_id) so each browser conversation keeps its own
isolated history via `claude --resume`.

Thread-safe: the HTTP API server runs handlers on ThreadingHTTPServer worker
threads while the orchestrator mutates state on the asyncio loop thread. All
access goes through a single lock.

SQLite persistence (opt-in): pass ``db_path`` to survive process restarts.
Without it, behaviour is identical to the original in-memory-only store.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

DEFAULT_TTL_SECONDS = 30 * 60
DEFAULT_MAX_ENTRIES = 500

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id        TEXT PRIMARY KEY,
    claude_session_id TEXT,
    title             TEXT,
    last_access       REAL NOT NULL,
    created_at        REAL NOT NULL
);
"""


@dataclass
class _Entry:
    claude_session_id: str | None
    last_access: float          # monotonic — in-memory only
    title: str | None = None
    created_at: float = field(default_factory=time.time)  # wall-clock


class CodiSessionStore:
    """Lock-guarded dashboard session_id -> claude_session_id mapping.

    If ``db_path`` is given the mapping is persisted to SQLite so it survives
    process restarts. The in-memory dict is always the primary source; SQLite
    is a write-through backing store loaded once at startup.
    """

    def __init__(
        self,
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        db_path: Optional[Path] = None,
    ) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._lock = threading.Lock()
        self._entries: dict[str, _Entry] = {}
        self._db: Optional[sqlite3.Connection] = None

        if db_path is not None:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(str(db_path), check_same_thread=False)
            self._db.executescript(_SCHEMA)
            self._db.commit()
            self._load_from_db()

    # ── public API (same signature as before) ─────────────────────────────────

    def get_claude_session_id(self, session_id: str) -> str | None:
        """Return the Claude thread id for a dashboard session, or None.

        Sweeps expired entries and refreshes last_access on a hit.
        """
        now = time.monotonic()
        with self._lock:
            self._sweep_locked(now)
            entry = self._entries.get(session_id)
            if entry is None:
                return None
            entry.last_access = now
            self._db_touch(session_id)
            return entry.claude_session_id

    def set_claude_session_id(self, session_id: str, claude_session_id: str | None) -> None:
        """Persist the Claude thread id learned from a completed CLI run."""
        now = time.monotonic()
        with self._lock:
            self._sweep_locked(now)
            existing = self._entries.get(session_id)
            self._entries[session_id] = _Entry(
                claude_session_id=claude_session_id,
                last_access=now,
                title=existing.title if existing else None,
                created_at=existing.created_at if existing else time.time(),
            )
            self._evict_if_needed_locked()
            self._db_upsert(session_id, self._entries[session_id])

    def delete(self, session_id: str) -> None:
        """Drop a session mapping (logout / explicit new conversation)."""
        with self._lock:
            self._entries.pop(session_id, None)
            if self._db is not None:
                self._db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                self._db.commit()

    def list_sessions(self) -> list[dict]:
        """Return all active sessions sorted by last_access descending."""
        now = time.monotonic()
        with self._lock:
            self._sweep_locked(now)
            return [
                {
                    "session_id": sid,
                    "claude_session_id": e.claude_session_id,
                    "title": e.title,
                    "created_at": e.created_at,
                    "last_access_age": now - e.last_access,
                }
                for sid, e in sorted(
                    self._entries.items(),
                    key=lambda kv: kv[1].last_access,
                    reverse=True,
                )
            ]

    # ── private helpers ───────────────────────────────────────────────────────

    def _load_from_db(self) -> None:
        """Restore non-expired entries from DB into the in-memory dict."""
        if self._db is None:
            return
        mono_now = time.monotonic()
        wall_now = time.time()
        wall_cutoff = (wall_now - self._ttl) if self._ttl > 0 else 0.0
        rows = self._db.execute(
            "SELECT session_id, claude_session_id, title, last_access, created_at "
            "FROM sessions WHERE last_access >= ?",
            (wall_cutoff,),
        ).fetchall()
        for session_id, claude_session_id, title, last_access_wall, created_at in rows:
            age = max(wall_now - last_access_wall, 0.0)
            self._entries[session_id] = _Entry(
                claude_session_id=claude_session_id,
                last_access=mono_now - age,
                title=title,
                created_at=created_at or wall_now,
            )

    def _sweep_locked(self, now: float) -> None:
        if self._ttl <= 0:
            return
        cutoff = now - self._ttl
        expired = [sid for sid, e in self._entries.items() if e.last_access < cutoff]
        for sid in expired:
            self._entries.pop(sid)
        if expired and self._db is not None:
            wall_cutoff = time.time() - self._ttl
            self._db.execute("DELETE FROM sessions WHERE last_access < ?", (wall_cutoff,))
            self._db.commit()

    def _evict_if_needed_locked(self) -> None:
        if len(self._entries) <= self._max:
            return
        ordered = sorted(self._entries.items(), key=lambda kv: kv[1].last_access)
        overflow = len(self._entries) - self._max
        evicted = [sid for sid, _ in ordered[:overflow]]
        for sid in evicted:
            self._entries.pop(sid)
        if self._db is not None:
            for sid in evicted:
                self._db.execute("DELETE FROM sessions WHERE session_id = ?", (sid,))
            self._db.commit()

    def _db_upsert(self, session_id: str, entry: _Entry) -> None:
        if self._db is None:
            return
        wall_now = time.time()
        self._db.execute(
            "INSERT OR REPLACE INTO sessions "
            "(session_id, claude_session_id, title, last_access, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                session_id,
                entry.claude_session_id,
                entry.title,
                wall_now,
                entry.created_at,
            ),
        )
        self._db.commit()

    def _db_touch(self, session_id: str) -> None:
        if self._db is None:
            return
        self._db.execute(
            "UPDATE sessions SET last_access = ? WHERE session_id = ?",
            (time.time(), session_id),
        )
        self._db.commit()
