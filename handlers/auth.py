"""Authorization and lightweight rate limiting for Telegram handlers."""

from __future__ import annotations

import functools
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from telegram import Update
from telegram.ext import ContextTypes

HandlerFunc = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]


class InMemoryRateLimiter:
    """Track simple per-user request rates in memory."""

    def __init__(self, max_requests_per_minute: int) -> None:
        self._max_requests = max_requests_per_minute
        self._buckets: dict[int, deque[float]] = defaultdict(deque)

    def allow(self, user_id: int) -> bool:
        """Return whether the user can make another request right now."""

        now = time.monotonic()
        window_start = now - 60
        bucket = self._buckets[user_id]
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= self._max_requests:
            return False
        bucket.append(now)
        return True


def require_auth(handler_func: HandlerFunc) -> HandlerFunc:
    """Ensure the caller is whitelisted before executing a handler."""

    @functools.wraps(handler_func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        user = update.effective_user
        if message is None or user is None:
            return

        settings = context.application.bot_data["settings"]
        logger = context.application.bot_data["logger"]
        rate_limiter = context.application.bot_data.setdefault(
            "rate_limiter",
            InMemoryRateLimiter(settings.max_requests_per_minute),
        )

        if user.id not in settings.allowed_user_ids:
            logger.warning("user_id=%s | action=unauthorized", user.id)
            await message.reply_text("Akses ditolak.")
            return

        if not rate_limiter.allow(user.id):
            logger.warning("user_id=%s | action=rate_limited", user.id)
            await message.reply_text("Terlalu banyak request. Coba lagi sebentar.")
            return

        alert_target_registry = context.application.bot_data.get("alert_target_registry")
        chat = update.effective_chat
        if alert_target_registry is not None and chat is not None:
            await alert_target_registry.register_chat(user_id=user.id, chat_id=chat.id)

        await handler_func(update, context)

    return wrapper  # type: ignore[return-value]
