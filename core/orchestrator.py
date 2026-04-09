"""Central orchestration logic for the Telegram Codex agent."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from html import escape
from pathlib import Path

from config import Settings
from core.case_manager import CaseManager
from core.device_registry import DeviceRegistryManager
from core.desktop_actions import (
    DesktopActionManager,
    DesktopActionError,
    DesktopActionRequest,
    match_desktop_action,
)
from core.desktop_screenshot import (
    DesktopScreenshotError,
    DesktopScreenshotService,
    match_desktop_screenshot_query,
)
from core.edit_approval import (
    EditApprovalError,
    EditApprovalManager,
    rewrite_workspace_paths,
)
from core.env_config import (
    EnvConfigError,
    EnvConfigUpdateRequest,
    apply_env_config_update,
    match_env_config_update_query,
)
from core.local_shell import (
    LocalShellError,
    LocalShellRequest,
    LocalShellService,
    build_shell_request_for_repo_shortcut,
    build_shell_request_for_service_shortcut,
    match_local_shell_query,
    match_repo_shell_shortcut,
    match_restart_self_query,
    match_system_service_shortcut,
)
from core.prompts import build_codex_prompt
from core.repo_context import (
    extract_repo_context_selection,
    is_repo_context_status_query,
)
from core.repo_resolver import RepoResolution, RepoResolver, RepoResolverError
from core.repo_watch import RepoWatchError, RepoWatchManager
from core.role_policy import get_role_policy
from core.router import IntentRouter, RoutingDecision
from core.safety import (
    PendingSafetyApproval,
    SafetyManager,
    SafetyPolicy,
    classify_env_config_policy,
    classify_repo_shortcut_policy,
    classify_restart_policy,
    classify_service_shortcut_policy,
    classify_shell_policy,
)
from core.self_maintenance import SelfMaintenanceManager
from core.session_manager import (
    QueueFullError,
    SessionInvalidatedError,
    SessionLease,
    SessionLimitError,
    SessionManager,
)
from core.system_activity import (
    SystemActivityInspector,
    SystemActivityRequest,
    match_system_activity_query,
)
from models.result import MessagePayload
from models.session import Session
from utils.executor import run_codex_task
from utils.formatter import (
    format_desktop_screenshot_payload,
    format_edit_approval_payload,
    format_edit_approval_result,
    format_env_config_update_payload,
    format_error_payload,
    format_execution_payload,
    format_local_shell_payload,
    format_self_update_result,
    format_system_activity_payload,
)
from utils.logger import redact_prompt

ProgressCallback = Callable[[str], Awaitable[None]]


class OrchestratorUserError(RuntimeError):
    """A user-facing error that can be shown directly in Telegram."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


@dataclass(slots=True)
class PreparedDispatch:
    """Prepared execution metadata reserved before Codex is invoked."""

    kind: str
    user_id: int
    prompt: str
    role: str
    session: Session | None
    lease: SessionLease | None
    decision: RoutingDecision | None
    ack_text: str
    execution_prompt: str
    case_id: str | None = None
    repo_resolution: RepoResolution | None = None
    desktop_request: DesktopActionRequest | None = None


class Orchestrator:
    """Coordinate routing, session selection, execution, and formatting."""

    def __init__(
        self,
        settings: Settings,
        router: IntentRouter,
        case_manager: CaseManager,
        session_manager: SessionManager,
        repo_resolver: RepoResolver,
        repo_watch_manager: RepoWatchManager,
        device_registry_manager: DeviceRegistryManager,
        self_maintenance_manager: SelfMaintenanceManager,
        desktop_action_manager: DesktopActionManager,
        desktop_screenshot_service: DesktopScreenshotService,
        local_shell_service: LocalShellService,
        edit_approval_manager: EditApprovalManager,
        safety_manager: SafetyManager,
        system_activity_inspector: SystemActivityInspector,
        logger: logging.Logger,
    ) -> None:
        self._settings = settings
        self._router = router
        self._case_manager = case_manager
        self._session_manager = session_manager
        self._repo_resolver = repo_resolver
        self._repo_watch_manager = repo_watch_manager
        self._device_registry_manager = device_registry_manager
        self._self_maintenance_manager = self_maintenance_manager
        self._desktop_action_manager = desktop_action_manager
        self._desktop_screenshot_service = desktop_screenshot_service
        self._local_shell_service = local_shell_service
        self._edit_approval_manager = edit_approval_manager
        self._safety_manager = safety_manager
        self._system_activity_inspector = system_activity_inspector
        self._logger = logger

    async def prepare_dispatch(self, user_id: int, prompt: str) -> PreparedDispatch:
        """Route the prompt and reserve a session before execution starts."""

        normalized_prompt = prompt.strip()
        if not normalized_prompt:
            raise OrchestratorUserError("Kirim task dalam bentuk pesan teks.")

        desktop_request = match_desktop_action(normalized_prompt)
        if desktop_request is not None and self._settings.enable_desktop_actions:
            self._logger.info(
                "user_id=%s | action=desktop_dispatch | app=%s | operation=%s | prompt=%r",
                user_id,
                desktop_request.action.action_id,
                desktop_request.operation,
                redact_prompt(normalized_prompt),
            )
            operation_text = (
                "membuka" if desktop_request.operation == "open" else "menutup"
            )
            return PreparedDispatch(
                kind="desktop_action",
                user_id=user_id,
                prompt=normalized_prompt,
                role="ops",
                session=None,
                lease=None,
                decision=None,
                ack_text=(
                    f"{self._settings.assistant_name} akan coba "
                    f"{operation_text} {desktop_request.action.label}."
                ),
                execution_prompt="",
                desktop_request=desktop_request,
            )

        active_case = await self._case_manager.get_active_case(user_id)
        active_session = await self._session_manager.get_active_session(user_id)
        try:
            repo_resolution = self._repo_resolver.resolve(
                normalized_prompt,
                active_session,
                active_case,
            )
        except RepoResolverError as exc:
            raise OrchestratorUserError(str(exc)) from exc

        decision = self._router.route(normalized_prompt, active_session)
        policy = get_role_policy(decision.role)
        if (
            policy.allow_write
            and repo_resolution.reason == "default_workdir"
            and not (repo_resolution.root / ".git").exists()
        ):
            raise OrchestratorUserError(
                "Untuk edit kode, sebutkan repo atau path target dulu supaya Codi tidak salah workspace."
            )
        prefer_reuse = self._router.should_reuse(
            normalized_prompt,
            decision,
            active_session,
        )
        case, created_case = await self._case_manager.open_or_reuse_case(
            user_id,
            repo_resolution.root,
            prompt=normalized_prompt,
            role=decision.role,
        )

        try:
            lease = await self._session_manager.acquire_session(
                user_id,
                decision.role,
                repo_resolution.root,
                prefer_reuse=prefer_reuse,
                case_id=case.case_id,
            )
        except SessionLimitError as exc:
            raise OrchestratorUserError(
                "Semua agent sedang sibuk. Coba lagi sebentar."
            ) from exc
        except QueueFullError as exc:
            raise OrchestratorUserError(
                "Session terkait sedang penuh. Coba ulang atau /reset."
            ) from exc
        except SessionInvalidatedError as exc:
            raise OrchestratorUserError(
                "Session sebelumnya berubah saat menunggu. Coba kirim ulang task."
            ) from exc

        session = lease.session
        execution_prompt = build_codex_prompt(
            role=decision.role,
            user_prompt=normalized_prompt,
            session_summary=session.summary,
            assistant_name=self._settings.assistant_name,
            repo_name=repo_resolution.label,
            repo_path=str(repo_resolution.root),
        )
        ack_parts = [
            self._build_ack_text(decision.role),
            self._build_case_ack(case.title, created_case),
            self._build_repo_ack(repo_resolution),
        ]
        if lease.queued_before_acquire:
            ack_parts.append("Task ini sempat masuk antrean sebentar.")
        if decision.role == "general" and decision.confidence < 0.5:
            ack_parts.append("Saya mulai dari jalur umum dulu karena maksud task-nya masih cukup luas.")
        ack_text = "\n".join(ack_parts)

        self._logger.info(
            "user_id=%s | case=%s | session=%s | role=%s | repo=%s | repo_reason=%s | action=dispatch | reuse=%s | confidence=%.2f | prompt=%r",
            user_id,
            case.case_id,
            session.session_id,
            decision.role,
            str(repo_resolution.root),
            repo_resolution.reason,
            str(not lease.created_session).lower(),
            decision.confidence,
            redact_prompt(normalized_prompt),
        )

        return PreparedDispatch(
            kind="codex",
            user_id=user_id,
            prompt=normalized_prompt,
            role=decision.role,
            session=session,
            lease=lease,
            decision=decision,
            ack_text=ack_text,
            execution_prompt=execution_prompt,
            case_id=case.case_id,
            repo_resolution=repo_resolution,
        )

    async def run_prepared(
        self,
        prepared: PreparedDispatch,
        on_progress: ProgressCallback | None = None,
    ) -> MessagePayload:
        """Execute a prepared task and always release its session lease."""

        if prepared.kind == "desktop_action" and prepared.desktop_request is not None:
            return await self._run_desktop_action(prepared)

        started = time.perf_counter()
        policy = get_role_policy(prepared.role)
        if prepared.session is None or prepared.lease is None:
            return format_error_payload(
                "Task ini kehilangan konteks eksekusinya sebelum dijalankan.",
                assistant_name=self._settings.assistant_name,
            )

        summary_update = self._summarize_session(prepared.session.summary, prepared.prompt)
        try:
            if policy.allow_write and prepared.repo_resolution is not None:
                return await self._run_write_task_with_approval(
                    prepared,
                    policy=policy,
                    on_progress=on_progress,
                    started=started,
                )
            result = await run_codex_task(
                prompt=prepared.execution_prompt,
                role=prepared.role,
                cwd=prepared.session.cwd,
                timeout=self._settings.codex_timeout,
                session_id=prepared.session.session_id,
                codex_bin=self._settings.codex_bin,
                model_reasoning_effort=self._settings.codex_reasoning_effort,
                sandbox_mode=policy.sandbox_mode,
                codex_thread_id=prepared.session.codex_thread_id,
                persist_session=True,
                on_progress=on_progress,
            )
            prepared.session.codex_thread_id = result.thread_id
            duration = time.perf_counter() - started
            self._logger.info(
                "user_id=%s | session=%s | role=%s | exit_code=%s | duration=%.2fs",
                prepared.user_id,
                prepared.session.session_id,
                prepared.role,
                result.exit_code,
                duration,
            )
            return format_execution_payload(
                assistant_name=self._settings.assistant_name,
                role=prepared.role,
                session_id=prepared.session.session_id,
                exit_code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr,
                max_output_length=self._settings.max_output_length,
            )
        except FileNotFoundError:
            self._logger.exception(
                "user_id=%s | session=%s | role=%s | action=codex_missing",
                prepared.user_id,
                prepared.session.session_id,
                prepared.role,
            )
            return format_error_payload(
                "Codex CLI tidak ditemukan di sistem.",
                assistant_name=self._settings.assistant_name,
            )
        except asyncio.TimeoutError:
            self._logger.warning(
                "user_id=%s | session=%s | role=%s | action=timeout | timeout=%ss",
                prepared.user_id,
                prepared.session.session_id,
                prepared.role,
                self._settings.codex_timeout,
            )
            return format_error_payload(
                (
                    f"{self._settings.assistant_name} belum selesai dalam "
                    f"{self._settings.codex_timeout} detik. "
                    "Kalau mau, sempitkan fokusnya ke file, folder, atau masalah tertentu."
                ),
                assistant_name=self._settings.assistant_name,
            )
        except Exception:
            self._logger.exception(
                "user_id=%s | session=%s | role=%s | action=unexpected_error",
                prepared.user_id,
                prepared.session.session_id,
                prepared.role,
            )
            return format_error_payload(
                "Terjadi kesalahan internal saat memproses task ini.",
                assistant_name=self._settings.assistant_name,
            )
        finally:
            await prepared.lease.release(summary_update)
            if prepared.case_id is not None:
                await self._case_manager.update_case(
                    prepared.case_id,
                    role=prepared.role,
                    prompt=prepared.prompt,
                )

    async def reset_user(self, user_id: int) -> int:
        """Clear session state for a user."""

        self._safety_manager.reset_user(user_id)
        await self._edit_approval_manager.reset_user(user_id)
        await self._case_manager.reset_user(user_id)
        count = await self._session_manager.reset_user(user_id)
        self._logger.info("user_id=%s | action=reset | sessions=%s", user_id, count)
        return count

    async def close_active_case(self, user_id: int) -> MessagePayload:
        """Close the active case and stop its related sessions."""

        self._safety_manager.clear_pending(user_id)
        if await self._edit_approval_manager.has_pending(user_id):
            try:
                await self._edit_approval_manager.reject(user_id)
            except EditApprovalError:
                pass

        case = await self._case_manager.close_active_case(user_id)
        if case is None:
            return format_error_payload(
                "Belum ada case aktif yang bisa diselesaikan.",
                assistant_name=self._settings.assistant_name,
            )

        await self._edit_approval_manager.close_case(case.case_id)
        closed_sessions = await self._session_manager.close_case_sessions(case.case_id)
        self._logger.info(
            "user_id=%s | action=close_case | case=%s | repo=%s | sessions=%s",
            user_id,
            case.case_id,
            case.repo_root,
            closed_sessions,
        )
        return MessagePayload(
            text=(
                f"<b>{escape(self._settings.assistant_name)} menutup konteks kerja ini.</b>\n\n"
                f"Fokus terakhir: {escape(case.title or 'tanpa judul')}\n"
                f"Repo: <code>{escape(case.repo_root)}</code>\n"
                f"Session yang ditutup: {closed_sessions}"
            ),
            parse_mode="HTML",
        )

    async def try_handle_repo_watch_message(
        self,
        user_id: int,
        chat_id: int,
        text: str,
    ) -> MessagePayload | None:
        """Handle repo watch control messages without invoking Codex."""

        action = self._repo_watch_manager.classify_message(text)
        if action is None:
            return None

        if action == "list":
            return await self._repo_watch_manager.list_watches(
                user_id=user_id,
                assistant_name=self._settings.assistant_name,
            )

        active_case = await self._case_manager.get_active_case(user_id)
        active_session = await self._session_manager.get_active_session(user_id)
        repo_resolution: RepoResolution | None = None
        try:
            repo_resolution = self._repo_resolver.resolve(
                text,
                active_session,
                active_case,
            )
        except RepoResolverError as exc:
            return format_error_payload(
                str(exc),
                assistant_name=self._settings.assistant_name,
            )

        try:
            if action == "start":
                return await self._repo_watch_manager.add_watch(
                    user_id=user_id,
                    chat_id=chat_id,
                    repo_root=repo_resolution.root,
                    repo_label=repo_resolution.label,
                    assistant_name=self._settings.assistant_name,
                )

            target_root: Path | None = None
            if (
                repo_resolution.explicit
                or repo_resolution.used_active_case
                or repo_resolution.used_active_session
            ):
                target_root = repo_resolution.root
            return await self._repo_watch_manager.remove_watch(
                user_id=user_id,
                repo_root=target_root,
                assistant_name=self._settings.assistant_name,
            )
        except RepoWatchError as exc:
            return format_error_payload(
                str(exc),
                assistant_name=self._settings.assistant_name,
            )

    async def get_status_snapshot(self, user_id: int) -> dict[str, object]:
        """Return internal session data for the `/status` handler."""

        stats = await self._session_manager.get_stats(user_id)
        case_stats = await self._case_manager.get_stats(user_id)
        watch_stats = await self._repo_watch_manager.get_stats(user_id)
        device_stats = self._device_registry_manager.get_stats()
        return {
            "active_sessions": stats.active_sessions,
            "busy_sessions": stats.busy_sessions,
            "queued_tasks": stats.queued_tasks,
            "max_active_sessions": stats.max_active_sessions,
            "active_role": stats.active_role,
            "active_cwd": stats.active_cwd,
            "active_case_id": case_stats.active_case_id,
            "active_case_title": case_stats.active_case_title,
            "active_case_repo": case_stats.active_case_repo,
            "user_case_count": case_stats.user_case_count,
            "user_session_count": stats.user_session_count,
            "watched_repos": watch_stats.watched_repos,
            "watched_labels": watch_stats.watched_labels,
            "registered_devices": device_stats.registered_devices,
            "online_devices": device_stats.online_devices,
            "safety_mode": self._safety_manager.get_current_mode(user_id),
            "safety_max_mode": self._safety_manager.get_max_mode(user_id),
            "safety_pending": self._safety_manager.get_pending_summary(user_id),
            "audit_log_path": str(self._safety_manager.get_audit_log_path()),
        }

    async def try_handle_device_message(
        self,
        user_id: int,
        text: str,
    ) -> MessagePayload | None:
        """Handle device-registry queries without invoking Codex."""

        del user_id
        query = self._device_registry_manager.classify_message(text)
        if query is None:
            return None
        if query.action == "list":
            return self._device_registry_manager.render_list_payload()
        if query.action == "detail" and query.device_ref:
            return self._device_registry_manager.render_detail_payload(query.device_ref)
        return None

    @staticmethod
    def _summarize_session(existing_summary: str, prompt: str) -> str:
        snippet = prompt.strip().replace("\n", " ")
        if len(snippet) > 180:
            snippet = f"{snippet[:177]}..."
        if not existing_summary.strip():
            return f"- {snippet}"
        lines = [line for line in existing_summary.splitlines() if line.strip()]
        lines.append(f"- {snippet}")
        return "\n".join(lines[-5:])

    def _build_ack_text(self, role: str) -> str:
        assistant_name = self._settings.assistant_name
        role_messages = {
            "builder": f"{assistant_name} akan mulai mengerjakan task ini.",
            "reviewer": f"{assistant_name} akan meninjau ini dulu.",
            "debugger": f"{assistant_name} akan telusuri masalahnya dulu.",
            "ops": f"{assistant_name} akan cek kondisi sistemnya dulu.",
            "general": f"{assistant_name} akan cek dulu lalu bantu dari sana.",
        }
        return role_messages.get(role, f"{assistant_name} sedang memproses task ini.")

    def _build_repo_ack(self, resolution: RepoResolution) -> str:
        if resolution.reason == "default_workdir":
            return f"Saya mulai dari workspace {resolution.root}."
        if resolution.used_active_case:
            return f"Saya lanjut pakai repo dari case aktif: {resolution.label} ({resolution.root})."
        if resolution.used_active_session:
            return f"Saya lanjut pakai workspace aktif: {resolution.label} ({resolution.root})."
        return f"Saya pakai repo {resolution.label} di {resolution.root}."

    @staticmethod
    def _build_case_ack(case_title: str, created_case: bool) -> str:
        if created_case:
            if case_title:
                return f"Saya buka konteks kerja baru: {case_title}."
            return "Saya buka konteks kerja baru untuk pekerjaan ini."
        if case_title:
            return f"Saya lanjutkan konteks kerja: {case_title}."
        return "Saya lanjutkan konteks kerja yang tadi."

    async def _run_desktop_action(self, prepared: PreparedDispatch) -> MessagePayload:
        request = prepared.desktop_request
        if request is None:
            return format_error_payload(
                "Aksi desktop ini tidak valid.",
                assistant_name=self._settings.assistant_name,
            )

        try:
            message = await self._desktop_action_manager.perform(request)
            self._logger.info(
                "user_id=%s | action=desktop_%s | app=%s",
                prepared.user_id,
                request.operation,
                request.action.action_id,
            )
            return MessagePayload(
                text=(
                    f"<b>{escape(self._settings.assistant_name)}</b>\n\n"
                    f"{escape(message)}"
                ),
                parse_mode="HTML",
            )
        except DesktopActionError as exc:
            self._logger.warning(
                "user_id=%s | action=desktop_%s_failed | app=%s | error=%s",
                prepared.user_id,
                request.operation,
                request.action.action_id,
                str(exc),
            )
            return format_error_payload(
                str(exc),
                assistant_name=self._settings.assistant_name,
            )

    async def try_handle_control_message(
        self,
        user_id: int,
        text: str,
    ) -> MessagePayload | None:
        safety_result = self._safety_manager.try_handle_control_message(user_id, text)
        if safety_result.handled:
            if safety_result.approved and safety_result.pending is not None:
                return await self._execute_approved_safety_action(
                    user_id,
                    safety_result.pending,
                )
            return safety_result.payload

        action = self._edit_approval_manager.classify_control_message(text)
        if action is not None:
            if not await self._edit_approval_manager.has_pending(user_id):
                return None

            try:
                if action == "approve":
                    pending = await self._edit_approval_manager.approve(user_id)
                    self._logger.info(
                        "user_id=%s | action=edit_approved | approval_id=%s | repo=%s | files=%s",
                        user_id,
                        pending.approval_id,
                        str(pending.repo_root),
                        len(pending.changes),
                    )
                    if self._self_maintenance_manager.is_self_repo(pending.repo_root):
                        check_result = await self._self_maintenance_manager.verify_self_update()
                        restart_scheduled = check_result.ready_for_restart
                        if restart_scheduled:
                            self._logger.info(
                                "user_id=%s | action=self_update_verified | compile_ok=%s | tests_ok=%s | restart=pending",
                                user_id,
                                str(check_result.compile_ok).lower(),
                                str(check_result.tests_ok).lower(),
                            )
                        else:
                            self._logger.warning(
                                "user_id=%s | action=self_update_verification_failed | compile_ok=%s | tests_ok=%s",
                                user_id,
                                str(check_result.compile_ok).lower(),
                                str(check_result.tests_ok).lower(),
                            )
                        return format_self_update_result(
                            assistant_name=self._settings.assistant_name,
                            pending=pending,
                            check_result=check_result,
                            max_output_length=self._settings.max_output_length,
                            restart_scheduled=restart_scheduled,
                        )
                    return format_edit_approval_result(
                        assistant_name=self._settings.assistant_name,
                        approved=True,
                        pending=pending,
                    )

                pending = await self._edit_approval_manager.reject(user_id)
                self._logger.info(
                    "user_id=%s | action=edit_rejected | approval_id=%s | repo=%s",
                    user_id,
                    pending.approval_id,
                    str(pending.repo_root),
                )
                return format_edit_approval_result(
                    assistant_name=self._settings.assistant_name,
                    approved=False,
                    pending=pending,
                )
            except EditApprovalError as exc:
                return format_error_payload(
                    str(exc),
                    assistant_name=self._settings.assistant_name,
                )

        case_action = self._case_manager.classify_control_message(text)
        if case_action == "close_case":
            return await self.close_active_case(user_id)
        return None

    async def try_handle_direct_query(
        self,
        user_id: int,
        text: str,
    ) -> MessagePayload | None:
        """Handle runtime host-observability questions directly."""

        if is_repo_context_status_query(text):
            active_case = await self._case_manager.get_active_case(user_id)
            active_session = await self._session_manager.get_active_session(user_id)
            if active_case is None and active_session is None:
                return MessagePayload(
                    text=(
                        f"<b>{escape(self._settings.assistant_name)} belum punya repo aktif saat ini.</b>\n\n"
                        "Sebutkan repo atau path dulu, misalnya <code>pakai repo AI-Agent-Telegram</code>."
                    ),
                    parse_mode="HTML",
                )
            try:
                resolution = self._repo_resolver.resolve(
                    "repo aktif saat ini",
                    active_session,
                    active_case,
                )
            except RepoResolverError as exc:
                return format_error_payload(
                    str(exc),
                    assistant_name=self._settings.assistant_name,
                )
            return MessagePayload(
                text=(
                    f"<b>{escape(self._settings.assistant_name)} sedang pakai repo ini sebagai konteks aktif.</b>\n\n"
                    f"Repo: <code>{escape(resolution.label)}</code>\n"
                    f"Path: <code>{escape(str(resolution.root))}</code>\n\n"
                    "Prompt berikutnya bisa langsung pakai frasa seperti <code>repo ini</code>."
                ),
                parse_mode="HTML",
            )

        repo_context_target = extract_repo_context_selection(text)
        if repo_context_target is not None:
            active_case = await self._case_manager.get_active_case(user_id)
            active_session = await self._session_manager.get_active_session(user_id)
            try:
                resolution_prompt = repo_context_target
                if not resolution_prompt.startswith(("/", "~")) and not resolution_prompt.lower().startswith(
                    ("repo ", "project ", "proyek ", "folder ", "workspace ")
                ):
                    resolution_prompt = f"repo {resolution_prompt}"
                resolution = self._repo_resolver.resolve(
                    resolution_prompt,
                    active_session,
                    active_case,
                )
            except RepoResolverError as exc:
                return format_error_payload(
                    str(exc),
                    assistant_name=self._settings.assistant_name,
                )

            case, created_case = await self._case_manager.open_or_reuse_case(
                user_id,
                resolution.root,
                prompt=f"pakai repo {resolution.label}",
                role="general",
            )
            case_text = (
                f"Konteks kerja baru: {escape(case.title)}"
                if created_case
                else f"Konteks kerja aktif: {escape(case.title)}"
            )
            return MessagePayload(
                text=(
                    f"<b>{escape(self._settings.assistant_name)} sekarang pakai repo ini sebagai konteks aktif.</b>\n\n"
                    f"Repo: <code>{escape(resolution.label)}</code>\n"
                    f"Path: <code>{escape(str(resolution.root))}</code>\n"
                    f"{case_text}\n\n"
                    "Prompt berikutnya bisa langsung menyebut <code>repo ini</code>."
                ),
                parse_mode="HTML",
            )

        if match_restart_self_query(text):
            self._logger.info(
                "user_id=%s | action=restart_self_request | prompt=%r",
                user_id,
                redact_prompt(text),
            )
            policy = classify_restart_policy()
            gate = self._safety_manager.evaluate_action(
                user_id=user_id,
                kind="restart_self",
                payload=None,
                policy=policy,
            )
            if not gate.allowed:
                return gate.payload
            return self._build_restart_payload_with_audit(
                user_id,
                policy=policy,
            )

        env_config_request = match_env_config_update_query(text)
        if env_config_request is not None:
            self._logger.info(
                "user_id=%s | action=env_config_update | key=%s | prompt=%r",
                user_id,
                env_config_request.key,
                redact_prompt(text),
            )
            preview = f"{env_config_request.key}={env_config_request.value}"
            policy = classify_env_config_policy(env_config_request.key, preview)
            gate = self._safety_manager.evaluate_action(
                user_id=user_id,
                kind="env_config",
                payload=env_config_request,
                policy=policy,
            )
            if not gate.allowed:
                return gate.payload
            return self._apply_env_config_with_audit(
                user_id,
                env_config_request,
                policy=policy,
            )

        shell_request = match_local_shell_query(text)
        if shell_request is not None:
            self._logger.info(
                "user_id=%s | action=local_shell_query | shell=%s | prompt=%r",
                user_id,
                shell_request.shell,
                redact_prompt(text),
            )
            active_case = await self._case_manager.get_active_case(user_id)
            cwd = (
                Path(active_case.repo_root)
                if active_case is not None and active_case.repo_root
                else self._settings.codex_work_dir
            )
            try:
                policy = classify_shell_policy(shell_request.command)
            except ValueError as exc:
                return format_error_payload(
                    str(exc),
                    assistant_name=self._settings.assistant_name,
                )
            gate = self._safety_manager.evaluate_action(
                user_id=user_id,
                kind="local_shell",
                payload={"request": shell_request, "cwd": str(cwd)},
                policy=policy,
            )
            if not gate.allowed:
                return gate.payload
            return await self._run_local_shell_with_audit(
                user_id,
                shell_request,
                cwd=cwd,
                policy=policy,
                failure_message="Codi belum berhasil menjalankan perintah shell lokal itu.",
                log_action="local_shell_query_failed",
            )

        service_shortcut = match_system_service_shortcut(text)
        if service_shortcut is not None:
            self._logger.info(
                "user_id=%s | action=service_shell_shortcut | shortcut=%s | prompt=%r",
                user_id,
                service_shortcut.action,
                redact_prompt(text),
            )
            try:
                shell_request = build_shell_request_for_service_shortcut(
                    service_shortcut,
                    important_services=self._settings.important_services,
                )
            except LocalShellError as exc:
                return format_error_payload(
                    str(exc),
                    assistant_name=self._settings.assistant_name,
                )
            policy = classify_service_shortcut_policy(
                service_shortcut.action,
                shell_request.command,
            )
            gate = self._safety_manager.evaluate_action(
                user_id=user_id,
                kind="local_shell",
                payload={
                    "request": shell_request,
                    "cwd": str(self._settings.codex_work_dir),
                },
                policy=policy,
            )
            if not gate.allowed:
                return gate.payload
            return await self._run_local_shell_with_audit(
                user_id,
                shell_request,
                cwd=self._settings.codex_work_dir,
                policy=policy,
                failure_message="Codi belum berhasil menjalankan shortcut service itu.",
                log_action="service_shell_shortcut_failed",
            )

        repo_shortcut = match_repo_shell_shortcut(text)
        if repo_shortcut is not None:
            self._logger.info(
                "user_id=%s | action=repo_shell_shortcut | shortcut=%s | prompt=%r",
                user_id,
                repo_shortcut.action,
                redact_prompt(text),
            )
            active_case = await self._case_manager.get_active_case(user_id)
            active_session = await self._session_manager.get_active_session(user_id)
            try:
                resolution_prompt = repo_shortcut.repo_hint
                if not resolution_prompt.startswith(
                    ("repo ", "project ", "proyek ", "folder ", "workspace ")
                ):
                    resolution_prompt = f"repo {resolution_prompt}"
                repo_resolution = self._repo_resolver.resolve(
                    resolution_prompt,
                    active_session,
                    active_case,
                )
                shell_request = build_shell_request_for_repo_shortcut(
                    repo_shortcut,
                    repo_resolution.root,
                )
            except (LocalShellError, RepoResolverError) as exc:
                return format_error_payload(
                    str(exc),
                    assistant_name=self._settings.assistant_name,
                )
            policy = classify_repo_shortcut_policy(
                repo_shortcut.action,
                shell_request.command,
            )
            gate = self._safety_manager.evaluate_action(
                user_id=user_id,
                kind="local_shell",
                payload={
                    "request": shell_request,
                    "cwd": str(repo_resolution.root),
                },
                policy=policy,
            )
            if not gate.allowed:
                return gate.payload
            return await self._run_local_shell_with_audit(
                user_id,
                shell_request,
                cwd=repo_resolution.root,
                policy=policy,
                failure_message="Codi belum berhasil menjalankan shortcut repo itu.",
                log_action="repo_shell_shortcut_failed",
            )

        screenshot_request = match_desktop_screenshot_query(text)
        if screenshot_request is not None:
            self._logger.info(
                "user_id=%s | action=desktop_screenshot_query | mode=%s | prompt=%r",
                user_id,
                screenshot_request.mode,
                redact_prompt(text),
            )
            try:
                screenshot = await self._desktop_screenshot_service.capture(screenshot_request)
            except DesktopScreenshotError as exc:
                return format_error_payload(
                    str(exc),
                    assistant_name=self._settings.assistant_name,
                )
            except Exception:
                self._logger.exception(
                    "user_id=%s | action=desktop_screenshot_query_failed",
                    user_id,
                )
                return format_error_payload(
                    "Codi belum berhasil mengambil screenshot desktop saat ini.",
                    assistant_name=self._settings.assistant_name,
                )
            report = None
            if screenshot_request.include_summary:
                try:
                    report = await self._system_activity_inspector.inspect(
                        SystemActivityRequest(
                            include_processes=True,
                            include_logs=False,
                        )
                    )
                except Exception:
                    self._logger.exception(
                        "user_id=%s | action=desktop_screenshot_summary_failed",
                        user_id,
                    )
            return format_desktop_screenshot_payload(
                assistant_name=self._settings.assistant_name,
                screenshot=screenshot,
                report=report,
                include_summary_requested=screenshot_request.include_summary,
            )

        request = match_system_activity_query(text)
        if request is None:
            return None

        self._logger.info(
            "user_id=%s | action=system_activity_query | include_processes=%s | include_logs=%s | prompt=%r",
            user_id,
            str(request.include_processes).lower(),
            str(request.include_logs).lower(),
            redact_prompt(text),
        )
        try:
            report = await self._system_activity_inspector.inspect(request)
        except Exception:
            self._logger.exception(
                "user_id=%s | action=system_activity_query_failed",
                user_id,
            )
            return format_error_payload(
                "Codi belum berhasil membaca aktivitas host saat ini.",
                assistant_name=self._settings.assistant_name,
            )
        return format_system_activity_payload(
            assistant_name=self._settings.assistant_name,
            request=request,
            report=report,
            max_output_length=self._settings.max_output_length,
        )

    async def _execute_approved_safety_action(
        self,
        user_id: int,
        pending: PendingSafetyApproval,
    ) -> MessagePayload:
        if pending.kind == "restart_self":
            return self._build_restart_payload_with_audit(
                user_id,
                policy=classify_restart_policy(),
                approval_id=pending.approval_id,
            )

        if pending.kind == "env_config":
            request = pending.payload
            if not isinstance(request, EnvConfigUpdateRequest):
                return format_error_payload(
                    "Payload approval konfigurasi lokal ini tidak lagi valid.",
                    assistant_name=self._settings.assistant_name,
                )
            policy = classify_env_config_policy(
                request.key,
                f"{request.key}={request.value}",
            )
            return self._apply_env_config_with_audit(
                user_id,
                request,
                policy=policy,
                approval_id=pending.approval_id,
            )

        if pending.kind == "local_shell":
            payload = pending.payload if isinstance(pending.payload, dict) else {}
            request = payload.get("request")
            cwd_value = payload.get("cwd")
            if not isinstance(request, LocalShellRequest) or not cwd_value:
                return format_error_payload(
                    "Payload approval shell ini tidak lagi valid.",
                    assistant_name=self._settings.assistant_name,
                )
            return await self._run_local_shell_with_audit(
                user_id,
                request,
                cwd=Path(str(cwd_value)),
                policy=SafetyPolicy(
                    category=pending.category,
                    required_mode=pending.required_mode,
                    requires_confirmation=True,
                    summary=pending.summary,
                    preview=pending.preview,
                ),
                approval_id=pending.approval_id,
                failure_message="Codi belum berhasil menjalankan aksi host yang tadi disetujui.",
                log_action="approved_local_shell_failed",
            )

        return format_error_payload(
            "Jenis aksi sensitif ini belum punya executor yang cocok.",
            assistant_name=self._settings.assistant_name,
        )

    def _build_restart_payload_with_audit(
        self,
        user_id: int,
        *,
        policy,
        approval_id: str | None = None,
    ) -> MessagePayload:
        self._safety_manager.record_audit_event(
            user_id=user_id,
            event="executed",
            category=policy.category,
            mode=self._safety_manager.get_current_mode(user_id),
            required_mode=policy.required_mode,
            summary=policy.summary,
            preview=policy.preview,
            outcome="scheduled",
            approval_id=approval_id,
        )
        return MessagePayload(
            text=(
                f"<b>{escape(self._settings.assistant_name)}</b>\n\n"
                "Codi akan mulai ulang setelah pesan ini terkirim."
            ),
            parse_mode="HTML",
            post_send_action="restart_self",
        )

    def _apply_env_config_with_audit(
        self,
        user_id: int,
        request: EnvConfigUpdateRequest,
        *,
        policy,
        approval_id: str | None = None,
    ) -> MessagePayload:
        try:
            result = apply_env_config_update(
                request,
                env_path=self._settings.codex_work_dir / ".env",
            )
        except EnvConfigError as exc:
            self._safety_manager.record_audit_event(
                user_id=user_id,
                event="executed",
                category=policy.category,
                mode=self._safety_manager.get_current_mode(user_id),
                required_mode=policy.required_mode,
                summary=policy.summary,
                preview=policy.preview,
                outcome="failed",
                approval_id=approval_id,
            )
            return format_error_payload(
                str(exc),
                assistant_name=self._settings.assistant_name,
            )
        except Exception:
            self._logger.exception(
                "user_id=%s | action=env_config_update_failed",
                user_id,
            )
            self._safety_manager.record_audit_event(
                user_id=user_id,
                event="executed",
                category=policy.category,
                mode=self._safety_manager.get_current_mode(user_id),
                required_mode=policy.required_mode,
                summary=policy.summary,
                preview=policy.preview,
                outcome="failed",
                approval_id=approval_id,
            )
            return format_error_payload(
                "Codi belum berhasil merapikan konfigurasi lokal itu.",
                assistant_name=self._settings.assistant_name,
            )

        self._safety_manager.record_audit_event(
            user_id=user_id,
            event="executed",
            category=policy.category,
            mode=self._safety_manager.get_current_mode(user_id),
            required_mode=policy.required_mode,
            summary=policy.summary,
            preview=policy.preview,
            outcome="success" if result.changed else "noop",
            approval_id=approval_id,
        )
        return format_env_config_update_payload(
            assistant_name=self._settings.assistant_name,
            result=result,
        )

    async def _run_local_shell_with_audit(
        self,
        user_id: int,
        request: LocalShellRequest,
        *,
        cwd: Path,
        policy,
        failure_message: str,
        log_action: str,
        approval_id: str | None = None,
    ) -> MessagePayload:
        try:
            result = await self._local_shell_service.run(request, cwd=cwd)
        except LocalShellError as exc:
            self._safety_manager.record_audit_event(
                user_id=user_id,
                event="executed",
                category=policy.category,
                mode=self._safety_manager.get_current_mode(user_id),
                required_mode=policy.required_mode,
                summary=policy.summary,
                preview=policy.preview,
                outcome="failed",
                approval_id=approval_id,
            )
            return format_error_payload(
                str(exc),
                assistant_name=self._settings.assistant_name,
            )
        except Exception:
            self._logger.exception("user_id=%s | action=%s", user_id, log_action)
            self._safety_manager.record_audit_event(
                user_id=user_id,
                event="executed",
                category=policy.category,
                mode=self._safety_manager.get_current_mode(user_id),
                required_mode=policy.required_mode,
                summary=policy.summary,
                preview=policy.preview,
                outcome="failed",
                approval_id=approval_id,
            )
            return format_error_payload(
                failure_message,
                assistant_name=self._settings.assistant_name,
            )

        self._safety_manager.record_audit_event(
            user_id=user_id,
            event="executed",
            category=policy.category,
            mode=self._safety_manager.get_current_mode(user_id),
            required_mode=policy.required_mode,
            summary=policy.summary,
            preview=policy.preview,
            outcome="success" if result.exit_code == 0 else "failed",
            approval_id=approval_id,
            exit_code=result.exit_code,
        )
        return format_local_shell_payload(
            assistant_name=self._settings.assistant_name,
            result=result,
            max_output_length=self._settings.max_output_length,
        )

    async def _run_write_task_with_approval(
        self,
        prepared: PreparedDispatch,
        *,
        policy,
        on_progress: ProgressCallback | None,
        started: float,
    ) -> MessagePayload:
        if prepared.session is None or prepared.repo_resolution is None:
            return format_error_payload(
                "Task edit ini kehilangan konteks workspace.",
                assistant_name=self._settings.assistant_name,
            )
        if prepared.case_id is None:
            return format_error_payload(
                "Task edit ini kehilangan konteks kerja aktif.",
                assistant_name=self._settings.assistant_name,
            )

        repo_root = prepared.repo_resolution.root
        draft = await self._edit_approval_manager.open_or_reuse_draft(
            user_id=prepared.user_id,
            case_id=prepared.case_id,
            repo_root=repo_root,
        )
        execution_prompt = rewrite_workspace_paths(
            prepared.execution_prompt,
            repo_root,
            draft.draft_root,
        )

        try:
            result = await run_codex_task(
                prompt=execution_prompt,
                role=prepared.role,
                cwd=str(draft.draft_root),
                timeout=self._settings.codex_timeout,
                session_id=f"{prepared.session.session_id}-proposal",
                codex_bin=self._settings.codex_bin,
                model_reasoning_effort=self._settings.codex_reasoning_effort,
                sandbox_mode=policy.sandbox_mode,
                codex_thread_id=draft.codex_thread_id,
                persist_session=True,
                on_progress=on_progress,
            )
            await self._edit_approval_manager.update_draft_thread(
                prepared.case_id,
                result.thread_id,
            )
            duration = time.perf_counter() - started
            self._logger.info(
                "user_id=%s | session=%s | role=%s | repo=%s | exit_code=%s | duration=%.2fs | approval=staged",
                prepared.user_id,
                prepared.session.session_id,
                prepared.role,
                str(repo_root),
                result.exit_code,
                duration,
            )
            if result.exit_code != 0:
                await self._edit_approval_manager.discard_draft_changes(prepared.case_id)
                return format_execution_payload(
                    assistant_name=self._settings.assistant_name,
                    role=prepared.role,
                    session_id=prepared.session.session_id,
                    exit_code=result.exit_code,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    max_output_length=self._settings.max_output_length,
                )

            pending = await self._edit_approval_manager.build_pending(
                case_id=prepared.case_id,
                user_id=prepared.user_id,
                role=prepared.role,
                repo_root=repo_root,
                prompt=prepared.prompt,
                draft_root=draft.draft_root,
                execution_output=result.stdout,
            )
            if pending is None:
                return format_execution_payload(
                    assistant_name=self._settings.assistant_name,
                    role=prepared.role,
                    session_id=prepared.session.session_id,
                    exit_code=result.exit_code,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    max_output_length=self._settings.max_output_length,
                )

            return format_edit_approval_payload(
                assistant_name=self._settings.assistant_name,
                pending=pending,
            )
        except asyncio.TimeoutError:
            await self._edit_approval_manager.discard_draft_changes(prepared.case_id)
            raise
        except Exception:
            await self._edit_approval_manager.discard_draft_changes(prepared.case_id)
            raise
