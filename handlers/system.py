"""System command handlers for start, help, and reset flows."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from handlers.auth import require_auth, require_role
from handlers.messages import _build_inline_markup


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


@require_role("operator")
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


@require_role("operator")
async def devices_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """List registered devices known by the central bot."""

    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return

    orchestrator = context.application.bot_data["orchestrator"]
    payload = orchestrator.render_devices_panel(user.id)
    await message.reply_text(
        payload.text,
        parse_mode=payload.parse_mode,
        reply_markup=_build_inline_markup(payload.inline_buttons),
    )


def _build_help_text(context: ContextTypes.DEFAULT_TYPE) -> str:
    assistant_name = context.application.bot_data["settings"].assistant_name
    return f"""{assistant_name} aktif.

Kirim pesan biasa untuk menjalankan task.
Contoh:
- /chat bahas ide onboarding user tanpa eksekusi task
- review auth middleware ini
- buat endpoint login FastAPI
- kenapa service systemd gagal start
- cek repo web-dashboard-payroll
- repo aktif saat ini
- pakai repo AI-Agent-Telegram
- pakai builder, perbaiki bug di /home/hans/aplikasi-customerchant
- di repo ini, perbaiki Codi agar /help lebih jelas
- pantau repo ini
- stop pantau repo ini
- repo yang dipantau apa
- device yang online apa saja
- status semua device
- detail device laptop-kerja
- pakai host pusat
- pakai device absen-server
- Codi laptop ku sedang menjalankan aplikasi apa
- tampilkan log Codi terbaru
- kirim screenshot laptop sekarang
- kirim screenshot laptop sekarang dan ringkas isi layar
- kirim screenshot monitor aktif
- kirim screenshot jendela aktif sekarang
- /screenshot
- /screenshot monitor
- /screenshot jendela
- /screenshot ringkas
- tambah fitur /ping ke kamu
- perbaiki help text kamu
- tambahkan command /version ke codi
- ubah timeout codex jadi 900
- apakah kamu bisa memodifikasi dirimu sendiri
- ai backend saat ini
- pakai claude
- pakai codex
- mode saya apa
- mode aman
- mode ops
- mode admin
- lanjutkan aksi
- batal aksi
- restart codi
- ubah codex timeout jadi 600
- ubah local shell timeout jadi 600
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
- commit semua perubahan di repo ini dengan pesan "Update payroll flow"
- cherry-pick commit a1b2c3d di repo ini
- rollback commit terakhir di repo ini
- rollback ke tag v1.2.3 di repo ini
- buat tag v1.2.3 di repo ini
- cek health service codex-agent
- cek health semua service penting
- status service codex-agent
- start service payroll
- stop service payroll
- restart service payroll
- lihat log service payroll
- pm2 status rotasi-front-staging
- restart pm2 rotasi-front-staging
- lihat log pm2 rotasi-front-staging
- publish build frontend payroll
- deploy frontend payroll
- publish backend payroll
- deploy backend payroll
- test backend payroll
- build frontend payroll
- test repo web-dashboard-payroll

	Untuk task edit, Codi akan menyiapkan diff dulu.
	Balas `lanjutkan` untuk apply checkpoint edit itu, atau `batal` untuk membuang revisi terakhir.
	Selama konteks kerja yang sama masih aktif, draft edit akan tetap dipakai supaya revisi lanjutan tidak mulai dari nol.

	Untuk aksi host yang sensitif seperti restart, shell langsung, deploy, push, merge, atau ubah `.env`,
	Codi sekarang pakai safety layer.
	Kamu bisa pindah mode dengan `mode aman`, `mode ops`, atau `mode admin`,
	lalu balas `lanjutkan aksi` atau `batal aksi` saat diminta konfirmasi 2 langkah.

Konteks kerja sekarang lebih lengket karena session AI dijaga per session Codi.
Kalau repo aktif adalah repo Codi sendiri, setelah apply Codi akan cek test lokal lalu restart otomatis bila aman.

Kamu bisa ganti AI backend kapan saja:
- <code>pakai claude</code> - pakai Claude Code CLI
- <code>pakai codex</code> - pakai Codex CLI (default)
- <code>ai backend saat ini</code> - cek backend yang aktif

Commands:
/pilih_project - pilih project bisnis sebagai konteks aktif
/ping - cek cepat apakah Codi aktif
/chat - ngobrol ide dengan backend AI aktif tanpa eksekusi task
/status - cek status {assistant_name.lower()} dan sistem
/screenshot - ambil screenshot desktop saat ini
/devices - lihat device yang terdaftar di bot pusat
/done - akhiri konteks kerja aktif dan session terkait
/reset - reset seluruh konteks kerja aktif kamu
/help - tampilkan bantuan
"""
