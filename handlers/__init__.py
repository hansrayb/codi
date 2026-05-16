"""Telegram handler registration for the orchestrated Codex bot."""

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from handlers.callbacks import handle_callback_query
from handlers.messages import handle_text_message
from handlers.status import status_command
from handlers.system import (
    help_command,
    ping_command,
    reset_command,
    start_command,
)


def register_handlers(application: Application) -> None:
    """Register Telegram handlers on the given application."""

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ping", ping_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)
    )
    application.add_handler(CallbackQueryHandler(handle_callback_query))
