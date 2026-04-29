"""Async subprocess execution helpers for Codex CLI tasks."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import tempfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

ProgressCallback = Callable[[str], Awaitable[None]]


@dataclass(frozen=True)
class CodexRunResult:
    """Normalized output from a Codex CLI execution."""

    exit_code: int
    stdout: str
    stderr: str
    thread_id: str | None = None


async def run_codex_task(
    prompt: str,
    role: str,
    cwd: str,
    timeout: int,
    session_id: str | None = None,
    *,
    codex_bin: str = "codex",
    model_reasoning_effort: str = "medium",
    sandbox_mode: str = "read-only",
    codex_thread_id: str | None = None,
    persist_session: bool = True,
    on_progress: ProgressCallback | None = None,
) -> CodexRunResult:
    """Run Codex in non-interactive mode and return exit code, stdout, and stderr."""

    output_path = _build_temp_output_path(session_id or role)
    args = _build_codex_args(
        prompt=prompt,
        cwd=cwd,
        output_path=output_path,
        codex_bin=codex_bin,
        model_reasoning_effort=model_reasoning_effort,
        sandbox_mode=sandbox_mode,
        codex_thread_id=codex_thread_id,
        persist_session=persist_session,
    )

    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=4 * 1024 * 1024,  # 4MB — prevents LimitOverrunError on large output lines
    )
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    thread_id_holder = {"value": codex_thread_id}

    try:
        stdout_task = asyncio.create_task(
            _read_stdout_stream(
                process.stdout,
                stdout_lines,
                on_progress,
                thread_id_holder,
            )
        )
        stderr_task = asyncio.create_task(_read_stderr_stream(process.stderr, stderr_lines))
        await asyncio.wait_for(process.wait(), timeout)
        await stdout_task
        await stderr_task
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
        raise
    finally:
        output_text = (
            output_path.read_text(encoding="utf-8", errors="replace")
            if output_path.exists()
            else ""
        )
        output_path.unlink(missing_ok=True)

    stdout_text = "\n".join(stdout_lines).strip()
    stderr_text = "\n".join(stderr_lines).strip()
    cleaned_stdout = output_text.strip() or stdout_text.strip()
    return CodexRunResult(
        exit_code=process.returncode or 0,
        stdout=cleaned_stdout,
        stderr=stderr_text.strip(),
        thread_id=thread_id_holder["value"],
    )


def _build_temp_output_path(session_tag: str) -> Path:
    fd, path = tempfile.mkstemp(prefix=f"codex-{session_tag}-", suffix=".txt")
    os.close(fd)
    return Path(path)


def _decode_output(raw: bytes) -> str:
    if not raw:
        return ""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="replace")


async def _read_stdout_stream(
    stream: asyncio.StreamReader | None,
    sink: list[str],
    on_progress: ProgressCallback | None,
    thread_id_holder: dict[str, str | None],
) -> None:
    if stream is None:
        return

    while True:
        try:
            raw_line = await stream.readline()
        except asyncio.LimitOverrunError:
            # Line exceeds buffer limit — drain and skip it
            await stream.read(4 * 1024 * 1024)
            continue
        if not raw_line:
            break
        line = _decode_output(raw_line).strip()
        if not line:
            continue
        sink.append(line)
        thread_id = _extract_thread_id(line)
        if thread_id is not None:
            thread_id_holder["value"] = thread_id
        progress_text = _parse_progress_line(line)
        if progress_text and on_progress is not None:
            await on_progress(progress_text)


async def _read_stderr_stream(
    stream: asyncio.StreamReader | None,
    sink: list[str],
) -> None:
    if stream is None:
        return

    while True:
        try:
            raw_line = await stream.readline()
        except asyncio.LimitOverrunError:
            await stream.read(4 * 1024 * 1024)
            continue
        if not raw_line:
            break
        line = _decode_output(raw_line).strip()
        if line:
            sink.append(line)


def _parse_progress_line(line: str) -> str | None:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None

    item = payload.get("item")
    event_type = payload.get("type")
    if not isinstance(item, dict):
        return None

    item_type = item.get("type")
    if item_type != "command_execution":
        return None

    command = item.get("command")
    if not isinstance(command, str):
        return None
    aggregated_output = item.get("aggregated_output")
    output_text = aggregated_output if isinstance(aggregated_output, str) else ""
    return _humanize_command_event(command, event_type, output_text)


def _extract_thread_id(line: str) -> str | None:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None
    if payload.get("type") != "thread.started":
        return None
    thread_id = payload.get("thread_id")
    if isinstance(thread_id, str) and thread_id.strip():
        return thread_id
    return None


def _build_codex_args(
    *,
    prompt: str,
    cwd: str,
    output_path: Path,
    codex_bin: str,
    model_reasoning_effort: str,
    sandbox_mode: str,
    codex_thread_id: str | None,
    persist_session: bool,
) -> list[str]:
    args = [
        codex_bin,
        "-c",
        f'model_reasoning_effort="{model_reasoning_effort}"',
        "-a",
        "never",
        "exec",
    ]
    if codex_thread_id:
        args.extend(
            [
                "resume",
                "--json",
                "--skip-git-repo-check",
                "--output-last-message",
                str(output_path),
                codex_thread_id,
                prompt,
            ]
        )
        return args

    args.extend(
        [
            "--json",
            "--skip-git-repo-check",
        ]
    )
    if not persist_session:
        args.append("--ephemeral")
    args.extend(
        [
            "--color",
            "never",
            "--sandbox",
            sandbox_mode,
            "--cd",
            cwd,
            "--output-last-message",
            str(output_path),
            prompt,
        ]
    )
    return args


def _humanize_command(command: str) -> str:
    cleaned = re.sub(r"^/bin/bash -lc\s+", "", command).strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        cleaned = cleaned[1:-1]
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return _shorten(cleaned, 140)


def _shorten(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."


def _humanize_command_event(command: str, event_type: str, output_text: str) -> str | None:
    command_text = _humanize_command(command)
    if not command_text:
        return None

    try:
        parts = shlex.split(command_text)
    except ValueError:
        parts = command_text.split()

    if not parts:
        return None

    if parts[0] == "find" and "-name" in parts:
        target = _extract_after_flag(parts, "-name") or "repo target"
        if event_type == "item.started":
            return f"Mencari lokasi repo {target}."
        repo_path = _first_nonempty_line(output_text)
        if repo_path:
            return f"Repo ditemukan di {repo_path}."
        return f"Pencarian repo {target} selesai."

    if parts[0] == "git" and "status" in parts and "--short" in parts and "--branch" in parts:
        if event_type == "item.started":
            return "Mengecek status git repo."
        branch_line = _first_nonempty_line(output_text)
        if branch_line and branch_line.startswith("## "):
            return f"Status git: {branch_line[3:]}."
        return "Status git repo sudah dicek."

    if parts[0] == "rg" and "--files" in parts:
        if event_type == "item.started":
            return "Mencari file penting proyek."
        match_count = len([line for line in output_text.splitlines() if line.strip()])
        if match_count:
            return f"File penting proyek ditemukan, total sekitar {match_count} file."
        return "Pencarian file penting proyek selesai."

    if parts[0] == "rg" and "-n" in parts:
        query = _extract_rg_pattern(parts)
        if event_type == "item.started":
            return f"Mencari referensi terkait {query}."
        return f"Referensi terkait {query} sudah ditemukan."

    if parts[0] in {"sed", "cat", "head", "tail"}:
        target_path = _extract_target_path(parts)
        if not target_path:
            return None
        file_label = _format_path_label(target_path)
        if event_type == "item.started":
            return f"Membaca {file_label}."
        return f"Selesai membaca {file_label}."

    if parts[0] == "ls" and "-la" in parts:
        target_path = _extract_target_path(parts)
        if target_path in {"/", "/home"}:
            return None
        if target_path:
            label = _format_path_label(target_path)
            if event_type == "item.started":
                return f"Melihat struktur folder {label}."
            return f"Struktur folder {label} sudah dicek."
        return None

    if event_type == "item.started":
        return f"Menjalankan pengecekan: {command_text}."

    summary = _summarize_command_output(output_text)
    if summary:
        return f"Selesai: {summary}"
    return f"Selesai menjalankan pengecekan: {command_text}."


def _extract_after_flag(parts: list[str], flag: str) -> str | None:
    try:
        index = parts.index(flag)
    except ValueError:
        return None
    if index + 1 >= len(parts):
        return None
    return parts[index + 1].strip("'\"")


def _extract_target_path(parts: list[str]) -> str | None:
    for token in reversed(parts):
        if token.startswith("/"):
            return token
    return None


def _extract_rg_pattern(parts: list[str]) -> str:
    for token in parts[1:]:
        if token in {"-n", "--files"}:
            continue
        if token.startswith("-"):
            continue
        if token.startswith("/"):
            continue
        cleaned = token.strip("'\"")
        if cleaned:
            return _shorten(cleaned, 60)
    return "topik yang diminta"


def _format_path_label(path: str) -> str:
    path_obj = Path(path)
    name = path_obj.name or path
    parent = path_obj.parent.name
    if parent and parent != "/":
        return f"{name} di {parent}"
    return name


def _first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _summarize_command_output(text: str) -> str:
    first_line = _first_nonempty_line(text)
    if not first_line:
        return ""
    if first_line.startswith(("import ", "export ", "const ", "final ", "class ", "function ")):
        return ""
    if first_line.startswith(("## ", "?? ", "M ", "A ", "D ")):
        return first_line
    if first_line.startswith("/"):
        return _shorten(first_line, 120)
    if len(first_line) > 120:
        return _shorten(first_line, 120)
    return first_line
