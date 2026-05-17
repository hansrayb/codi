"""Central dispatch and Orchestrator class for the Codi agent."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace as dataclass_replace
from html import escape
from pathlib import Path

from config import Settings
from core.backend_prefs import BACKEND_LABELS, BackendPrefs
from core.business_data import BusinessDataService
from core.case_manager import CaseManager
from core.desktop_actions import DesktopActionManager, DesktopActionRequest, match_desktop_action
from core.desktop_screenshot import DesktopScreenshotService
from core.device_registry import DeviceRegistryManager
from core.device_tasks import DeviceContextStore, DeviceTaskQueue
from core.edit_approval import EditApprovalError, EditApprovalManager
from core.local_shell import LocalShellService
from core.memory import MemoryStore, build_memory_context
from core.prompts import build_task_prompt
from core.repo_resolver import RepoResolution, RepoResolver, RepoResolverError
from core.repo_watch import RepoWatchManager
from core.role_policy import get_role_policy
from core.router import IntentRouter, RoutingDecision
from core.safety import SafetyManager
from core.self_context import CodiSelfContext
from core.self_maintenance import SelfMaintenanceManager
from core.session_manager import (
    QueueFullError,
    SessionInvalidatedError,
    SessionLease,
    SessionLimitError,
    SessionManager,
)
from core.system_activity import SystemActivityInspector
from models.result import MessagePayload
from models.session import Session
from utils.formatter import format_error_payload
from utils.logger import redact_prompt

from ._helpers import _is_self_modification_action
from ._models import ChatSessionState
from .approval_flow import ApprovalFlowMixin
from .claude_flow import ClaudeFlowMixin
from .device_handler import DeviceHandlerMixin
from .repo_handler import RepoHandlerMixin
from .shell_handler import ShellHandlerMixin

ProgressCallback = Callable[[str], Awaitable[None]]


class OrchestratorUserError(RuntimeError):
    """A user-facing error that can be shown directly in Telegram."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


@dataclass
class PreparedDispatch:
    """Prepared execution metadata reserved before Claude is invoked."""

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


class Orchestrator(
    RepoHandlerMixin,
    DeviceHandlerMixin,
    ShellHandlerMixin,
    ApprovalFlowMixin,
    ClaudeFlowMixin,
):
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
        backend_prefs: BackendPrefs | None = None,
        device_task_queue: DeviceTaskQueue | None = None,
        device_context_store: DeviceContextStore | None = None,
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
        self._backend_prefs = backend_prefs or BackendPrefs(settings.ai_backend)
        self._business_data_service = BusinessDataService(settings)
        self._device_task_queue = device_task_queue
        self._device_context_store = device_context_store
        self._chat_sessions: dict[int, ChatSessionState] = {}
        self._memory = MemoryStore(settings.memory_db_path)
        self._self_context = CodiSelfContext(
            settings=settings,
            session_manager=session_manager,
            device_registry_manager=device_registry_manager,
            project_root=str(self_maintenance_manager.project_root),
        )

    async def prepare_dispatch(self, user_id: int, prompt: str, *, scope: str = "") -> PreparedDispatch:
        """Route the prompt and reserve a session before execution starts."""

        normalized_prompt = prompt.strip()
        if not normalized_prompt:
            raise OrchestratorUserError("Kirim task dalam bentuk pesan teks.")

        if _is_self_modification_action(normalized_prompt, self._settings.assistant_name):
            self_root = self._self_maintenance_manager.project_root
            if self._settings.is_workdir_allowed(self_root):
                self._logger.info(
                    "user_id=%s | action=self_modification_intent | prompt=%r",
                    user_id,
                    redact_prompt(normalized_prompt),
                )
                active_case = await self._case_manager.get_active_case(user_id)
                decision = self._router.route(normalized_prompt, await self._session_manager.get_active_session(user_id))
                if not decision.override_applied or decision.role not in {"builder", "debugger"}:
                    from core.router import RoutingDecision as _RD
                    decision = _RD(role="builder", confidence=0.95, reason="self_modification_intent")
                policy = get_role_policy(decision.role)
                repo_resolution = RepoResolution(
                    root=self_root,
                    label=self_root.name,
                    confidence=1.0,
                    reason="self_reference",
                    explicit=True,
                )
                case, created_case = await self._case_manager.open_or_reuse_case(
                    user_id,
                    self_root,
                    prompt=normalized_prompt,
                    role=decision.role,
                )
                try:
                    lease = await self._session_manager.acquire_session(
                        user_id,
                        decision.role,
                        self_root,
                        prefer_reuse=False,
                        case_id=case.case_id,
                    )
                except SessionLimitError as exc:
                    raise OrchestratorUserError("Semua agent sedang sibuk. Coba lagi sebentar.") from exc
                except QueueFullError as exc:
                    raise OrchestratorUserError("Session terkait sedang penuh. Coba ulang atau /reset.") from exc
                except SessionInvalidatedError as exc:
                    raise OrchestratorUserError("Session sebelumnya berubah saat menunggu. Coba kirim ulang task.") from exc
                session = lease.session
                execution_prompt = build_task_prompt(
                    role=decision.role,
                    user_prompt=normalized_prompt,
                    session_summary=session.summary,
                    assistant_name=self._settings.assistant_name,
                    repo_name=self_root.name,
                    repo_path=str(self_root),
                )
                ack_parts = [
                    f"{self._settings.assistant_name} akan mengerjakan perubahan di repo sendiri.",
                    self._build_case_ack(case.title, created_case),
                    "Setelah selesai, Codi akan menampilkan diff dan meminta persetujuan sebelum apply.",
                ]
                return PreparedDispatch(
                    kind="claude",
                    user_id=user_id,
                    prompt=normalized_prompt,
                    role=decision.role,
                    session=session,
                    lease=lease,
                    decision=decision,
                    ack_text="\n".join(ack_parts),
                    execution_prompt=execution_prompt,
                    case_id=case.case_id,
                    repo_resolution=repo_resolution,
                )

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

        if (
            user_id in self._settings.business_user_ids
            and self._settings.business_allowed_dirs
            and not self._settings.is_business_dir(repo_resolution.root)
        ):
            raise OrchestratorUserError(
                "Kamu hanya bisa mengakses project bisnis yang diizinkan. "
                "Gunakan /pilih-project untuk memilih project."
            )

        decision = self._router.route(normalized_prompt, active_session)
        if scope == "repo":
            _REPO_ROLES = {"builder", "reviewer", "debugger", "general"}
            if decision.role not in _REPO_ROLES:
                decision = dataclass_replace(decision, role="general", reason="scope_restricted")
        policy = get_role_policy(decision.role)
        if (
            policy.allow_write
            and decision.role != "codi"
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
        needs_workspace = policy.allow_write

        case_id: str | None = None
        if needs_workspace:
            case, created_case = await self._case_manager.open_or_reuse_case(
                user_id,
                repo_resolution.root,
                prompt=normalized_prompt,
                role=decision.role,
            )
            case_id = case.case_id

        try:
            lease = await self._session_manager.acquire_session(
                user_id,
                decision.role,
                repo_resolution.root,
                prefer_reuse=prefer_reuse,
                case_id=case_id,
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
        memory_ctx = build_memory_context(
            self._memory, user_id, repo_path=str(repo_resolution.root)
        )
        execution_prompt = build_task_prompt(
            role=decision.role,
            user_prompt=normalized_prompt,
            session_summary=session.summary,
            assistant_name=self._settings.assistant_name,
            repo_name=repo_resolution.label,
            repo_path=str(repo_resolution.root),
            memory_context=memory_ctx,
            bot_context=self._self_context.get_state_block(),
        )
        ack_parts = [self._build_ack_text(decision.role)]
        if needs_workspace:
            ack_parts.append(self._build_case_ack(case.title, created_case))
            ack_parts.append(self._build_repo_ack(repo_resolution))
        if lease.queued_before_acquire:
            ack_parts.append("Task ini sempat masuk antrean sebentar.")
        if decision.role == "general" and decision.confidence < 0.5:
            ack_parts.append("Saya mulai dari jalur umum dulu karena maksud task-nya masih cukup luas.")
        ack_text = "\n".join(ack_parts)

        self._logger.info(
            "user_id=%s | case=%s | session=%s | role=%s | repo=%s | repo_reason=%s | action=dispatch | reuse=%s | confidence=%.2f | prompt=%r",
            user_id,
            case_id,
            session.session_id,
            decision.role,
            str(repo_resolution.root),
            repo_resolution.reason,
            str(not lease.created_session).lower(),
            decision.confidence,
            redact_prompt(normalized_prompt),
        )

        return PreparedDispatch(
            kind="claude",
            user_id=user_id,
            prompt=normalized_prompt,
            role=decision.role,
            session=session,
            lease=lease,
            decision=decision,
            ack_text=ack_text,
            execution_prompt=execution_prompt,
            case_id=case_id,
            repo_resolution=repo_resolution,
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

    async def get_status_snapshot(self, user_id: int) -> dict[str, object]:
        """Return internal session data for the `/status` handler."""

        stats = await self._session_manager.get_stats(user_id)
        case_stats = await self._case_manager.get_stats(user_id)
        watch_stats = await self._repo_watch_manager.get_stats(user_id)
        device_stats = self._device_registry_manager.get_stats()
        active_target_kind = "host"
        active_target_device_id = None
        active_target_device_label = None
        if self._device_context_store is not None:
            active_target = self._device_context_store.get_active_target(user_id)
            active_target_kind = active_target.target_kind
            active_target_device_id = active_target.device_id
            if active_target.device_id:
                record = self._device_registry_manager.resolve_device(active_target.device_id)
                if record is not None:
                    active_target_device_label = record.label
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
            "active_target_kind": active_target_kind,
            "active_target_device_id": active_target_device_id,
            "active_target_device_label": active_target_device_label,
            "safety_mode": self._safety_manager.get_current_mode(user_id),
            "safety_max_mode": self._safety_manager.get_max_mode(user_id),
            "safety_pending": self._safety_manager.get_pending_summary(user_id),
            "audit_log_path": str(self._safety_manager.get_audit_log_path()),
            "ai_backend": self._backend_prefs.get(user_id),
        }

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
