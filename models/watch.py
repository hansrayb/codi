"""Models for repository watch state and snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class RepoWatchSnapshot:
    """A compact snapshot of the current git state for a watched repo."""

    branch: str
    head: str
    status_fingerprint: str
    status_count: int
    status_preview: tuple[str, ...]

    @property
    def is_dirty(self) -> bool:
        """Return whether the working tree has tracked or untracked changes."""

        return self.status_count > 0


@dataclass
class RepoWatch:
    """A user-owned watch registration for a git repository."""

    watch_id: str
    owner_user_id: int
    chat_id: int
    repo_root: str
    repo_label: str
    snapshot: RepoWatchSnapshot
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class RepoWatchStats:
    """Status snapshot for watched repositories."""

    watched_repos: int
    watched_labels: tuple[str, ...]
