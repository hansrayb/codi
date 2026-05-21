"""Async subprocess execution helpers for Claude Code CLI tasks."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable

from utils.executor import ClaudeRunResult

ProgressCallback = Callable[[str], Awaitable[None]]


async def run_claude_task(
    prompt: str,
    *,
    cwd: str,
    timeout: int,
    claude_bin: str = "claude",
    claude_model: str = "claude-sonnet-4-6",
    claude_session_id: str | None = None,
    mcp_config: str | None = None,
    allowed_tools: str | None = None,
    on_progress: ProgressCallback | None = None,
) -> ClaudeRunResult:
    """Run Claude Code CLI in non-interactive mode and return the result."""

    args = _build_claude_args(
        prompt=prompt,
        claude_bin=claude_bin,
        claude_model=claude_model,
        claude_session_id=claude_session_id,
        mcp_config=mcp_config,
        allowed_tools=allowed_tools,
    )

    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout_raw, stderr_raw = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise

    stdout_text = _decode(stdout_raw)
    stderr_text = _decode(stderr_raw)
    result_text, session_id = _parse_output(stdout_text)

    return ClaudeRunResult(
        exit_code=process.returncode or 0,
        stdout=result_text or stdout_text.strip(),
        stderr=stderr_text.strip(),
        thread_id=session_id,
    )


def _build_claude_args(
    *,
    prompt: str,
    claude_bin: str,
    claude_model: str,
    claude_session_id: str | None,
    mcp_config: str | None = None,
    allowed_tools: str | None = None,
) -> list[str]:
    args = [claude_bin, "--model", claude_model, "--output-format", "json"]
    if mcp_config:
        args.extend(["--mcp-config", mcp_config])
    if allowed_tools:
        args.extend(["--allowedTools", allowed_tools])
    if claude_session_id:
        args.extend(["--resume", claude_session_id])
    args.extend(["-p", prompt])
    return args


TokenCallback = Callable[[str], Awaitable[None]]


async def run_claude_task_streaming(
    prompt: str,
    *,
    cwd: str,
    timeout: int,
    on_token: TokenCallback,
    claude_bin: str = "claude",
    claude_model: str = "claude-sonnet-4-6",
    claude_session_id: str | None = None,
    mcp_config: str | None = None,
    allowed_tools: str | None = None,
    cancel_event: asyncio.Event | None = None,
) -> ClaudeRunResult:
    """Run Claude CLI in stream-json mode, invoking on_token for each text delta.

    Emits only assistant ``text_delta`` chunks (thinking deltas are skipped).
    Captures the CLI session_id from the ``system:init`` / ``result`` events so
    the caller can persist it for ``--resume`` continuity. Returns the full
    accumulated reply as ``ClaudeRunResult.stdout``.

    If ``cancel_event`` is set mid-stream (client disconnected), the subprocess
    is killed and the partial result returned.
    """

    args = _build_streaming_args(
        prompt=prompt,
        claude_bin=claude_bin,
        claude_model=claude_model,
        claude_session_id=claude_session_id,
        mcp_config=mcp_config,
        allowed_tools=allowed_tools,
    )

    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=4 * 1024 * 1024,  # 4MB — avoids LimitOverrunError on large lines
    )

    text_parts: list[str] = []
    session_holder: dict[str, str | None] = {"value": claude_session_id}
    final_result: dict[str, str | None] = {"value": None}

    async def _pump() -> None:
        assert process.stdout is not None
        while True:
            if cancel_event is not None and cancel_event.is_set():
                return
            try:
                raw_line = await process.stdout.readline()
            except asyncio.LimitOverrunError:
                await process.stdout.read(4 * 1024 * 1024)
                continue
            if not raw_line:
                break
            line = _decode(raw_line).strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            await _handle_stream_event(evt, on_token, text_parts, session_holder, final_result)

    pump_task = asyncio.create_task(_pump())
    cancel_task = (
        asyncio.create_task(cancel_event.wait()) if cancel_event is not None else None
    )

    try:
        if cancel_task is not None:
            done, _pending = await asyncio.wait(
                {pump_task, cancel_task},
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if pump_task not in done:
                # Either cancelled by client or timed out.
                raise _TimeoutOrCancel(cancelled=cancel_task in done)
        else:
            await asyncio.wait_for(pump_task, timeout=timeout)
        await asyncio.wait_for(process.wait(), timeout=5)
    except (asyncio.TimeoutError, _TimeoutOrCancel) as exc:
        cancelled = isinstance(exc, _TimeoutOrCancel) and exc.cancelled
        _kill(process)
        await _safe_wait(process)
        pump_task.cancel()
        await asyncio.gather(pump_task, return_exceptions=True)
        if not cancelled:
            # Real timeout — surface to caller for an error frame.
            raise asyncio.TimeoutError from None
        # Client disconnect: return partial, no raise.
    finally:
        if cancel_task is not None and not cancel_task.done():
            cancel_task.cancel()
            await asyncio.gather(cancel_task, return_exceptions=True)
        _kill(process)

    result_text = final_result["value"] or "".join(text_parts)
    return ClaudeRunResult(
        exit_code=process.returncode or 0,
        stdout=result_text.strip(),
        stderr="",
        thread_id=session_holder["value"],
    )


class _TimeoutOrCancel(Exception):
    """Internal signal distinguishing client-cancel from a real timeout."""

    def __init__(self, *, cancelled: bool) -> None:
        super().__init__()
        self.cancelled = cancelled


def _kill(process: asyncio.subprocess.Process) -> None:
    if process.returncode is None:
        try:
            process.kill()
        except ProcessLookupError:
            pass


async def _safe_wait(process: asyncio.subprocess.Process) -> None:
    try:
        await asyncio.wait_for(process.wait(), timeout=5)
    except asyncio.TimeoutError:
        pass


async def _handle_stream_event(
    evt: dict,
    on_token: TokenCallback,
    text_parts: list[str],
    session_holder: dict[str, str | None],
    final_result: dict[str, str | None],
) -> None:
    etype = evt.get("type")
    sid = evt.get("session_id")
    if sid:
        session_holder["value"] = sid

    if etype == "stream_event":
        inner = evt.get("event") or {}
        if inner.get("type") == "content_block_delta":
            delta = inner.get("delta") or {}
            # Only surface visible answer text; skip thinking_delta / signatures.
            if delta.get("type") == "text_delta":
                piece = delta.get("text") or ""
                if piece:
                    text_parts.append(piece)
                    await on_token(piece)
    elif etype == "result":
        final_result["value"] = str(evt.get("result") or "")


def _build_streaming_args(
    *,
    prompt: str,
    claude_bin: str,
    claude_model: str,
    claude_session_id: str | None,
    mcp_config: str | None = None,
    allowed_tools: str | None = None,
) -> list[str]:
    args = [
        claude_bin,
        "--model",
        claude_model,
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-partial-messages",
    ]
    if mcp_config:
        args.extend(["--mcp-config", mcp_config])
    if allowed_tools:
        args.extend(["--allowedTools", allowed_tools])
    if claude_session_id:
        args.extend(["--resume", claude_session_id])
    args.extend(["-p", prompt])
    return args


def _parse_output(raw: str) -> tuple[str, str | None]:
    """Parse JSON output from Claude Code CLI. Returns (result_text, session_id)."""
    raw = raw.strip()
    if not raw:
        return "", None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw, None
    result = payload.get("result") or ""
    session_id = payload.get("session_id") or None
    return str(result), session_id


def _decode(raw: bytes) -> str:
    if not raw:
        return ""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="replace")
