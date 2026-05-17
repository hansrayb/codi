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
