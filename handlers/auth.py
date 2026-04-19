"""Authorization, RBAC, and lightweight rate limiting for Telegram handlers."""

from __future__ import annotations

import functools
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from telegram import Update
from telegram.ext import ContextTypes

HandlerFunc = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]

ROLE_RANK: dict[str, int] = {"viewer": 0, "business": 1, "operator": 2, "admin": 3}


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


def get_user_role(user_id: int, settings) -> str:
    """Return the RBAC role for a user: 'admin', 'operator', 'viewer', or 'none'."""

    if user_id in settings.admin_user_ids:
        return "admin"
    if user_id in settings.viewer_user_ids:
        return "viewer"
    if user_id in settings.business_user_ids:
        return "business"
    if user_id in settings.allowed_user_ids:
        return "operator"
    return "none"


def require_role(min_role: str = "viewer") -> Callable[[HandlerFunc], HandlerFunc]:
    """Return a decorator that enforces a minimum RBAC role before the handler runs."""

    def decorator(handler_func: HandlerFunc) -> HandlerFunc:
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

            role = get_user_role(user.id, settings)
            if ROLE_RANK.get(role, -1) < ROLE_RANK.get(min_role, 0):
                logger.warning(
                    "user_id=%s | role=%s | required=%s | action=forbidden",
                    user.id,
                    role,
                    min_role,
                )
                await message.reply_text(
                    f"Akses ditolak. Perintah ini butuh role *{min_role}* atau lebih tinggi.",
                    parse_mode="Markdown",
                )
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

    return decorator


# Backward-compat alias: any whitelisted user (viewer and above) can pass
require_auth = require_role("viewer")
