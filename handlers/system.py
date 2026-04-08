"""System command handlers for start, help, and reset flows."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from handlers.auth import require_auth


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


@require_auth
async def done_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Close the active work case and related sessions."""

    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return

    orchestrator = context.application.bot_data["orchestrator"]
    payload = await orchestrator.close_active_case(user.id)
    await message.reply_text(payload.text, parse_mode=payload.parse_mode)


def _build_help_text(context: ContextTypes.DEFAULT_TYPE) -> str:
    assistant_name = context.application.bot_data["settings"].assistant_name
    return f"""{assistant_name} aktif.

Kirim pesan biasa untuk menjalankan task.
Contoh:
- review auth middleware ini
- buat endpoint login FastAPI
- kenapa service systemd gagal start
- cek repo web-dashboard-payroll
- pakai builder, perbaiki bug di /home/hans/aplikasi-customerchant
- di repo ini, perbaiki Codi agar /help lebih jelas
- pantau repo ini
- stop pantau repo ini
- repo yang dipantau apa
- Codi laptop ku sedang menjalankan aplikasi apa
- tampilkan log Codi terbaru
- kirim screenshot laptop sekarang
- kirim screenshot laptop sekarang dan ringkas isi layar
- kirim screenshot monitor aktif
- kirim screenshot jendela aktif sekarang
- restart codi
- shell: systemctl --user status codex-agent.service
- bash: git status --short
- pwsh: Get-Process | Select-Object -First 5
- pull repo ini
- cek branch repo ini
- buat branch fitur/login di repo ini
- switch ke branch main di repo ini
- merge branch staging ke main di repo ini
- hapus branch fitur/login di repo ini
- rebase branch fitur/login ke main di repo ini
- commit repo ini dengan pesan "Update payroll flow"
- build frontend payroll
- test repo web-dashboard-payroll

	Untuk task edit, Codi akan menyiapkan diff dulu.
	Balas `lanjutkan` untuk apply checkpoint edit itu, atau `batal` untuk membuang revisi terakhir.
	Selama konteks kerja yang sama masih aktif, draft edit akan tetap dipakai supaya revisi lanjutan tidak mulai dari nol.

Konteks kerja sekarang lebih lengket karena session Codex dijaga per session Codi.
Kalau repo aktif adalah repo Codi sendiri, setelah apply Codi akan cek test lokal lalu restart otomatis bila aman.

Commands:
/status - cek status {assistant_name.lower()} dan sistem
/done - akhiri konteks kerja aktif dan session terkait
/reset - reset seluruh konteks kerja aktif kamu
/help - tampilkan bantuan
"""
