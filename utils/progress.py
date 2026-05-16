"""Helpers for streaming Claude progress into Telegram-friendly updates."""

from __future__ import annotations

import time
from telegram import Message
from telegram.error import BadRequest

ROLE_PROGRESS_TEXT = {
    "builder": ("sedang mengerjakan task ini", "sudah selesai mengerjakan task ini"),
    "reviewer": ("sedang meninjau task ini", "sudah selesai meninjau task ini"),
    "debugger": ("sedang menelusuri masalah ini", "sudah selesai menelusuri masalah ini"),
    "ops": ("sedang mengecek kondisi sistem", "sudah selesai mengecek kondisi sistem"),
    "general": ("sedang memproses permintaanmu", "sudah selesai memproses permintaanmu"),
    "chat": ("sedang ngobrol di mode chat", "sudah selesai ngobrol di mode chat"),
}


class TelegramProgressReporter:
    """Edit a Telegram message in-place with recent progress updates."""

    def __init__(
        self,
        *,
        message: Message,
        assistant_name: str,
        role: str,
        session_id: str,
        max_lines: int = 5,
        min_edit_interval: float = 2.0,
    ) -> None:
        self._message = message
        self._assistant_name = assistant_name
        self._role = role
        self._session_id = session_id
        self._max_lines = max_lines
        self._min_edit_interval = min_edit_interval
        self._lines: list[str] = []
        self._last_text: str = ""
        self._last_edit_at: float = 0.0

    async def push(self, update: str) -> None:
        """Add a progress line and edit the Telegram message when appropriate."""

        for line in update.splitlines():
            clean = line.strip()
            if not clean:
                continue
            if self._lines and self._lines[-1] == clean:
                continue
            self._lines.append(clean)
        self._lines = self._lines[-self._max_lines :]

        now = time.monotonic()
        if now - self._last_edit_at >= self._min_edit_interval:
            await self.flush()

    async def flush(self, *, completed: bool = False) -> None:
        """Force a Telegram edit with the latest progress lines."""

        text = self._render_text(completed=completed)
        if text == self._last_text:
            return

        try:
            await self._message.edit_text(text)
        except BadRequest as exc:
            if "Message is not modified" not in str(exc):
                raise
        self._last_text = text
        self._last_edit_at = time.monotonic()

    def _render_text(self, *, completed: bool) -> str:
        active_text, completed_text = ROLE_PROGRESS_TEXT.get(
            self._role,
            ("sedang memproses task ini", "sudah selesai memproses task ini"),
        )
        header = f"{self._assistant_name} {active_text}."
        if completed:
            header = f"{self._assistant_name} {completed_text}."
        if not self._lines:
            return header

        body = "\n".join(f"- {line}" for line in self._lines)
        text = f"{header}\n\n{body}"
        return text[:4000]
