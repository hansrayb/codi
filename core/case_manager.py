"""In-memory case lifecycle management for multi-prompt work context."""

from __future__ import annotations

import asyncio
import itertools
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from config import Settings
from models.case import Case

CASE_CLOSE_WORDS = {
    "close case",
    "done",
    "selesai",
    "selesai case",
    "tutup case",
}


@dataclass(frozen=True)
class CaseStats:
    """Status snapshot for the active case."""

    active_case_id: str | None
    active_case_title: str | None
    active_case_repo: str | None
    user_case_count: int


class CaseManager:
    """Manage user-owned cases that span multiple prompts and sessions."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cases: dict[str, Case] = {}
        self._user_cases: dict[int, set[str]] = {}
        self._active_case_by_user: dict[int, str] = {}
        self._counter = itertools.count(1)
        self._lock = asyncio.Lock()

    @staticmethod
    def classify_control_message(text: str) -> str | None:
        normalized = " ".join(text.strip().lower().split())
        if normalized in CASE_CLOSE_WORDS:
            return "close_case"
        return None

    async def get_active_case(self, user_id: int) -> Case | None:
        async with self._lock:
            self._prune_expired_locked()
            case_id = self._active_case_by_user.get(user_id)
            if not case_id:
                return None
            return self._cases.get(case_id)

    async def open_or_reuse_case(
        self,
        user_id: int,
        repo_root: Path,
        *,
        prompt: str,
        role: str,
    ) -> tuple[Case, bool]:
        async with self._lock:
            self._prune_expired_locked()
            resolved_repo = str(repo_root.resolve())
            active_case_id = self._active_case_by_user.get(user_id)
            if active_case_id:
                active_case = self._cases.get(active_case_id)
                if active_case is not None and active_case.repo_root == resolved_repo:
                    active_case.last_activity_at = _utcnow()
                    active_case.last_role = role
                    active_case.message_count += 1
                    if not active_case.title:
                        active_case.title = _build_case_title(prompt)
                    return active_case, False

            user_case_ids = self._user_cases.setdefault(user_id, set())
            reusable_candidates = sorted(
                (
                    self._cases[case_id]
                    for case_id in user_case_ids
                    if case_id in self._cases
                    and self._cases[case_id].status == "open"
                    and self._cases[case_id].repo_root == resolved_repo
                ),
                key=lambda case: case.last_activity_at,
                reverse=True,
            )
            if reusable_candidates:
                case = reusable_candidates[0]
                self._active_case_by_user[user_id] = case.case_id
                case.last_activity_at = _utcnow()
                case.last_role = role
                case.message_count += 1
                if not case.title:
                    case.title = _build_case_title(prompt)
                return case, False

            case_id = f"c-{next(self._counter):02d}"
            case = Case(
                case_id=case_id,
                owner_user_id=user_id,
                repo_root=resolved_repo,
                title=_build_case_title(prompt),
                last_role=role,
                message_count=1,
            )
            self._cases[case_id] = case
            user_case_ids.add(case_id)
            self._active_case_by_user[user_id] = case_id
            return case, True

    async def update_case(
        self,
        case_id: str,
        *,
        role: str,
        prompt: str,
    ) -> None:
        async with self._lock:
            case = self._cases.get(case_id)
            if case is None or case.status != "open":
                return
            case.last_activity_at = _utcnow()
            case.last_role = role
            case.summary = _merge_case_summary(case.summary, prompt)

    async def close_active_case(self, user_id: int) -> Case | None:
        async with self._lock:
            self._prune_expired_locked()
            case_id = self._active_case_by_user.pop(user_id, None)
            if case_id is None:
                return None
            case = self._cases.pop(case_id, None)
            if case is None:
                return None
            case.status = "closed"
            case.last_activity_at = _utcnow()
            owner_cases = self._user_cases.get(user_id)
            if owner_cases is not None:
                owner_cases.discard(case_id)
                if not owner_cases:
                    self._user_cases.pop(user_id, None)
            return case

    async def get_stats(self, user_id: int) -> CaseStats:
        async with self._lock:
            self._prune_expired_locked()
            active_case_id = self._active_case_by_user.get(user_id)
            active_case = self._cases.get(active_case_id) if active_case_id else None
            return CaseStats(
                active_case_id=active_case.case_id if active_case else None,
                active_case_title=active_case.title if active_case else None,
                active_case_repo=active_case.repo_root if active_case else None,
                user_case_count=len(self._user_cases.get(user_id, set())),
            )

    async def reset_user(self, user_id: int) -> int:
        async with self._lock:
            case_ids = list(self._user_cases.get(user_id, set()))
            for case_id in case_ids:
                case = self._cases.pop(case_id, None)
                if case is not None:
                    case.status = "closed"
            self._user_cases.pop(user_id, None)
            self._active_case_by_user.pop(user_id, None)
            return len(case_ids)

    def _prune_expired_locked(self) -> None:
        now = _utcnow()
        expired_case_ids = [
            case_id
            for case_id, case in self._cases.items()
            if case.status == "open"
            and case.is_expired(self._settings.session_idle_ttl_seconds, now)
        ]
        for case_id in expired_case_ids:
            case = self._cases.pop(case_id, None)
            if case is None:
                continue
            case.status = "closed"
            owner_cases = self._user_cases.get(case.owner_user_id)
            if owner_cases is not None:
                owner_cases.discard(case_id)
                if not owner_cases:
                    self._user_cases.pop(case.owner_user_id, None)
            if self._active_case_by_user.get(case.owner_user_id) == case_id:
                self._active_case_by_user.pop(case.owner_user_id, None)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _build_case_title(prompt: str) -> str:
    snippet = " ".join(prompt.strip().split())
    if len(snippet) <= 72:
        return snippet
    return f"{snippet[:69].rstrip()}..."


def _merge_case_summary(existing: str, prompt: str) -> str:
    snippet = " ".join(prompt.strip().split())
    if len(snippet) > 180:
        snippet = f"{snippet[:177]}..."
    if not existing.strip():
        return f"- {snippet}"
    lines = [line for line in existing.splitlines() if line.strip()]
    lines.append(f"- {snippet}")
    return "\n".join(lines[-8:])
