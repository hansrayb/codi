"""Handler untuk perintah /cekrepo — list dan pilih repo aktif."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from handlers.auth import require_auth

_MAX_CALLBACK_PATH_LEN = 49  # cekrepo:select: = 15, total max 64


@require_auth
async def cekrepo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return

    orchestrator = context.application.bot_data["orchestrator"]
    assistant_name = context.application.bot_data["settings"].assistant_name

    repos = orchestrator.list_indexed_repos()

    if not repos:
        await message.reply_text(
            f"<b>{assistant_name}</b>\n\nTidak ada repo yang ditemukan di direktori yang diizinkan.",
            parse_mode="HTML",
        )
        return

    buttons: list[list[InlineKeyboardButton]] = []
    skipped: list[str] = []

    for repo in repos:
        path_str = str(repo.root)
        if len(path_str) > _MAX_CALLBACK_PATH_LEN:
            skipped.append(repo.name)
            continue
        callback_data = f"cekrepo:select:{path_str}"
        buttons.append([InlineKeyboardButton(f"📁 {repo.name}", callback_data=callback_data)])

    if not buttons:
        await message.reply_text(
            f"<b>{assistant_name}</b>\n\nSemua repo ditemukan tapi path-nya terlalu panjang untuk ditampilkan sebagai tombol.",
            parse_mode="HTML",
        )
        return

    skip_note = ""
    if skipped:
        skip_note = f"\n\n<i>⚠️ {len(skipped)} repo tidak ditampilkan karena path terlalu panjang: {', '.join(skipped)}</i>"

    await message.reply_text(
        f"<b>{assistant_name}</b>\n\nDitemukan <b>{len(buttons)}</b> repo. Tap untuk set sebagai konteks aktif:{skip_note}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
