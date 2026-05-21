"""Claude CLI invocation mixin for the Codi orchestrator."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.memory import build_memory_context
from core.prompts import build_chat_prompt
from core.role_policy import get_role_policy
from models.result import MessagePayload
from utils.claude_executor import run_claude_task, run_claude_task_streaming
from utils.formatter import format_error_payload, format_execution_payload

from ._models import ChatSessionState

if TYPE_CHECKING:
    from .dispatch import PreparedDispatch

ProgressCallback = Callable[[str], Awaitable[None]]


class ClaudeFlowMixin:
    """Mixin providing Claude task execution and /chat mode."""

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

        if prepared.user_id in self._settings.business_user_ids and policy.allow_write:
            return format_error_payload(
                "Role business hanya bisa membaca data. Aksi edit/tulis tidak diizinkan.",
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
            _fast_roles = {"general", "ops"}
            _model = (
                self._settings.claude_model_fast
                if prepared.role in _fast_roles
                else self._settings.claude_model
            )
            result = await run_claude_task(
                    prompt=prepared.execution_prompt,
                    cwd=prepared.session.cwd,
                    timeout=self._settings.claude_timeout,
                    claude_bin=self._settings.claude_bin,
                    claude_model=_model,
                    claude_session_id=prepared.session.claude_session_id,
                    mcp_config=self._settings.claude_mcp_config or None,
                    allowed_tools=self._settings.claude_allowed_tools or None,
                    on_progress=on_progress,
                )
            prepared.session.claude_session_id = result.thread_id
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
                "user_id=%s | session=%s | role=%s | action=claude_missing",
                prepared.user_id,
                prepared.session.session_id,
                prepared.role,
            )
            return format_error_payload(
                "Claude CLI tidak ditemukan di sistem.",
                assistant_name=self._settings.assistant_name,
            )
        except asyncio.TimeoutError:
            self._logger.warning(
                "user_id=%s | session=%s | role=%s | action=timeout | timeout=%ss",
                prepared.user_id,
                prepared.session.session_id,
                prepared.role,
                self._settings.claude_timeout,
            )
            return format_error_payload(
                (
                    f"{self._settings.assistant_name} belum selesai dalam "
                    f"{self._settings.claude_timeout} detik. "
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
            if summary_update and prepared.repo_resolution is not None:
                self._memory.save_session_summary(
                    user_id=prepared.user_id,
                    repo_path=str(prepared.repo_resolution.root),
                    role=prepared.role,
                    summary=summary_update,
                )
            if prepared.case_id is not None:
                await self._case_manager.update_case(
                    prepared.case_id,
                    role=prepared.role,
                    prompt=prepared.prompt,
                )

    async def run_chat(
        self,
        user_id: int,
        text: str,
        on_progress: ProgressCallback | None = None,
    ) -> MessagePayload:
        """Run a read-only backend chat turn isolated from task sessions."""
        from html import escape

        normalized_text = text.strip()
        if not normalized_text:
            return MessagePayload(
                text=(
                    f"<b>{escape(self._settings.assistant_name)} mode chat.</b>\n\n"
                    "Kirim ide setelah command, contoh:\n"
                    "<code>/chat menurutmu alur onboarding ini sebaiknya dibuat bagaimana?</code>\n\n"
                    "Mode ini hanya untuk ngobrol ide. Untuk eksekusi task, kirim pesan biasa."
                ),
                parse_mode="HTML",
            )

        state = self._chat_sessions.setdefault(user_id, ChatSessionState())
        if state.lock.locked():
            return format_error_payload(
                "Obrolan /chat sebelumnya masih diproses. Tunggu balasan itu selesai dulu.",
                assistant_name=self._settings.assistant_name,
            )

        async with state.lock:
            started = time.perf_counter()
            execution_prompt = build_chat_prompt(
                user_prompt=normalized_text,
                session_summary=state.summary,
                assistant_name=self._settings.assistant_name,
                memory_context=build_memory_context(self._memory, user_id),
            )
            try:
                result = await run_claude_task(
                        prompt=execution_prompt,
                        cwd=str(self._settings.claude_work_dir),
                        timeout=self._settings.claude_timeout,
                        claude_bin=self._settings.claude_bin,
                        claude_model=self._settings.claude_model_fast,
                        claude_session_id=state.claude_session_id,
                        mcp_config=self._settings.claude_mcp_config or None,
                        allowed_tools=self._settings.claude_allowed_tools or None,
                        on_progress=on_progress,
                    )
                state.claude_session_id = result.thread_id
                duration = time.perf_counter() - started
                state.summary = self._summarize_session(state.summary, normalized_text)
                self._logger.info(
                    "user_id=%s | action=chat | model=%s | exit_code=%s | duration=%.2fs",
                    user_id,
                    self._settings.claude_model_fast,
                    result.exit_code,
                    duration,
                )
                return format_execution_payload(
                    assistant_name=self._settings.assistant_name,
                    role="chat",
                    session_id=f"chat-{user_id}",
                    exit_code=result.exit_code,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    max_output_length=self._settings.max_output_length,
                )
            except FileNotFoundError:
                self._logger.exception("user_id=%s | action=chat_backend_missing", user_id)
                return format_error_payload(
                    "Backend AI tidak ditemukan di sistem.",
                    assistant_name=self._settings.assistant_name,
                )
            except asyncio.TimeoutError:
                self._logger.warning(
                    "user_id=%s | action=chat_timeout | timeout=%ss",
                    user_id,
                    self._settings.claude_timeout,
                )
                return format_error_payload(
                    (
                        f"Mode /chat belum selesai dalam {self._settings.claude_timeout} detik. "
                        "Coba kirim versi yang lebih pendek."
                    ),
                    assistant_name=self._settings.assistant_name,
                )
            except Exception:
                self._logger.exception("user_id=%s | action=chat_unexpected_error", user_id)
                return format_error_payload(
                    "Terjadi kesalahan internal saat memproses /chat.",
                    assistant_name=self._settings.assistant_name,
                )

    async def run_chat_streaming(
        self,
        *,
        message: str,
        user_id: int,
        on_token: Callable[[str], Awaitable[None]],
        claude_session_id: str | None,
        cancel_event=None,
    ) -> tuple[str, str | None]:
        """Stream a read-only dashboard chat turn token-by-token.

        Isolated from Telegram /chat: history continuity is driven entirely by
        ``claude_session_id`` (dashboard session_id -> CLI thread mapping lives
        in the caller's CodiSessionStore, not in self._chat_sessions).

        Returns (full_reply_text, new_claude_session_id). Raises on timeout /
        CLI-missing so the caller can emit the right SSE error frame.
        """
        from html import escape  # noqa: F401 — parity with run_chat import style

        execution_prompt = build_chat_prompt(
            user_prompt=message.strip(),
            session_summary="",
            assistant_name=self._settings.assistant_name,
            memory_context=build_memory_context(self._memory, user_id),
        )
        result = await run_claude_task_streaming(
            prompt=execution_prompt,
            cwd=str(self._settings.claude_work_dir),
            timeout=self._settings.claude_timeout,
            on_token=on_token,
            claude_bin=self._settings.claude_bin,
            claude_model=self._settings.claude_model_fast,
            claude_session_id=claude_session_id,
            mcp_config=self._settings.claude_mcp_config or None,
            allowed_tools=self._settings.claude_allowed_tools or None,
            cancel_event=cancel_event,
        )
        return result.stdout, result.thread_id
