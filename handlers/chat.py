"""Command handler for lightweight backend chat mode."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from handlers.auth import require_role
from handlers.messages import _handle_post_send_action, _send_payload
from utils.progress import TelegramProgressReporter


@require_role("operator")
async def chat_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Discuss ideas with the active AI backend without starting a work task."""

    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return

    text = " ".join(context.args or []).strip()
    orchestrator = context.application.bot_data["orchestrator"]
    if not text:
        payload = await orchestrator.run_chat(user.id, "")
        await _send_payload(message, payload)
        return

    assistant_name = context.application.bot_data["settings"].assistant_name
    progress_message = await message.reply_text(f"{assistant_name} masuk mode chat.")
    reporter = TelegramProgressReporter(
        message=progress_message,
        assistant_name=assistant_name,
        role="chat",
        session_id=f"chat-{user.id}",
    )
    payload = await orchestrator.run_chat(user.id, text, on_progress=reporter.push)
    await reporter.flush(completed=True)
    await _send_payload(message, payload)
    chat_id = update.effective_chat.id if update.effective_chat is not None else None
    await _handle_post_send_action(context, payload, chat_id=chat_id)
