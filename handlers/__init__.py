"""Telegram handler registration for the orchestrated Codex bot."""

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from handlers.callbacks import handle_callback_query
from handlers.chat import chat_command
from handlers.cekrepo import cekrepo_command
from handlers.messages import handle_text_message
from handlers.pilihproject import pilihproject_command
from handlers.screenshot import screenshot_command
from handlers.status import status_command
from handlers.system import (
    devices_command,
    done_command,
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
    application.add_handler(CommandHandler("chat", chat_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("screenshot", screenshot_command))
    application.add_handler(CommandHandler("cekrepo", cekrepo_command))
    application.add_handler(CommandHandler("pilih_project", pilihproject_command))
    application.add_handler(CommandHandler("devices", devices_command))
    application.add_handler(CommandHandler("done", done_command))
    application.add_handler(CommandHandler("reset", reset_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)
    )
    application.add_handler(CallbackQueryHandler(handle_callback_query))
