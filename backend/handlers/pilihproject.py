"""Handler untuk perintah /pilih-project — list dan pilih project bisnis."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from handlers.auth import require_auth

_MAX_CALLBACK_PATH_LEN = 53  # pilihproject:select: = 19, total max 64


@require_auth
async def pilihproject_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return

    settings = context.application.bot_data["settings"]
    orchestrator = context.application.bot_data["orchestrator"]
    assistant_name = settings.assistant_name

    if not settings.business_allowed_dirs:
        await message.reply_text(
            f"<b>{assistant_name}</b>\n\nBelum ada project bisnis yang dikonfigurasi.\n"
            "Tambahkan <code>BUSINESS_ALLOWED_DIRS</code> di file <code>.env</code>.",
            parse_mode="HTML",
        )
        return

    repos = orchestrator.list_business_repos()

    if not repos:
        await message.reply_text(
            f"<b>{assistant_name}</b>\n\nTidak ada project bisnis yang ditemukan di direktori yang dikonfigurasi.",
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
        callback_data = f"pilihproject:select:{path_str}"
        buttons.append([InlineKeyboardButton(f"📊 {repo.name}", callback_data=callback_data)])

    if not buttons:
        await message.reply_text(
            f"<b>{assistant_name}</b>\n\nSemua project ditemukan tapi path-nya terlalu panjang untuk ditampilkan.",
            parse_mode="HTML",
        )
        return

    skip_note = ""
    if skipped:
        skip_note = f"\n\n<i>⚠️ {len(skipped)} project tidak ditampilkan karena path terlalu panjang: {', '.join(skipped)}</i>"

    await message.reply_text(
        f"<b>{assistant_name}</b>\n\nDitemukan <b>{len(buttons)}</b> project bisnis. Tap untuk set sebagai konteks aktif:{skip_note}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
