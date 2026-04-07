"""Result payload models for Telegram output handling."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MessagePayload:
    """A Telegram-bound response payload."""

    text: str
    parse_mode: str | None = None
    attachment_filename: str | None = None
    attachment_bytes: bytes | None = None
    post_send_action: str | None = None

    @property
    def has_attachment(self) -> bool:
        """Return whether the payload should be sent as a document."""

        return self.attachment_filename is not None and self.attachment_bytes is not None
