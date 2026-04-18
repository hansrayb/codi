"""In-memory session lifecycle management for logical Codex terminals."""

from __future__ import annotations

import asyncio
import itertools
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from config import Settings
from models.session import Session


class SessionError(RuntimeError):
    """Base class for session-related issues."""


class SessionLimitError(SessionError):
    """Raised when the configured session limits are exhausted."""


class QueueFullError(SessionError):
    """Raised when a session queue is already full."""


class SessionInvalidatedError(SessionError):
    """Raised when a session disappears while a task is waiting for it."""


@dataclass
class SessionLease:
    """Reservation returned when a task acquires a session."""

    manager: "SessionManager"
    session: Session
    created_session: bool
    queued_before_acquire: bool
    released: bool = False

    async def release(self, summary_update: str = "") -> None:
        """Release the session after work has completed."""

        if self.released:
            return
        await self.manager._release_lease(self, summary_update)
        self.released = True


@dataclass(frozen=True)
class SessionStats:
    """Status snapshot for `/status` and diagnostics."""

    active_sessions: int
    busy_sessions: int
    queued_tasks: int
    max_active_sessions: int
    active_role: str | None
    active_cwd: str | None
    user_session_count: int


class SessionManager:
    """Manage user-owned logical sessions with small in-memory state."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._sessions: dict[str, Session] = {}
        self._user_sessions: dict[int, set[str]] = defaultdict(set)
        self._active_session_by_user: dict[int, str] = {}
        self._counter = itertools.count(1)
        self._lock = asyncio.Lock()

    async def get_active_session(self, user_id: int) -> Session | None:
        """Return the currently active session for the user, if any."""

        async with self._lock:
            self._prune_expired_locked()
            session_id = self._active_session_by_user.get(user_id)
            if not session_id:
                return None
            return self._sessions.get(session_id)

    async def acquire_session(
        self,
        user_id: int,
        role: str,
        cwd: Path,
        *,
        prefer_reuse: bool,
        case_id: str | None = None,
    ) -> SessionLease:
        """Acquire a session for a task, optionally reusing an existing one."""

        queued_before_acquire = False
        async with self._lock:
            self._prune_expired_locked()
            session, created_session = self._select_session_locked(
                user_id=user_id,
                role=role,
                cwd=cwd,
                prefer_reuse=prefer_reuse,
                case_id=case_id,
            )
            if session.lock.locked():
                if session.queued_tasks >= self._settings.max_queue_per_session:
                    raise QueueFullError("Session queue is full.")
                session.queued_tasks += 1
                session.status = "queued"
                queued_before_acquire = True
            self._active_session_by_user[user_id] = session.session_id

        await session.lock.acquire()

        async with self._lock:
            if session.session_id not in self._sessions or session.status == "stopped":
                session.lock.release()
                raise SessionInvalidatedError("Session was reset while waiting.")
            if queued_before_acquire and session.queued_tasks > 0:
                session.queued_tasks -= 1
            session.status = "busy"
            session.last_activity_at = _utcnow()
            session.message_count += 1
            self._active_session_by_user[user_id] = session.session_id

        return SessionLease(
            manager=self,
            session=session,
            created_session=created_session,
            queued_before_acquire=queued_before_acquire,
        )

    async def reset_user(self, user_id: int) -> int:
        """Remove all session metadata for a user and clear active mapping."""

        async with self._lock:
            session_ids = list(self._user_sessions.get(user_id, set()))
            for session_id in session_ids:
                session = self._sessions.pop(session_id, None)
                if session is not None:
                    session.status = "stopped"
            self._user_sessions.pop(user_id, None)
            self._active_session_by_user.pop(user_id, None)
            return len(session_ids)

    async def close_case_sessions(self, case_id: str) -> int:
        """Stop all sessions that belong to a closed case."""

        async with self._lock:
            session_ids = [
                session_id
                for session_id, session in self._sessions.items()
                if session.case_id == case_id
            ]
            for session_id in session_ids:
                session = self._sessions.pop(session_id, None)
                if session is None:
                    continue
                session.status = "stopped"
                owner_sessions = self._user_sessions.get(session.owner_user_id)
                if owner_sessions is not None:
                    owner_sessions.discard(session_id)
                    if not owner_sessions:
                        self._user_sessions.pop(session.owner_user_id, None)
                if self._active_session_by_user.get(session.owner_user_id) == session_id:
                    self._active_session_by_user.pop(session.owner_user_id, None)
            return len(session_ids)

    async def get_stats(self, user_id: int) -> SessionStats:
        """Return a lightweight status snapshot."""

        async with self._lock:
            self._prune_expired_locked()
            active_role = None
            active_session_id = self._active_session_by_user.get(user_id)
            if active_session_id and active_session_id in self._sessions:
                active_role = self._sessions[active_session_id].role
            return SessionStats(
                active_sessions=len(self._sessions),
                busy_sessions=sum(1 for session in self._sessions.values() if session.lock.locked()),
                queued_tasks=sum(session.queued_tasks for session in self._sessions.values()),
                max_active_sessions=self._settings.max_active_sessions,
                active_role=active_role,
                active_cwd=(
                    self._sessions[active_session_id].cwd
                    if active_session_id and active_session_id in self._sessions
                    else None
                ),
                user_session_count=len(self._user_sessions.get(user_id, set())),
            )

    def _select_session_locked(
        self,
        *,
        user_id: int,
        role: str,
        cwd: Path,
        prefer_reuse: bool,
        case_id: str | None,
    ) -> tuple[Session, bool]:
        active_session_id = self._active_session_by_user.get(user_id)
        if prefer_reuse and active_session_id:
            active_session = self._sessions.get(active_session_id)
            if (
                active_session is not None
                and active_session.case_id == case_id
                and active_session.role == role
                and Path(active_session.cwd).resolve() == cwd.resolve()
            ):
                return active_session, False

        reusable_candidates = sorted(
            (
                self._sessions[session_id]
                for session_id in self._user_sessions.get(user_id, set())
                if session_id in self._sessions
                and self._sessions[session_id].case_id == case_id
                and self._sessions[session_id].role == role
                and Path(self._sessions[session_id].cwd).resolve() == cwd.resolve()
                and self._sessions[session_id].status != "stopped"
            ),
            key=lambda session: session.last_activity_at,
            reverse=True,
        )
        for candidate in reusable_candidates:
            if not candidate.lock.locked():
                return candidate, False

        if len(self._sessions) >= self._settings.max_active_sessions:
            raise SessionLimitError("All sessions are currently in use.")
        if len(self._user_sessions[user_id]) >= self._settings.max_sessions_per_user:
            raise SessionLimitError("The user has reached the session limit.")

        session_id = f"s-{next(self._counter):02d}"
        session = Session(
            session_id=session_id,
            owner_user_id=user_id,
            case_id=case_id,
            role=role,
            cwd=str(cwd),
        )
        self._sessions[session_id] = session
        self._user_sessions[user_id].add(session_id)
        return session, True

    async def _release_lease(self, lease: SessionLease, summary_update: str) -> None:
        async with self._lock:
            session = self._sessions.get(lease.session.session_id)
            if session is not None:
                session.last_activity_at = _utcnow()
                session.status = "queued" if session.queued_tasks > 0 else "idle"
                if summary_update.strip():
                    session.summary = summary_update.strip()
        lease.session.lock.release()

    def _prune_expired_locked(self) -> None:
        now = _utcnow()
        expired_session_ids = [
            session_id
            for session_id, session in self._sessions.items()
            if not session.lock.locked()
            and session.status != "stopped"
            and session.is_expired(self._settings.session_idle_ttl_seconds, now)
        ]
        for session_id in expired_session_ids:
            session = self._sessions.pop(session_id, None)
            if session is None:
                continue
            session.status = "stopped"
            owner_sessions = self._user_sessions.get(session.owner_user_id)
            if owner_sessions is not None:
                owner_sessions.discard(session_id)
                if not owner_sessions:
                    self._user_sessions.pop(session.owner_user_id, None)
            if self._active_session_by_user.get(session.owner_user_id) == session_id:
                self._active_session_by_user.pop(session.owner_user_id, None)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
