"""Persistent Telegram chat targets for background notifications."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class AlertTarget:
    """A chat that should receive background alerts for a specific user."""

    user_id: int
    chat_id: int
    registered_at: datetime
    last_seen_at: datetime


class AlertTargetRegistry:
    """Persist and return Telegram chats that are eligible for alerts."""

    def __init__(self, path: Path) -> None:
        self._path = path.expanduser().resolve()
        self._lock = asyncio.Lock()
        self._targets: dict[int, AlertTarget] = self._load()

    async def register_chat(self, *, user_id: int, chat_id: int) -> None:
        """Record the latest chat used by an authorized user."""

        now = datetime.now(timezone.utc)
        async with self._lock:
            existing = self._targets.get(user_id)
            registered_at = existing.registered_at if existing is not None else now
            self._targets[user_id] = AlertTarget(
                user_id=user_id,
                chat_id=chat_id,
                registered_at=registered_at,
                last_seen_at=now,
            )
            await asyncio.to_thread(self._persist)

    async def list_targets(self) -> tuple[AlertTarget, ...]:
        """Return alert targets ordered by user ID."""

        async with self._lock:
            return tuple(
                self._targets[user_id]
                for user_id in sorted(self._targets)
            )

    async def get_stats(self) -> dict[str, int]:
        """Return lightweight registry stats for status reporting."""

        async with self._lock:
            return {"registered_targets": len(self._targets)}

    def _load(self) -> dict[int, AlertTarget]:
        if not self._path.exists():
            return {}
        try:
            payload = json.loads(self._path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError, ValueError):
            return {}
        targets: dict[int, AlertTarget] = {}
        items = payload if isinstance(payload, list) else payload.get('targets', [])
        for item in items:
            try:
                user_id = int(item['user_id'])
                chat_id = int(item['chat_id'])
                registered_at = _parse_datetime(item['registered_at'])
                last_seen_at = _parse_datetime(item['last_seen_at'])
            except (KeyError, TypeError, ValueError):
                continue
            targets[user_id] = AlertTarget(
                user_id=user_id,
                chat_id=chat_id,
                registered_at=registered_at,
                last_seen_at=last_seen_at,
            )
        return targets

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {
                'user_id': target.user_id,
                'chat_id': target.chat_id,
                'registered_at': target.registered_at.isoformat(),
                'last_seen_at': target.last_seen_at.isoformat(),
            }
            for target in sorted(self._targets.values(), key=lambda item: item.user_id)
        ]
        self._path.write_text(
            json.dumps({'targets': payload}, indent=2),
            encoding='utf-8',
        )


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
