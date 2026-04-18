"""Case domain models for multi-prompt orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class Case:
    """A user-facing work case that can span multiple prompts and roles."""

    case_id: str
    owner_user_id: int
    repo_root: str
    status: str = "open"
    title: str = ""
    summary: str = ""
    last_role: str | None = None
    message_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def is_expired(self, ttl_seconds: int, now: datetime | None = None) -> bool:
        """Return whether the case has been idle beyond its TTL."""

        current = now or datetime.now(timezone.utc)
        return current - self.last_activity_at > timedelta(seconds=ttl_seconds)
