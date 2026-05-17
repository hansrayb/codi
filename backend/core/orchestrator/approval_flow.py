"""Edit-approval flow mixin for the Codi orchestrator."""

from __future__ import annotations

import asyncio
import re
import shlex
import time
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

from core.edit_approval import PendingApproval, rewrite_workspace_paths
from core.local_shell import (
    LocalShellError,
    LocalShellRequest,
    LocalShellResult,
    Pm2ShellShortcutRequest,
    PostApprovalShellPlan,
    RepoShellShortcutRequest,
    build_shell_request_for_pm2_shortcut,
    build_shell_request_for_repo_shortcut,
    match_post_approval_shell_plan,
    resolve_build_context,
)
from core.safety import (
    classify_pm2_shortcut_policy,
    classify_repo_shortcut_policy,
)
from models.result import MessagePayload
from utils.claude_executor import run_claude_task
from utils.formatter import format_edit_approval_payload, format_execution_payload, format_error_payload

if TYPE_CHECKING:
    from ._models import ProgressCallback
    from .dispatch import PreparedDispatch


class ApprovalFlowMixin:
    """Mixin providing write-task staging and post-approval execution."""

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
            result = await run_claude_task(
                    prompt=execution_prompt,
                    cwd=str(draft.draft_root),
                    timeout=self._settings.claude_timeout,
                    claude_bin=self._settings.claude_bin,
                    claude_model=self._settings.claude_model,
                    claude_session_id=draft.claude_thread_id,
                    mcp_config=self._settings.claude_mcp_config or None,
                    allowed_tools=self._settings.claude_allowed_tools or None,
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
                post_approval_note=self._build_post_approval_note(pending),
            )
        except asyncio.TimeoutError:
            await self._edit_approval_manager.discard_draft_changes(prepared.case_id)
            raise
        except Exception:
            await self._edit_approval_manager.discard_draft_changes(prepared.case_id)
            raise

    async def _run_post_approval_shell_plan(
        self,
        user_id: int,
        pending: PendingApproval,
    ) -> MessagePayload | None:
        relative_paths = tuple(c.relative_path for c in pending.changes)
        build_context = resolve_build_context(
            pending.repo_root,
            relative_paths,
            self._settings.repo_pm2_map,
        )

        if build_context is not None and build_context.mode == "push":
            return await self._run_post_approval_git_push(user_id, pending)

        if build_context is not None and build_context.mode == "local":
            plan = PostApprovalShellPlan(run_build=True, pm2_app_name=build_context.pm2_app_name)
            build_dir = build_context.build_dir
        else:
            plan = match_post_approval_shell_plan(
                pending.prompt,
                important_pm2_apps=self._settings.important_pm2_apps,
            )
            build_dir = pending.repo_root

        if plan is None:
            return None

        try:
            build_request = build_shell_request_for_repo_shortcut(
                RepoShellShortcutRequest(
                    action="node_build",
                    repo_hint="repo ini",
                    original_prompt=pending.prompt,
                ),
                build_dir,
            )
        except LocalShellError as exc:
            return MessagePayload(
                text=(
                    f"<b>{escape(self._settings.assistant_name)} sudah meng-apply perubahan.</b>\n\n"
                    f"Repo: <code>{escape(str(pending.repo_root))}</code>\n"
                    f"Total file: {len(pending.changes)}\n\n"
                    "<b>Post-approval ops:</b>\n"
                    f"Build: gagal disiapkan. {escape(str(exc))}\n"
                    "PM2 restart: dilewati."
                ),
                parse_mode="HTML",
            )
        build_policy = classify_repo_shortcut_policy("node_build", build_request.command)
        try:
            build_result = await self._run_local_shell_result_with_audit(
                user_id,
                build_request,
                cwd=build_dir,
                policy=build_policy,
                approval_id=pending.approval_id,
                log_action="post_approval_build_failed",
            )
        except Exception as exc:
            return MessagePayload(
                text=(
                    f"<b>{escape(self._settings.assistant_name)} sudah meng-apply perubahan.</b>\n\n"
                    f"Repo: <code>{escape(str(pending.repo_root))}</code>\n"
                    f"Total file: {len(pending.changes)}\n\n"
                    "<b>Post-approval ops:</b>\n"
                    f"Build: gagal dijalankan. {escape(str(exc))}\n"
                    "PM2 restart: dilewati."
                ),
                parse_mode="HTML",
            )

        pm2_result: LocalShellResult | None = None
        pm2_error: str | None = None
        if build_result.exit_code == 0:
            if plan.pm2_app_name:
                pm2_request = build_shell_request_for_pm2_shortcut(
                    Pm2ShellShortcutRequest(
                        action="pm2_restart",
                        app_name=plan.pm2_app_name,
                        original_prompt=pending.prompt,
                    )
                )
                pm2_policy = classify_pm2_shortcut_policy("pm2_restart", pm2_request.command)
                try:
                    pm2_result = await self._run_local_shell_result_with_audit(
                        user_id,
                        pm2_request,
                        cwd=self._settings.claude_work_dir,
                        policy=pm2_policy,
                        approval_id=pending.approval_id,
                        log_action="post_approval_pm2_restart_failed",
                    )
                except Exception as exc:
                    pm2_error = f"gagal dijalankan. {exc}"
            else:
                pm2_error = (
                    "Nama aplikasi PM2 belum terbaca dari prompt, jadi restart PM2 saya lewati."
                )

        return self._format_post_approval_shell_result(
            pending=pending,
            build_result=build_result,
            pm2_result=pm2_result,
            pm2_error=pm2_error,
        )

    async def _run_post_approval_git_push(
        self,
        user_id: int,
        pending: PendingApproval,
    ) -> MessagePayload:
        aname = self._settings.assistant_name
        header = (
            f"<b>{escape(aname)} sudah meng-apply perubahan.</b>\n\n"
            f"Repo: <code>{escape(str(pending.repo_root))}</code>\n"
            f"Total file: {len(pending.changes)}\n\n"
            "<b>Post-approval ops (CI/CD flow):</b>\n"
        )
        commit_msg = _build_auto_commit_message(pending.prompt)
        git_request = LocalShellRequest(
            shell="bash",
            command=f"git add -A && git commit -m {shlex.quote(commit_msg)} && git push",
        )
        git_policy = classify_repo_shortcut_policy("git_push", git_request.command)
        try:
            git_result = await self._run_local_shell_result_with_audit(
                user_id,
                git_request,
                cwd=pending.repo_root,
                policy=git_policy,
                approval_id=pending.approval_id,
                log_action="post_approval_git_push_failed",
            )
        except Exception as exc:
            return MessagePayload(
                text=header + f"Git commit & push: gagal dijalankan. {escape(str(exc))}",
                parse_mode="HTML",
            )

        if git_result.exit_code == 0:
            status = "Git commit & push: berhasil — CI/CD pipeline akan jalan otomatis."
        else:
            status = f"Git commit & push: gagal (exit {git_result.exit_code})"

        detail_lines = [
            f"Command: {git_result.command}",
            f"CWD: {git_result.cwd}",
            f"Exit: {git_result.exit_code}",
        ]
        if git_result.stdout.strip():
            detail_lines += ["STDOUT:", git_result.stdout.strip()]
        if git_result.stderr.strip():
            detail_lines += ["STDERR:", git_result.stderr.strip()]
        detail_text = "\n".join(detail_lines)

        if len(detail_text) > self._settings.max_output_length:
            return MessagePayload(
                text=header + status + "\n\nDetail saya kirim sebagai file.",
                parse_mode="HTML",
                attachment_filename=f"{pending.approval_id}-git-push.txt",
                attachment_bytes=detail_text.encode("utf-8"),
            )
        return MessagePayload(
            text=header + status + f"\n\n<b>Detail:</b>\n<pre>{escape(detail_text)}</pre>",
            parse_mode="HTML",
        )

    def _format_post_approval_shell_result(
        self,
        *,
        pending: PendingApproval,
        build_result: LocalShellResult,
        pm2_result: LocalShellResult | None,
        pm2_error: str | None,
    ) -> MessagePayload:
        lines = [
            f"<b>{escape(self._settings.assistant_name)} sudah meng-apply perubahan.</b>",
            "",
            f"Repo: <code>{escape(str(pending.repo_root))}</code>",
            f"Total file: {len(pending.changes)}",
            "",
            "<b>Post-approval ops:</b>",
            (
                "Build: berhasil"
                if build_result.exit_code == 0
                else f"Build: gagal (exit {build_result.exit_code})"
            ),
        ]
        if build_result.exit_code != 0:
            lines.append("PM2 restart: dilewati karena build gagal.")
        elif pm2_error is not None:
            lines.append(f"PM2 restart: {escape(pm2_error)}")
        elif pm2_result is not None:
            lines.append(
                "PM2 restart: berhasil"
                if pm2_result.exit_code == 0
                else f"PM2 restart: gagal (exit {pm2_result.exit_code})"
            )

        detail_text = _build_post_approval_detail_text(build_result, pm2_result, pm2_error)
        if len(detail_text) > self._settings.max_output_length:
            return MessagePayload(
                text="\n".join(lines + ["", "Detail build/restart saya kirim sebagai file."]),
                parse_mode="HTML",
                attachment_filename=f"{pending.approval_id}-post-approval-ops.txt",
                attachment_bytes=detail_text.encode("utf-8"),
            )

        lines.extend(["", "<b>Detail:</b>", f"<pre>{escape(detail_text)}</pre>"])
        return MessagePayload(text="\n".join(lines), parse_mode="HTML")

    def _build_post_approval_note(self, pending: PendingApproval) -> str | None:
        relative_paths = tuple(c.relative_path for c in pending.changes)
        build_context = resolve_build_context(
            pending.repo_root,
            relative_paths,
            self._settings.repo_pm2_map,
        )
        if build_context is not None:
            if build_context.mode == "push":
                return (
                    "Setelah disetujui, Codi akan otomatis git commit + push "
                    "ke remote — CI/CD pipeline akan jalan otomatis."
                )
            if build_context.pm2_app_name:
                return (
                    "Setelah disetujui, Codi akan otomatis build project dan "
                    f"restart PM2 app `{build_context.pm2_app_name}`."
                )
        plan = match_post_approval_shell_plan(
            pending.prompt,
            important_pm2_apps=self._settings.important_pm2_apps,
        )
        if plan is None:
            return None
        if plan.pm2_app_name:
            return (
                "Codi akan menjalankan build project. Jika build berhasil, "
                f"Codi akan restart PM2 app `{plan.pm2_app_name}`."
            )
        return (
            "Codi akan menjalankan build project. Prompt meminta PM2 restart, "
            "tetapi nama app PM2 belum terbaca; restart akan dilewati jika tetap tidak ada target."
        )


def _build_post_approval_detail_text(
    build_result: LocalShellResult,
    pm2_result: LocalShellResult | None,
    pm2_error: str | None,
) -> str:
    sections = [
        _format_shell_result_detail("Build", build_result),
    ]
    if pm2_result is not None:
        sections.append(_format_shell_result_detail("PM2 restart", pm2_result))
    elif pm2_error is not None:
        sections.append(f"PM2 restart\nError: {pm2_error}")
    else:
        sections.append("PM2 restart\nTidak dijalankan.")
    return "\n\n".join(sections).strip()


def _format_shell_result_detail(label: str, result: LocalShellResult) -> str:
    parts = [
        label,
        f"Command: {result.command}",
        f"CWD: {result.cwd}",
        f"Exit: {result.exit_code}",
    ]
    if result.timed_out:
        parts.append("Timed out: yes")
    if result.stdout.strip():
        parts.extend(["STDOUT:", result.stdout.strip()])
    if result.stderr.strip():
        parts.extend(["STDERR:", result.stderr.strip()])
    return "\n".join(parts)


def _build_auto_commit_message(prompt: str) -> str:
    """Build a safe git commit message from a user prompt (max 72 chars)."""
    sanitized = re.sub(r"[^\w\s\-.,:/()]", "", prompt).strip()
    sanitized = re.sub(r"\s+", " ", sanitized)
    prefix = "codi: "
    max_body = 72 - len(prefix)
    if len(sanitized) > max_body:
        sanitized = sanitized[:max_body - 1] + "…"
    return prefix + sanitized if sanitized else "codi: update"
