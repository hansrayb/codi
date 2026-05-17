"""Shell, env-config, and system-activity handler mixin for the Codi orchestrator."""

from __future__ import annotations

from html import escape
from pathlib import Path

from core.backend_prefs import BACKEND_LABELS, is_backend_query, match_backend_switch
from core.desktop_actions import DesktopActionError
from core.desktop_screenshot import DesktopScreenshotError, match_desktop_screenshot_query
from core.edit_approval import EditApprovalError
from core.env_config import (
    EnvConfigError,
    EnvConfigUpdateRequest,
    apply_env_config_update,
    match_env_config_update_query,
)
from core.local_shell import (
    LocalShellError,
    LocalShellRequest,
    LocalShellResult,
    build_shell_request_for_pm2_shortcut,
    build_shell_request_for_repo_shortcut,
    build_shell_request_for_service_shortcut,
    match_local_shell_query,
    match_pm2_shortcut,
    match_repo_shell_shortcut,
    match_restart_self_query,
    match_system_service_shortcut,
)
from core.repo_context import extract_repo_context_selection, is_repo_context_status_query
from core.repo_resolver import RepoResolverError
from core.safety import (
    PendingSafetyApproval,
    SafetyPolicy,
    classify_env_config_policy,
    classify_pm2_shortcut_policy,
    classify_repo_shortcut_policy,
    classify_restart_policy,
    classify_service_shortcut_policy,
    classify_shell_policy,
)
from core.system_activity import SystemActivityRequest, match_system_activity_query
from models.result import MessagePayload
from utils.formatter import (
    format_desktop_screenshot_payload,
    format_edit_approval_result,
    format_env_config_update_payload,
    format_error_payload,
    format_local_shell_payload,
    format_self_update_result,
    format_system_activity_payload,
)
from utils.logger import redact_prompt

from ._helpers import _is_self_capability_question, _is_self_modification_action


class ShellHandlerMixin:
    """Mixin providing shell, desktop, env-config, and system-activity handling."""

    async def _try_handle_business_data_query(
        self,
        user_id: int,
        text: str,
    ) -> MessagePayload | None:
        request = self._business_data_service.match(text)
        if request is None:
            return None

        active_case = await self._case_manager.get_active_case(user_id)
        active_session = await self._session_manager.get_active_session(user_id)
        try:
            resolution = self._repo_resolver.resolve(text, active_session, active_case)
        except RepoResolverError as exc:
            return format_error_payload(
                str(exc),
                assistant_name=self._settings.assistant_name,
            )

        if self._is_business_user(user_id) and not self._settings.is_business_dir(resolution.root):
            return format_error_payload(
                "Query bisnis hanya bisa membaca project dari BUSINESS_ALLOWED_DIRS. Gunakan /pilih_project untuk memilih project bisnis.",
                assistant_name=self._settings.assistant_name,
            )

        self._logger.info(
            "user_id=%s | action=business_data_query | kind=%s | repo=%s | prompt=%r",
            user_id,
            request.kind,
            str(resolution.root),
            redact_prompt(text),
        )
        return self._business_data_service.handle(
            request,
            resolution.root,
            assistant_name=self._settings.assistant_name,
        )

    def _is_business_user(self, user_id: int) -> bool:
        return user_id in getattr(self._settings, "business_user_ids", ())

    async def _run_desktop_action(self, prepared) -> MessagePayload:
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
                    post_apply_payload = await self._run_post_approval_shell_plan(
                        user_id,
                        pending,
                    )
                    if post_apply_payload is not None:
                        return post_apply_payload
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

        if _is_self_modification_action(text, self._settings.assistant_name):
            return None

        business_payload = await self._try_handle_business_data_query(user_id, text)
        if business_payload is not None:
            return business_payload

        if _is_self_capability_question(text, self._settings.assistant_name):
            self_root = self._self_maintenance_manager.project_root
            name = escape(self._settings.assistant_name)
            return MessagePayload(
                text=(
                    f"<b>{name} bisa memodifikasi dirinya sendiri!</b>\n\n"
                    f"Infrastruktur sudah siap:\n"
                    f"• AI akan membuat perubahan di draft dulu\n"
                    f"• {name} menampilkan diff dan meminta persetujuanmu\n"
                    f"• Setelah kamu setuju, {name} apply perubahan, jalankan test, lalu restart otomatis\n\n"
                    f"<b>Cara pakainya:</b>\n"
                    f"Cukup kirim perintah langsung, contoh:\n"
                    f"<code>tambah fitur /ping ke kamu</code>\n"
                    f"<code>perbaiki help text kamu</code>\n"
                    f"<code>tambahkan command /version ke codi</code>\n"
                    f"<code>ubah claude timeout jadi 900</code>\n\n"
                    f"Repo: <code>{escape(str(self_root))}</code>"
                ),
                parse_mode="HTML",
            )

        switch_target = match_backend_switch(text)
        if switch_target is not None:
            self._backend_prefs.set(user_id, switch_target)
            label = BACKEND_LABELS[switch_target]
            self._logger.info(
                "user_id=%s | action=backend_switch | backend=%s",
                user_id,
                switch_target,
            )
            return MessagePayload(
                text=(
                    f"<b>{escape(self._settings.assistant_name)}</b>\n\n"
                    f"Backend AI sekarang: <b>{label}</b>.\n"
                    "Task berikutnya akan diproses menggunakan backend ini."
                ),
                parse_mode="HTML",
            )

        if is_backend_query(text):
            current = self._backend_prefs.get(user_id)
            label = BACKEND_LABELS.get(current, current)
            return MessagePayload(
                text=(
                    f"<b>{escape(self._settings.assistant_name)}</b>\n\n"
                    f"Backend AI aktif: <b>{label}</b>.\n\n"
                    "Backend AI: Claude Code CLI."
                ),
                parse_mode="HTML",
            )

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
            if self._is_business_user(user_id) and not self._settings.is_business_dir(resolution.root):
                return format_error_payload(
                    "Konteks aktif kamu bukan project bisnis yang diizinkan. Gunakan /pilih_project untuk memilih project bisnis.",
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
            if self._is_business_user(user_id) and not self._settings.is_business_dir(resolution.root):
                return format_error_payload(
                    "Role business hanya bisa memilih project dari BUSINESS_ALLOWED_DIRS.",
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

        if self._is_business_user(user_id):
            return None

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
                else self._settings.claude_work_dir
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
                    "cwd": str(self._settings.claude_work_dir),
                },
                policy=policy,
            )
            if not gate.allowed:
                return gate.payload
            return await self._run_local_shell_with_audit(
                user_id,
                shell_request,
                cwd=self._settings.claude_work_dir,
                policy=policy,
                failure_message="Codi belum berhasil menjalankan shortcut service itu.",
                log_action="service_shell_shortcut_failed",
            )

        pm2_shortcut = match_pm2_shortcut(text)
        if pm2_shortcut is not None:
            self._logger.info(
                "user_id=%s | action=pm2_shell_shortcut | shortcut=%s | prompt=%r",
                user_id,
                pm2_shortcut.action,
                redact_prompt(text),
            )
            try:
                shell_request = build_shell_request_for_pm2_shortcut(pm2_shortcut)
            except LocalShellError as exc:
                return format_error_payload(
                    str(exc),
                    assistant_name=self._settings.assistant_name,
                )
            policy = classify_pm2_shortcut_policy(
                pm2_shortcut.action,
                shell_request.command,
            )
            gate = self._safety_manager.evaluate_action(
                user_id=user_id,
                kind="local_shell",
                payload={
                    "request": shell_request,
                    "cwd": str(self._settings.claude_work_dir),
                },
                policy=policy,
            )
            if not gate.allowed:
                return gate.payload
            return await self._run_local_shell_with_audit(
                user_id,
                shell_request,
                cwd=self._settings.claude_work_dir,
                policy=policy,
                failure_message="Codi belum berhasil menjalankan shortcut PM2 itu.",
                log_action="pm2_shell_shortcut_failed",
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
                env_path=self._settings.claude_work_dir / ".env",
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

    async def _run_local_shell_result_with_audit(
        self,
        user_id: int,
        request: LocalShellRequest,
        *,
        cwd: Path,
        policy,
        log_action: str,
        approval_id: str | None = None,
    ) -> LocalShellResult:
        try:
            result = await self._local_shell_service.run(request, cwd=cwd)
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
            raise

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
        return result
