"""Inline keyboard callback query handlers."""

from __future__ import annotations

from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from core.orchestrator import OrchestratorUserError
from handlers.auth import require_auth
from handlers.messages import _send_payload


@require_auth
async def handle_callback_query(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Route inline button presses to the appropriate orchestrator action."""

    query = update.callback_query
    user = update.effective_user
    if query is None or user is None:
        return

    await query.answer()

    data = query.data or ""
    orchestrator = context.application.bot_data["orchestrator"]
    assistant_name = context.application.bot_data["settings"].assistant_name

    if data.startswith("cekrepo:select:"):
        repo_path = data[len("cekrepo:select:"):]
        try:
            payload = await orchestrator.select_repo(user.id, repo_path)
        except Exception as exc:
            await query.edit_message_text(
                f"<b>{assistant_name}</b>\n\nGagal set repo: {exc}",
                parse_mode="HTML",
            )
            return
        await query.edit_message_text(
            payload.text,
            parse_mode=payload.parse_mode,
        )
        return

    if data == "safety:approve":
        synthetic_text = "lanjutkan aksi"
    elif data == "safety:reject":
        synthetic_text = "batal aksi"
    elif data == "edit:approve":
        synthetic_text = "lanjutkan"
    elif data == "edit:reject":
        synthetic_text = "batal"
    else:
        await query.answer("Aksi tidak dikenal.")
        return

    try:
        payload = await orchestrator.try_handle_control_message(user.id, synthetic_text)
    except OrchestratorUserError as exc:
        await query.edit_message_text(
            f"<b>{assistant_name}</b>\n\n{exc.user_message}",
            parse_mode="HTML",
        )
        return

    if payload is None:
        await query.edit_message_text(
            f"<b>{assistant_name}</b>\n\nTidak ada aksi yang sedang menunggu.",
            parse_mode="HTML",
        )
        return

    await query.edit_message_text(
        payload.text,
        parse_mode=payload.parse_mode,
        reply_markup=InlineKeyboardMarkup([]) if payload.inline_buttons else None,
    )

    if payload.has_attachment and query.message is not None:
        from io import BytesIO
        from telegram import InputFile
        document = InputFile(
            BytesIO(payload.attachment_bytes or b""),
            filename=payload.attachment_filename or "output.txt",
        )
        await query.message.reply_document(document=document)

    if payload.post_send_action == "restart_self":
        manager = context.application.bot_data.get("self_maintenance_manager")
        if manager is not None:
            chat_id = query.message.chat_id if query.message else None
            manager.schedule_restart(
                notify_chat_id=chat_id,
                notify_text=(
                    f"<b>{assistant_name}</b>\n\n"
                    "Saya sudah aktif lagi dan siap lanjut."
                ) if chat_id else None,
            )
