"""Screenshot command handler."""

from __future__ import annotations

from io import BytesIO

from telegram import InputFile, Update
from telegram.ext import ContextTypes

from core.desktop_screenshot import (
    DesktopScreenshotError,
    DesktopScreenshotRequest,
    DesktopScreenshotService,
)
from core.system_activity import SystemActivityInspector, SystemActivityRequest
from handlers.auth import require_auth
from utils.formatter import format_desktop_screenshot_payload, format_error_payload

SUMMARY_HINTS = (
    "ringkas",
    "ringkasan",
    "summary",
    "jelaskan",
    "deskripsikan",
    "isi layar",
)
WINDOW_HINTS = (
    "active window",
    "jendela aktif",
    "window aktif",
    "jendela",
    "window",
)
MONITOR_HINTS = (
    "current monitor",
    "monitor aktif",
    "layar aktif",
    "monitor",
)


@require_auth
async def screenshot_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Capture the current desktop and send it back to Telegram."""

    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return

    settings = context.application.bot_data["settings"]
    logger = context.application.bot_data["logger"]
    service: DesktopScreenshotService = context.application.bot_data[
        "desktop_screenshot_service"
    ]
    request = parse_screenshot_command_args(" ".join(context.args or ()))

    logger.info(
        "user_id=%s | action=screenshot_command | mode=%s | include_summary=%s",
        user.id,
        request.mode,
        request.include_summary,
    )

    try:
        screenshot = await service.capture(request)
    except DesktopScreenshotError as exc:
        payload = format_error_payload(str(exc), assistant_name=settings.assistant_name)
        await message.reply_text(payload.text, parse_mode=payload.parse_mode)
        return
    except Exception:
        logger.exception("user_id=%s | action=screenshot_command_failed", user.id)
        payload = format_error_payload(
            "Codi belum berhasil mengambil screenshot desktop saat ini.",
            assistant_name=settings.assistant_name,
        )
        await message.reply_text(payload.text, parse_mode=payload.parse_mode)
        return

    report = None
    if request.include_summary:
        inspector: SystemActivityInspector | None = context.application.bot_data.get(
            "system_activity_inspector"
        )
        if inspector is not None:
            try:
                report = await inspector.inspect(
                    SystemActivityRequest(include_processes=True, include_logs=False)
                )
            except Exception:
                logger.exception(
                    "user_id=%s | action=screenshot_command_summary_failed",
                    user.id,
                )

    payload = format_desktop_screenshot_payload(
        assistant_name=settings.assistant_name,
        screenshot=screenshot,
        report=report,
        include_summary_requested=request.include_summary,
    )
    await message.reply_text(payload.text, parse_mode=payload.parse_mode)
    if payload.has_photo:
        photo = InputFile(
            BytesIO(payload.photo_bytes or b""),
            filename=payload.photo_filename or "desktop-screenshot.png",
        )
        await message.reply_photo(photo=photo)


def parse_screenshot_command_args(args_text: str) -> DesktopScreenshotRequest:
    """Parse optional `/screenshot` arguments into a screenshot request."""

    normalized = " ".join(args_text.strip().lower().split())
    mode = "fullscreen"
    if any(hint in normalized for hint in WINDOW_HINTS):
        mode = "active_window"
    elif any(hint in normalized for hint in MONITOR_HINTS):
        mode = "current_monitor"

    return DesktopScreenshotRequest(
        mode=mode,
        include_summary=any(hint in normalized for hint in SUMMARY_HINTS),
    )
