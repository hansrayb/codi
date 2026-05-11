"""Status handlers for the orchestrated Codex Telegram bot."""

from __future__ import annotations

import platform
from datetime import datetime, timezone
from pathlib import Path

import psutil
from telegram import Update
from telegram.ext import ContextTypes

from handlers.auth import require_role


@require_role("operator")
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
    service_watch_manager = context.application.bot_data["service_watch_manager"]
    alert_target_registry = context.application.bot_data["alert_target_registry"]
    service_watch_stats = await service_watch_manager.get_stats()
    alert_target_stats = await alert_target_registry.get_stats()
    active_cwd = snapshot["active_cwd"]
    active_workspace = Path(active_cwd).name if active_cwd else "-"
    active_case_title = snapshot["active_case_title"] or "-"
    active_repo_path = snapshot["active_case_repo"] or active_cwd or "-"
    safety_pending = snapshot["safety_pending"] or "-"
    active_target_kind = snapshot.get("active_target_kind", "host")
    active_target_device_id = snapshot.get("active_target_device_id")
    active_target_device_label = snapshot.get("active_target_device_label")
    if active_target_kind == "device" and active_target_device_id:
        target_display = (
            f"device {active_target_device_label or active_target_device_id}"
            f" ({active_target_device_id})"
        )
    else:
        target_display = "host pusat"

    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count() or 1
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    host_uptime_seconds = _read_uptime_seconds()
    bot_uptime_seconds = int((datetime.now(timezone.utc) - started_at).total_seconds())

    ai_backend = snapshot.get("ai_backend", "claude").upper()
    lines = [
        f"Status {assistant_name} - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"AI Backend      : {ai_backend}",
        f"Versi Python    : {platform.python_version()}",
        f"Konteks aktif   : {active_case_title}",
        f"Session aktif   : {snapshot['active_sessions']} / {snapshot['max_active_sessions']}",
        f"Role aktif      : {snapshot['active_role'] or '-'}",
        f"Repo aktif      : {active_workspace}",
        f"Path repo aktif : {active_repo_path}",
        f"Target aktif    : {target_display}",
        f"Repo dipantau   : {snapshot['watched_repos']}",
        (
            "Monitor host   : "
            f"svc {service_watch_stats.unhealthy_services}/{service_watch_stats.monitored_services} down, "
            f"pm2 {service_watch_stats.unhealthy_pm2_apps}/{service_watch_stats.monitored_pm2_apps} down"
        ),
        f"Target alert    : {alert_target_stats['registered_targets']} chat",
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
