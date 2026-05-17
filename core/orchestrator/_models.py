"""Shared lightweight dataclasses used across orchestrator sub-modules."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field


@dataclass
class ChatSessionState:
    """Per-user lightweight backend chat state, isolated from work sessions."""

    claude_session_id: str | None = None
    summary: str = ""
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


ProgressCallback = Callable[[str], Awaitable[None]]
