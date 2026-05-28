"""Entry point for the orchestrated Codi Telegram bot."""

from __future__ import annotations

import asyncio
import os
import sys
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path

from telegram import BotCommand, Update
from telegram.ext import Application, ApplicationBuilder

from config import ConfigError, Settings, load_settings
from core.alert_targets import AlertTargetRegistry
from core.agent_messaging import AgentMessagingStore
from core.auth import AuthDb, AuthService, JwtHelper
from core.case_manager import CaseManager
from core.codi_sessions import CodiSessionStore
from core.device_api import DeviceApiServer
from core.device_registry import DeviceRegistryManager
from core.device_tasks import DeviceContextStore, DeviceTaskQueue
from core.desktop_actions import DesktopActionManager
from core.desktop_screenshot import DesktopScreenshotService
from core.edit_approval import EditApprovalManager
from core.local_shell import LocalShellService
from core.orchestrator import Orchestrator
from core.repo_resolver import RepoResolver
from core.repo_watch import RepoWatchManager
from core.service_watch import ServiceWatchManager
from core.router import IntentRouter
from core.safety import SafetyManager
from core.self_maintenance import SelfMaintenanceManager
from core.session_manager import SessionManager
from core.system_activity import SystemActivityInspector
from handlers import register_handlers
from utils.logger import configure_logging


def _git_head_info(project_root: Path) -> str:
    import subprocess
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%h %s"],
            capture_output=True, text=True, cwd=str(project_root), timeout=5,
        )
        return result.stdout.strip() or "-"
    except Exception:
        return "-"


def _make_notify_fn(bot, settings, loop, logger):
    from html import escape as _escape

    async def _send(text: str) -> None:
        for uid in settings.admin_user_ids:
            try:
                await bot.send_message(chat_id=uid, text=text, parse_mode="HTML")
            except Exception:
                logger.exception("action=notify_admin_failed | uid=%s", uid)

    def notify_fn(text: str) -> None:
        asyncio.run_coroutine_threadsafe(_send(text), loop)

    return notify_fn


def build_application(settings: Settings) -> Application:
    """Build and wire the Telegram application."""

    logger = configure_logging(settings.log_level, settings.log_file)
    router = IntentRouter(default_role=settings.default_role)
    case_manager = CaseManager(settings)
    session_manager = SessionManager(settings)
    repo_resolver = RepoResolver(settings)
    repo_watch_manager = RepoWatchManager(settings)
    alert_target_registry = AlertTargetRegistry(settings.alert_targets_path)
    service_watch_manager = ServiceWatchManager(
        settings,
        alert_targets=alert_target_registry,
    )
    device_registry_manager = DeviceRegistryManager(
        registry_path=settings.device_registry_path,
        heartbeat_ttl_seconds=settings.device_heartbeat_ttl_seconds,
        assistant_name=settings.assistant_name,
        logger=logger,
    )
    device_task_queue = DeviceTaskQueue(
        queue_path=settings.claude_work_dir / "codi-device-tasks.json",
        logger=logger,
    )
    device_context_store = DeviceContextStore(
        context_path=settings.claude_work_dir / "codi-device-contexts.json",
        logger=logger,
    )
    auth_service: AuthService | None = None
    if settings.codi_jwt_secret:
        auth_db = AuthDb.connect(settings.auth_db_path)
        auth_db.seed_default_roles()
        jwt_helper = JwtHelper(
            secret=settings.codi_jwt_secret,
            access_ttl_minutes=settings.codi_jwt_access_ttl_minutes,
            refresh_ttl_days=settings.codi_jwt_refresh_ttl_days,
        )
        auth_service = AuthService(auth_db, jwt_helper)
        logger.info("action=auth_service_ready | db=%s", settings.auth_db_path)
    else:
        logger.warning(
            "CODI_JWT_SECRET tidak di-set — mobile auth real dinonaktifkan, "
            "hanya bootstrap shared-token yang berfungsi.",
        )

    device_api_server = DeviceApiServer(
        host=settings.device_api_host,
        port=settings.device_api_port,
        shared_token=settings.device_api_shared_token or "",
        registry=device_registry_manager,
        task_queue=device_task_queue,
        logger=logger,
        auth_service=auth_service,
        allow_bootstrap_token=settings.allow_bootstrap_token,
    )

    # Agent-to-agent messaging (peer messaging antar Claude Code agent
    # via Codi broker). Same SQLite db dir sebagai auth db.
    agent_msg_path = settings.auth_db_path.parent / "codi-agent-messages.db"
    agent_msg_store = AgentMessagingStore.connect(agent_msg_path)
    device_api_server.set_agent_messaging_store(agent_msg_store)
    logger.info("action=agent_messaging_ready | db=%s", agent_msg_path)
    desktop_action_manager = DesktopActionManager()
    desktop_screenshot_service = DesktopScreenshotService()
    local_shell_service = LocalShellService(
        enabled=settings.enable_local_shell,
        default_cwd=settings.claude_work_dir,
        timeout=settings.local_shell_timeout,
    )
    edit_approval_manager = EditApprovalManager(
        draft_ttl_seconds=settings.session_idle_ttl_seconds,
    )
    _non_readonly_ids = set(settings.allowed_user_ids) - set(settings.viewer_user_ids) - set(settings.business_user_ids)
    _ops_ids = tuple(uid for uid in settings.allowed_user_ids if uid in _non_readonly_ids)
    safety_manager = SafetyManager(
        assistant_name=settings.assistant_name,
        allowed_user_ids=settings.allowed_user_ids,
        default_mode="ops",
        admin_user_ids=settings.admin_user_ids or tuple(_non_readonly_ids),
        ops_user_ids=_ops_ids or tuple(_non_readonly_ids),
        approval_ttl_seconds=180,
        audit_log_path=settings.claude_work_dir / "codi-audit.log",
        logger=logger,
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
        device_registry_manager,
        self_maintenance_manager,
        desktop_action_manager,
        desktop_screenshot_service,
        local_shell_service,
        edit_approval_manager,
        safety_manager,
        system_activity_inspector,
        logger,
        device_task_queue=device_task_queue,
        device_context_store=device_context_store,
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
            "alert_target_registry": alert_target_registry,
            "service_watch_manager": service_watch_manager,
            "device_registry_manager": device_registry_manager,
            "device_task_queue": device_task_queue,
            "device_context_store": device_context_store,
            "device_api_server": device_api_server,
            "desktop_action_manager": desktop_action_manager,
            "desktop_screenshot_service": desktop_screenshot_service,
            "local_shell_service": local_shell_service,
            "edit_approval_manager": edit_approval_manager,
            "safety_manager": safety_manager,
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

    logger = application.bot_data["logger"]
    settings: Settings = application.bot_data["settings"]
    self_maintenance_manager: SelfMaintenanceManager = application.bot_data[
        "self_maintenance_manager"
    ]
    device_api_server: DeviceApiServer = application.bot_data["device_api_server"]
    if settings.enable_device_registry:
        try:
            device_api_server.start()
        except Exception:
            logger.exception("action=device_api_start_failed")

        loop = asyncio.get_running_loop()
        device_api_server.set_notify_fn(
            _make_notify_fn(application.bot, settings, loop, logger)
        )

        _orch: Orchestrator = application.bot_data["orchestrator"]

        async def _chat_async(message: str, user_id: int, scope: str = "") -> str:
            prepared = await _orch.prepare_dispatch(
                user_id or settings.admin_user_ids[0], message, scope=scope
            )
            payload = await _orch.run_prepared(prepared)
            return payload.text

        def _chat_sync(message: str, user_id: int, scope: str = "") -> str:
            future = asyncio.run_coroutine_threadsafe(_chat_async(message, user_id, scope), loop)
            return future.result(timeout=120)

        device_api_server.set_chat_fn(_chat_sync)

        # ── Dashboard SSE streaming wiring ──────────────────────────────────
        codi_session_store = CodiSessionStore(db_path=settings.codi_sessions_db_path)

        async def _chat_stream(
            *, session_id, message, user_id, on_token, claude_session_id, cancel_event
        ):
            return await _orch.run_chat_streaming(
                message=message,
                user_id=user_id or settings.admin_user_ids[0],
                on_token=on_token,
                claude_session_id=claude_session_id,
                cancel_event=cancel_event,
            )

        device_api_server.set_chat_stream_factory(_chat_stream)
        device_api_server.set_loop(loop)
        device_api_server.set_session_store(codi_session_store)

    assistant_name = settings.assistant_name
    try:
        await application.bot.set_my_commands([
            BotCommand("start", f"Mulai dan lihat panduan {assistant_name}"),
            BotCommand("help", f"Lihat daftar lengkap kemampuan {assistant_name}"),
            BotCommand("ping", f"Cek cepat apakah {assistant_name} aktif"),
            BotCommand("chat", "Ngobrol ide dengan backend AI aktif"),
            BotCommand("status", f"Cek status {assistant_name} dan sistem"),
            BotCommand("screenshot", "Ambil screenshot desktop saat ini"),
            BotCommand("cekrepo", "List repo yang tersedia dan pilih yang aktif"),
            BotCommand("done", "Tutup konteks kerja aktif"),
            BotCommand("reset", "Reset semua session aktif"),
            BotCommand("devices", "Lihat device yang terdaftar"),
        ])
    except Exception:
        logger.exception("action=set_my_commands_failed")

    restart_notice = self_maintenance_manager.consume_restart_notice()
    if restart_notice is not None:
        chat_id, text = restart_notice
        try:
            await application.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
            )
        except Exception:
            logger.exception("action=restart_notice_failed | chat_id=%s", chat_id)

    git_info = _git_head_info(Path(__file__).parent)
    started_at = application.bot_data["started_at"].strftime("%Y-%m-%d %H:%M UTC")
    startup_text = (
        f"✅ <b>{assistant_name} aktif</b>\n\n"
        f"Commit: <code>{git_info}</code>\n"
        f"Waktu: {started_at}"
    )
    for uid in settings.admin_user_ids:
        try:
            await application.bot.send_message(chat_id=uid, text=startup_text, parse_mode="HTML")
        except Exception:
            logger.exception("action=startup_notice_failed | uid=%s", uid)

    watch_task = asyncio.create_task(_repo_watch_loop(application))
    service_watch_task = asyncio.create_task(_service_watch_loop(application))
    application.bot_data["repo_watch_task"] = watch_task
    application.bot_data["service_watch_task"] = service_watch_task


async def _post_shutdown(application: Application) -> None:
    """Stop background services before the app exits."""

    self_maintenance_manager = application.bot_data.get("self_maintenance_manager")
    if self_maintenance_manager is not None:
        self_maintenance_manager.cancel_restart()
    device_api_server = application.bot_data.get("device_api_server")
    if device_api_server is not None:
        device_api_server.stop()

    for task_name in ("repo_watch_task", "service_watch_task"):
        watch_task = application.bot_data.pop(task_name, None)
        if watch_task is None:
            continue
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


async def _service_watch_loop(application: Application) -> None:
    """Send Telegram notifications when a monitored service or PM2 app changes state."""

    settings: Settings = application.bot_data["settings"]
    logger = application.bot_data["logger"]
    manager: ServiceWatchManager = application.bot_data["service_watch_manager"]

    while True:
        try:
            alerts = await manager.scan_once(assistant_name=settings.assistant_name)
            for alert in alerts:
                logger.info(
                    "user_id=%s | action=service_watch_alert | chat_id=%s",
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
            logger.exception("action=service_watch_loop_failed")
        await asyncio.sleep(settings.service_watch_poll_seconds)


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
