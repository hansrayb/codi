"""System command handlers for start, help, and reset flows."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from handlers.auth import require_auth, require_role


@require_auth
async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Send the primary help text."""

    message = update.effective_message
    if message is None:
        return
    await message.reply_text(_build_help_text(context))


@require_auth
async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Alias for the start/help output."""

    message = update.effective_message
    if message is None:
        return
    await message.reply_text(_build_help_text(context))


@require_auth
async def ping_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Return a lightweight liveness response."""

    message = update.effective_message
    if message is None:
        return
    await message.reply_text("Pong! Codi aktif.")


@require_role("operator")
async def reset_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Clear the user's active work context."""

    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return

    orchestrator = context.application.bot_data["orchestrator"]
    reset_count = await orchestrator.reset_user(user.id)
    await message.reply_text(
        f"Konteks kerja direset. {reset_count} session lama dibersihkan."
    )


def _build_help_text(context: ContextTypes.DEFAULT_TYPE) -> str:
    assistant_name = context.application.bot_data["settings"].assistant_name
    return f"""{assistant_name} siap.

Kirim pesan apapun — langsung dijawab.

Contoh:
- transaksi emas hari ini berapa?
- rekap absensi bulan ini
- siapa karyawan yang belum absen hari ini?
- berapa payroll bulan ini?
- analisis performa mitra
- kenapa service X gagal start?
- buatkan endpoint login FastAPI
- review PR ini
- restart pm2 rotasi-backend

Untuk aksi sensitif (restart, deploy, push, edit .env), Codi akan minta konfirmasi dulu.
Balas "lanjutkan" atau "batal" saat diminta.

/ping - cek Codi aktif
/status - lihat status sistem dan session
/reset - reset konteks kalau Codi stuck
/help - tampilkan pesan ini
"""
