"""Message handlers for natural-language task execution."""

from __future__ import annotations

from io import BytesIO

from telegram import InputFile, Update
from telegram.ext import ContextTypes

from core.orchestrator import OrchestratorUserError
from handlers.auth import require_auth
from utils.progress import TelegramProgressReporter


@require_auth
async def handle_text_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Treat any plain text message as an orchestrated Codex task."""

    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return

    chat_id = update.effective_chat.id if update.effective_chat is not None else None
    orchestrator = context.application.bot_data["orchestrator"]
    control_payload = await orchestrator.try_handle_control_message(user.id, message.text or "")
    if control_payload is not None:
        await _send_payload(message, control_payload)
        await _handle_post_send_action(context, control_payload, chat_id=chat_id)
        return

    device_payload = await orchestrator.try_handle_device_message(user.id, message.text or "")
    if device_payload is not None:
        await _send_payload(message, device_payload)
        await _handle_post_send_action(context, device_payload, chat_id=chat_id)
        return

    watch_payload = await orchestrator.try_handle_repo_watch_message(
        user.id,
        chat_id if chat_id is not None else user.id,
        message.text or "",
    )
    if watch_payload is not None:
        await _send_payload(message, watch_payload)
        await _handle_post_send_action(context, watch_payload, chat_id=chat_id)
        return

    direct_payload = await orchestrator.try_handle_direct_query(user.id, message.text or "")
    if direct_payload is not None:
        await _send_payload(message, direct_payload)
        await _handle_post_send_action(context, direct_payload, chat_id=chat_id)
        return

    try:
        prepared = await orchestrator.prepare_dispatch(user.id, message.text or "")
    except OrchestratorUserError as exc:
        await message.reply_text(exc.user_message)
        return

    if prepared.kind == "desktop_action":
        await message.reply_text(prepared.ack_text)
        payload = await orchestrator.run_prepared(prepared)
        await _send_payload(message, payload)
        await _handle_post_send_action(context, payload, chat_id=chat_id)
        return

    assistant_name = context.application.bot_data["settings"].assistant_name
    progress_message = await message.reply_text(prepared.ack_text)
    reporter = TelegramProgressReporter(
        message=progress_message,
        assistant_name=assistant_name,
        role=prepared.role,
        session_id=prepared.session.session_id if prepared.session is not None else "-",
    )
    payload = await orchestrator.run_prepared(prepared, on_progress=reporter.push)
    await reporter.flush(completed=True)
    await _send_payload(message, payload)
    await _handle_post_send_action(context, payload, chat_id=chat_id)


async def _send_payload(message, payload) -> None:
    await message.reply_text(payload.text, parse_mode=payload.parse_mode)
    if payload.has_photo:
        photo = InputFile(
            BytesIO(payload.photo_bytes or b""),
            filename=payload.photo_filename or "image.png",
        )
        await message.reply_photo(photo=photo)
    if not payload.has_attachment:
        return
    document = InputFile(
        BytesIO(payload.attachment_bytes or b""),
        filename=payload.attachment_filename or "output.txt",
    )
    await message.reply_document(document=document)


async def _handle_post_send_action(
    context: ContextTypes.DEFAULT_TYPE,
    payload,
    *,
    chat_id: int | None = None,
) -> None:
    if payload.post_send_action != "restart_self":
        return
    manager = context.application.bot_data.get("self_maintenance_manager")
    if manager is None:
        return
    assistant_name = context.application.bot_data["settings"].assistant_name
    manager.schedule_restart(
        notify_chat_id=chat_id,
        notify_text=(
            f"<b>{assistant_name}</b>\n\n"
            "Saya sudah aktif lagi dan siap lanjut."
        )
        if chat_id is not None
        else None,
    )
