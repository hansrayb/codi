"""Session domain models for orchestrated Codi execution."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


class SessionLock:
    """Minimal async-compatible lock that is safe to construct without an event loop."""

    def __init__(self) -> None:
        self._locked = False

    async def acquire(self) -> bool:
        while self._locked:
            await asyncio.sleep(0.05)
        self._locked = True
        return True

    def release(self) -> None:
        if not self._locked:
            raise RuntimeError("Lock is not acquired.")
        self._locked = False

    def locked(self) -> bool:
        return self._locked


@dataclass
class Session:
    """A logical execution session that behaves like a focused terminal."""

    session_id: str
    owner_user_id: int
    role: str
    cwd: str
    case_id: str | None = None
    claude_session_id: str | None = None
    status: str = "idle"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    summary: str = ""
    message_count: int = 0
    queued_tasks: int = 0
    lock: SessionLock = field(default_factory=SessionLock, repr=False)

    def is_expired(self, ttl_seconds: int, now: datetime | None = None) -> bool:
        """Return whether the session has been idle beyond its TTL."""

        current = now or datetime.now(timezone.utc)
        return current - self.last_activity_at > timedelta(seconds=ttl_seconds)
