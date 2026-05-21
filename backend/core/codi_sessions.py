"""Dashboard chat session store: maps a dashboard session_id to a Claude CLI
thread id (claude_session_id) so each browser conversation keeps its own
isolated history via `claude --resume`.

Thread-safe: the HTTP API server runs handlers on ThreadingHTTPServer worker
threads while the orchestrator mutates state on the asyncio loop thread. All
access goes through a single lock.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

# Idle TTL: drop a session->thread mapping after this many seconds without use.
DEFAULT_TTL_SECONDS = 30 * 60
# Hard cap on tracked sessions; evicts least-recently-used beyond this.
DEFAULT_MAX_ENTRIES = 500


@dataclass
class _Entry:
    claude_session_id: str | None
    last_access: float


class CodiSessionStore:
    """Lock-guarded dashboard session_id -> claude_session_id mapping."""

    def __init__(
        self,
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._lock = threading.Lock()
        self._entries: dict[str, _Entry] = {}

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
            return entry.claude_session_id

    def set_claude_session_id(self, session_id: str, claude_session_id: str | None) -> None:
        """Persist the Claude thread id learned from a completed CLI run."""
        now = time.monotonic()
        with self._lock:
            self._sweep_locked(now)
            self._entries[session_id] = _Entry(
                claude_session_id=claude_session_id,
                last_access=now,
            )
            self._evict_if_needed_locked()

    def delete(self, session_id: str) -> None:
        """Drop a session mapping (logout / explicit new conversation)."""
        with self._lock:
            self._entries.pop(session_id, None)

    def _sweep_locked(self, now: float) -> None:
        if self._ttl <= 0:
            return
        cutoff = now - self._ttl
        expired = [sid for sid, e in self._entries.items() if e.last_access < cutoff]
        for sid in expired:
            self._entries.pop(sid, None)

    def _evict_if_needed_locked(self) -> None:
        if len(self._entries) <= self._max:
            return
        # Evict least-recently-used until back under the cap.
        ordered = sorted(self._entries.items(), key=lambda kv: kv[1].last_access)
        overflow = len(self._entries) - self._max
        for sid, _ in ordered[:overflow]:
            self._entries.pop(sid, None)
