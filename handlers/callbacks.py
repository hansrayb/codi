"""Inline keyboard callback query handlers."""

from __future__ import annotations

from pathlib import Path as from_path

from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from core.orchestrator import OrchestratorUserError
from handlers.auth import get_user_role, require_role
from handlers.messages import _build_inline_markup, _send_payload


@require_role("business")
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
    settings = context.application.bot_data["settings"]
    assistant_name = settings.assistant_name
    user_role = get_user_role(user.id, settings)
    if user_role == "business" and not data.startswith("pilihproject:select:"):
        await query.edit_message_text(
            f"<b>{assistant_name}</b>\n\nRole business hanya bisa memilih project bisnis dan membaca data.",
            parse_mode="HTML",
        )
        return

    if data.startswith("device:task:"):
        task_id = data[len("device:task:"):]
        task_queue = context.application.bot_data.get("device_task_queue")
        if task_queue is None:
            await query.answer("Task queue tidak aktif.")
            return
        payload = task_queue.render_task_payload(task_id, assistant_name=assistant_name)
        new_markup: InlineKeyboardMarkup | None = _build_inline_markup(payload.inline_buttons)
        await query.edit_message_text(
            payload.text,
            parse_mode=payload.parse_mode,
            reply_markup=new_markup,
        )
        return

    if data.startswith("device:panel:") or data.startswith("device:target:") or data.startswith("device:detail:"):
        payload = orchestrator.handle_device_panel_callback(user.id, data)
        await query.edit_message_text(
            payload.text,
            parse_mode=payload.parse_mode,
            reply_markup=_build_inline_markup(payload.inline_buttons),
        )
        return

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

    if data.startswith("pilihproject:select:"):
        repo_path = data[len("pilihproject:select:"):]
        if not settings.is_business_dir(from_path(repo_path)):
            await query.edit_message_text(
                f"<b>{assistant_name}</b>\n\nPath ini bukan bagian dari project bisnis yang diizinkan.",
                parse_mode="HTML",
            )
            return
        try:
            payload = await orchestrator.select_repo(user.id, repo_path)
        except Exception as exc:
            await query.edit_message_text(
                f"<b>{assistant_name}</b>\n\nGagal set project: {exc}",
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
