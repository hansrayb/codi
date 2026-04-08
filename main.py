"""Entry point for the orchestrated Codex Telegram bot."""

from __future__ import annotations

import asyncio
import os
import sys
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path

from telegram import Update
from telegram.ext import Application, ApplicationBuilder

from config import ConfigError, Settings, load_settings
from core.case_manager import CaseManager
from core.desktop_actions import DesktopActionManager
from core.desktop_screenshot import DesktopScreenshotService
from core.edit_approval import EditApprovalManager
from core.local_shell import LocalShellService
from core.orchestrator import Orchestrator
from core.repo_resolver import RepoResolver
from core.repo_watch import RepoWatchManager
from core.router import IntentRouter
from core.self_maintenance import SelfMaintenanceManager
from core.session_manager import SessionManager
from core.system_activity import SystemActivityInspector
from handlers import register_handlers
from utils.logger import configure_logging


def build_application(settings: Settings) -> Application:
    """Build and wire the Telegram application."""

    logger = configure_logging(settings.log_level, settings.log_file)
    router = IntentRouter(default_role=settings.default_role)
    case_manager = CaseManager(settings)
    session_manager = SessionManager(settings)
    repo_resolver = RepoResolver(settings)
    repo_watch_manager = RepoWatchManager(settings)
    desktop_action_manager = DesktopActionManager()
    desktop_screenshot_service = DesktopScreenshotService()
    local_shell_service = LocalShellService(
        enabled=settings.enable_local_shell,
        default_cwd=settings.codex_work_dir,
        timeout=settings.local_shell_timeout,
    )
    edit_approval_manager = EditApprovalManager(
        draft_ttl_seconds=settings.session_idle_ttl_seconds,
    )
    self_maintenance_manager = SelfMaintenanceManager(
        project_root=Path(__file__).resolve().parent,
        python_bin=sys.executable,
        entrypoint=Path(__file__).resolve(),
        logger=logger,
    )
    system_activity_inspector = SystemActivityInspector(
        log_file=settings.log_file,
        desktop_action_manager=desktop_action_manager,
    )
    orchestrator = Orchestrator(
        settings,
        router,
        case_manager,
        session_manager,
        repo_resolver,
        repo_watch_manager,
        self_maintenance_manager,
        desktop_action_manager,
        desktop_screenshot_service,
        local_shell_service,
        edit_approval_manager,
        system_activity_inspector,
        logger,
    )

    application = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    application.bot_data.update(
        {
            "settings": settings,
            "logger": logger,
            "router": router,
            "case_manager": case_manager,
            "session_manager": session_manager,
            "repo_resolver": repo_resolver,
            "repo_watch_manager": repo_watch_manager,
            "desktop_action_manager": desktop_action_manager,
            "desktop_screenshot_service": desktop_screenshot_service,
            "local_shell_service": local_shell_service,
            "edit_approval_manager": edit_approval_manager,
            "self_maintenance_manager": self_maintenance_manager,
            "system_activity_inspector": system_activity_inspector,
            "orchestrator": orchestrator,
            "started_at": datetime.now(timezone.utc),
        }
    )
    register_handlers(application)
    return application


async def _post_init(application: Application) -> None:
    """Start background services after Telegram polling is initialized."""

    watch_task = asyncio.create_task(_repo_watch_loop(application))
    application.bot_data["repo_watch_task"] = watch_task


async def _post_shutdown(application: Application) -> None:
    """Stop background services before the app exits."""

    self_maintenance_manager = application.bot_data.get("self_maintenance_manager")
    if self_maintenance_manager is not None:
        self_maintenance_manager.cancel_restart()

    watch_task = application.bot_data.pop("repo_watch_task", None)
    if watch_task is None:
        return
    watch_task.cancel()
    with suppress(asyncio.CancelledError):
        await watch_task


async def _repo_watch_loop(application: Application) -> None:
    """Send Telegram notifications when a watched repo changes."""

    settings: Settings = application.bot_data["settings"]
    logger = application.bot_data["logger"]
    manager: RepoWatchManager = application.bot_data["repo_watch_manager"]

    while True:
        try:
            alerts = await manager.scan_once(assistant_name=settings.assistant_name)
            for alert in alerts:
                logger.info(
                    "user_id=%s | action=repo_watch_alert | chat_id=%s",
                    alert.user_id,
                    alert.chat_id,
                )
                await application.bot.send_message(
                    chat_id=alert.chat_id,
                    text=alert.payload.text,
                    parse_mode=alert.payload.parse_mode,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("action=repo_watch_loop_failed")
        await asyncio.sleep(settings.repo_watch_poll_seconds)


def main() -> None:
    """Start the Telegram bot using the configured settings."""

    if hasattr(os, "geteuid") and os.geteuid() == 0:
        raise SystemExit("Bot tidak boleh dijalankan sebagai root.")

    try:
        settings = load_settings()
    except ConfigError as exc:
        raise SystemExit(f"Konfigurasi tidak valid: {exc}") from exc

    application = build_application(settings)
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
