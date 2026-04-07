"""Session domain models for orchestrated Codex execution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass(slots=True)
class Session:
    """A logical execution session that behaves like a focused terminal."""

    session_id: str
    owner_user_id: int
    role: str
    cwd: str
    case_id: str | None = None
    codex_thread_id: str | None = None
    status: str = "idle"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    summary: str = ""
    message_count: int = 0
    queued_tasks: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    def is_expired(self, ttl_seconds: int, now: datetime | None = None) -> bool:
        """Return whether the session has been idle beyond its TTL."""

        current = now or datetime.now(timezone.utc)
        return current - self.last_activity_at > timedelta(seconds=ttl_seconds)
