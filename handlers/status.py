"""Status handlers for the orchestrated Codex Telegram bot."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import psutil
from telegram import Update
from telegram.ext import ContextTypes

from handlers.auth import require_auth


@require_auth
async def status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Return a bot and host status summary."""

    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return

    orchestrator = context.application.bot_data["orchestrator"]
    started_at: datetime = context.application.bot_data["started_at"]
    assistant_name = context.application.bot_data["settings"].assistant_name
    snapshot = await orchestrator.get_status_snapshot(user.id)
    active_cwd = snapshot["active_cwd"]
    active_workspace = Path(active_cwd).name if active_cwd else "-"
    active_case_title = snapshot["active_case_title"] or "-"
    active_repo_path = snapshot["active_case_repo"] or active_cwd or "-"
    safety_pending = snapshot["safety_pending"] or "-"

    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count() or 1
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    host_uptime_seconds = _read_uptime_seconds()
    bot_uptime_seconds = int((datetime.now(timezone.utc) - started_at).total_seconds())

    lines = [
        f"Status {assistant_name} - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"Konteks aktif   : {active_case_title}",
        f"Session aktif   : {snapshot['active_sessions']} / {snapshot['max_active_sessions']}",
        f"Role aktif      : {snapshot['active_role'] or '-'}",
        f"Repo aktif      : {active_workspace}",
        f"Path repo aktif : {active_repo_path}",
        f"Repo dipantau   : {snapshot['watched_repos']}",
        f"Device online   : {snapshot['online_devices']} / {snapshot['registered_devices']}",
        f"Task antre      : {snapshot['queued_tasks']}",
        f"Mode keamanan   : {snapshot['safety_mode']} / {snapshot['safety_max_mode']}",
        f"Pending sensitif: {safety_pending}",
        f"{assistant_name} uptime : {_humanize_duration(bot_uptime_seconds)}",
        "",
        "Host:",
        f"CPU  : {cpu_percent:.0f}% ({cpu_count} core)",
        (
            "RAM  : "
            f"{memory.used / (1024 ** 3):.1f} GB / {memory.total / (1024 ** 3):.1f} GB "
            f"({memory.percent:.0f}%)"
        ),
        (
            "Disk : "
            f"{disk.used / (1024 ** 3):.1f} GB / {disk.total / (1024 ** 3):.1f} GB "
            f"({disk.percent:.0f}%) - /"
        ),
        f"Uptime host: {_humanize_duration(host_uptime_seconds)}",
        f"Audit log : {snapshot['audit_log_path']}",
    ]
    await message.reply_text("\n".join(lines))


def _read_uptime_seconds() -> int:
    uptime_text = Path("/proc/uptime").read_text(encoding="utf-8").strip()
    return int(float(uptime_text.split()[0]))


def _humanize_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} detik"
    minutes, remaining_seconds = divmod(seconds, 60)
    hours, remaining_minutes = divmod(minutes, 60)
    days, remaining_hours = divmod(hours, 24)

    parts: list[str] = []
    if days:
        parts.append(f"{days} hari")
    if remaining_hours:
        parts.append(f"{remaining_hours} jam")
    if remaining_minutes:
        parts.append(f"{remaining_minutes} menit")
    if not parts:
        parts.append(f"{remaining_seconds} detik")
    return " ".join(parts[:2])
