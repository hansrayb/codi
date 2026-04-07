"""Host observability helpers for running apps, processes, and recent logs."""

from __future__ import annotations

import asyncio
import getpass
import shutil
import subprocess
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import psutil

from core.desktop_actions import DesktopActionManager, TrackedDesktopProcess

PROCESS_QUERY_HINTS = (
    "sedang menjalankan",
    "sedang berjalan",
    "yang berjalan",
    "yang jalan",
    "running app",
    "running apps",
    "running process",
    "running processes",
    "aplikasi aktif",
    "proses aktif",
    "aktivitas laptop",
    "aktivitas komputer",
    "aktivitas pc",
    "aplikasi desktop",
    "background process",
    "background app",
)
PROCESS_NOUN_HINTS = (
    "aplikasi apa",
    "app apa",
    "program apa",
    "proses apa",
    "process apa",
)
LOG_QUERY_HINTS = (
    "log",
    "journal",
    "stderr",
    "stdout",
    "catatan runtime",
)
HOST_CONTEXT_HINTS = (
    "codi",
    "laptop",
    "komputer",
    "pc",
    "mesin",
    "host",
    "desktop ini",
    "bot ini",
    "runtime",
    "systemd",
)
DETAIL_HINTS = (
    "detail",
    "rinci",
    "lengkap",
    "lebih jelas",
    "lebih detail",
)
DESKTOP_HELPER_NAMES = {
    "chrome_crashpad_handler",
    "code-tunnel",
    "dbus-daemon",
    "fcitx5",
    "gsd-media-keys",
    "gvfsd",
    "ibus-daemon",
    "isolated web co",
    "pipewire",
    "privileged cont",
    "socket process",
    "web content",
    "wireplumber",
    "xdg-desktop-portal",
    "xdg-document-portal",
}
DESKTOP_HELPER_FLAGS = (
    "-contentproc",
    "--type=broker",
    "--type=crashpad-handler",
    "--type=gpu-process",
    "--type=renderer",
    "--type=utility",
    "--gapplication-service",
)
LOW_SIGNAL_BACKGROUND_NAMES = {
    "kworker",
    "kthreadd",
    "migration",
    "rcu_gp",
    "rcu_par_gp",
    "systemd",
    "systemd-journald",
}


@dataclass(frozen=True, slots=True)
class SystemActivityRequest:
    """A parsed request for local system activity details."""

    include_processes: bool
    include_logs: bool
    detail_hint: bool = False


@dataclass(frozen=True, slots=True)
class ProcessGroupSummary:
    """A grouped view of related running processes."""

    label: str
    process_count: int
    total_memory_bytes: int
    oldest_create_time: float
    sample_pid: int
    status_summary: str
    sample_command: str
    usernames: tuple[str, ...]
    tracked_by_codi: bool = False


@dataclass(frozen=True, slots=True)
class LogSnapshot:
    """A recent log excerpt from the configured runtime source."""

    source: str
    lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SystemActivityReport:
    """A point-in-time host activity snapshot."""

    captured_at: datetime
    current_user: str
    cpu_percent: float
    memory_used_bytes: int
    memory_total_bytes: int
    memory_percent: float
    swap_percent: float
    host_uptime_seconds: int
    desktop_apps: tuple[ProcessGroupSummary, ...]
    background_apps: tuple[ProcessGroupSummary, ...]
    logs: LogSnapshot | None = None
    notes: tuple[str, ...] = ()


class SystemActivityInspector:
    """Inspect the local host for running apps, background processes, and logs."""

    def __init__(
        self,
        *,
        log_file: str | None = None,
        journal_unit: str = "codex-agent.service",
        desktop_action_manager: DesktopActionManager | None = None,
        process_limit: int = 5,
        log_lines: int = 12,
    ) -> None:
        self._log_file = log_file
        self._journal_unit = journal_unit
        self._desktop_action_manager = desktop_action_manager
        self._process_limit = process_limit
        self._log_lines = log_lines

    async def inspect(self, request: SystemActivityRequest) -> SystemActivityReport:
        """Collect a host activity snapshot for a direct user query."""

        tracked_processes: tuple[TrackedDesktopProcess, ...] = ()
        if self._desktop_action_manager is not None:
            tracked_processes = await self._desktop_action_manager.get_tracked_processes()
        return await asyncio.to_thread(
            self._inspect_sync,
            request,
            tracked_processes,
        )

    def _inspect_sync(
        self,
        request: SystemActivityRequest,
        tracked_processes: tuple[TrackedDesktopProcess, ...],
    ) -> SystemActivityReport:
        current_user = _current_username()
        notes: list[str] = []
        desktop_apps: tuple[ProcessGroupSummary, ...] = ()
        background_apps: tuple[ProcessGroupSummary, ...] = ()

        if request.include_processes:
            desktop_apps, background_apps = self._collect_process_groups(
                current_user=current_user,
                tracked_processes=tracked_processes,
                limit=self._process_limit + (2 if request.detail_hint else 0),
            )
            if not desktop_apps:
                notes.append("Tidak ada aplikasi desktop menonjol yang terdeteksi untuk user saat ini.")
            if not background_apps:
                notes.append("Tidak ada background process menonjol yang terdeteksi.")

        logs = None
        if request.include_logs:
            logs = self._read_logs(limit=self._log_lines + (6 if request.detail_hint else 0))
            if logs is None:
                notes.append(
                    "Log Codi belum tersedia dari file maupun systemd journal di host ini."
                )

        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        cpu_percent = psutil.cpu_percent(interval=0.15)
        host_uptime_seconds = max(0, int(datetime.now(timezone.utc).timestamp() - psutil.boot_time()))

        return SystemActivityReport(
            captured_at=datetime.now(timezone.utc),
            current_user=current_user,
            cpu_percent=cpu_percent,
            memory_used_bytes=int(memory.used),
            memory_total_bytes=int(memory.total),
            memory_percent=float(memory.percent),
            swap_percent=float(swap.percent),
            host_uptime_seconds=host_uptime_seconds,
            desktop_apps=desktop_apps,
            background_apps=background_apps,
            logs=logs,
            notes=tuple(notes),
        )

    def _collect_process_groups(
        self,
        *,
        current_user: str,
        tracked_processes: tuple[TrackedDesktopProcess, ...],
        limit: int,
    ) -> tuple[tuple[ProcessGroupSummary, ...], tuple[ProcessGroupSummary, ...]]:
        tracked_by_pid = {
            tracked.process_group: tracked.label
            for tracked in tracked_processes
        }
        desktop_groups: dict[str, dict[str, object]] = {}
        background_groups: dict[str, dict[str, object]] = {}

        for process in psutil.process_iter(
            attrs=[
                "cmdline",
                "create_time",
                "memory_info",
                "name",
                "pid",
                "status",
                "terminal",
                "username",
            ]
        ):
            try:
                info = process.info
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

            pid = _coerce_int(info.get("pid"))
            if pid <= 0:
                continue

            name = _safe_text(info.get("name")) or _derive_name_from_cmdline(info.get("cmdline"))
            if not name:
                continue

            username = _safe_text(info.get("username")) or "unknown"
            command = _stringify_command(info.get("cmdline"))
            status = _safe_text(info.get("status")) or "unknown"
            terminal = _safe_text(info.get("terminal"))
            memory_info = info.get("memory_info")
            memory_bytes = getattr(memory_info, "rss", 0) if memory_info is not None else 0
            create_time = float(info.get("create_time") or 0.0)
            tracked_label = tracked_by_pid.get(pid)

            if _should_skip_process(name, command, username):
                continue

            is_desktop = _looks_like_desktop_process(
                name=name,
                command=command,
                username=username,
                current_user=current_user,
                terminal=terminal,
                tracked_label=tracked_label,
            )
            label = tracked_label or _humanize_process_name(name)
            bucket = desktop_groups if is_desktop else background_groups
            bucket_key = f"{label.lower()}::{username if not is_desktop else current_user}"
            accumulator = bucket.setdefault(
                bucket_key,
                {
                    "label": label,
                    "process_count": 0,
                    "total_memory_bytes": 0,
                    "oldest_create_time": create_time or float("inf"),
                    "sample_pid": pid,
                    "sample_command": command,
                    "statuses": Counter(),
                    "usernames": set(),
                    "tracked_by_codi": bool(tracked_label),
                },
            )
            accumulator["process_count"] = int(accumulator["process_count"]) + 1
            accumulator["total_memory_bytes"] = int(accumulator["total_memory_bytes"]) + int(memory_bytes)
            accumulator["oldest_create_time"] = min(
                float(accumulator["oldest_create_time"]),
                create_time or float("inf"),
            )
            if command and (
                not accumulator["sample_command"]
                or len(command) > len(str(accumulator["sample_command"]))
            ):
                accumulator["sample_command"] = command
                accumulator["sample_pid"] = pid
            accumulator["statuses"][status] += 1
            accumulator["usernames"].add(username)
            accumulator["tracked_by_codi"] = bool(accumulator["tracked_by_codi"] or tracked_label)

        desktop_summaries = tuple(
            sorted(
                (
                    _finalize_process_group(accumulator)
                    for accumulator in desktop_groups.values()
                ),
                key=lambda item: (
                    not item.tracked_by_codi,
                    -item.total_memory_bytes,
                    -item.process_count,
                    item.label.lower(),
                ),
            )[:limit]
        )
        background_summaries = tuple(
            sorted(
                (
                    _finalize_process_group(accumulator)
                    for accumulator in background_groups.values()
                ),
                key=lambda item: (
                    -item.total_memory_bytes,
                    -item.process_count,
                    item.label.lower(),
                ),
            )[:limit]
        )
        return desktop_summaries, background_summaries

    def _read_logs(self, limit: int) -> LogSnapshot | None:
        log_file_snapshot = self._read_log_file(limit)
        if log_file_snapshot is not None:
            return log_file_snapshot
        return self._read_systemd_journal(limit)

    def _read_log_file(self, limit: int) -> LogSnapshot | None:
        if not self._log_file:
            return None
        path = Path(self._log_file).expanduser()
        if not path.exists() or not path.is_file():
            return None

        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                lines = tuple(line.rstrip() for line in deque(handle, maxlen=limit) if line.strip())
        except OSError:
            return None
        if not lines:
            return None
        return LogSnapshot(source=f"file:{path}", lines=lines)

    def _read_systemd_journal(self, limit: int) -> LogSnapshot | None:
        journalctl_bin = shutil.which("journalctl")
        if journalctl_bin is None or not self._journal_unit:
            return None

        try:
            result = subprocess.run(
                [
                    journalctl_bin,
                    "-u",
                    self._journal_unit,
                    "-n",
                    str(limit),
                    "--no-pager",
                    "-o",
                    "short-iso",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=3,
            )
        except (OSError, subprocess.SubprocessError):
            return None

        if result.returncode != 0:
            return None
        lines = tuple(line.rstrip() for line in result.stdout.splitlines() if line.strip())
        if not lines:
            return None
        return LogSnapshot(source=f"journal:{self._journal_unit}", lines=lines)


def match_system_activity_query(prompt: str) -> SystemActivityRequest | None:
    """Return a structured activity request for direct host-observability prompts."""

    normalized = " ".join(prompt.strip().lower().split())
    if not normalized:
        return None

    has_host_context = any(hint in normalized for hint in HOST_CONTEXT_HINTS)
    include_logs = any(hint in normalized for hint in LOG_QUERY_HINTS) and (
        has_host_context or "journal" in normalized
    )
    include_processes = any(hint in normalized for hint in PROCESS_QUERY_HINTS)
    if not include_processes:
        include_processes = (
            any(hint in normalized for hint in PROCESS_NOUN_HINTS)
            and (has_host_context or any(token in normalized for token in ("jalan", "berjalan", "running", "aktif")))
        )
    if not include_processes:
        include_processes = (
            any(token in normalized for token in ("aplikasi", "program", "proses", "process"))
            and any(token in normalized for token in ("jalan", "berjalan", "running", "aktif"))
        )
    if not include_processes:
        include_processes = (
            "sedang apa" in normalized
            and any(token in normalized for token in ("laptop", "komputer", "pc", "mesin", "host"))
        )

    if not include_processes and not include_logs:
        return None

    return SystemActivityRequest(
        include_processes=include_processes,
        include_logs=include_logs,
        detail_hint=any(hint in normalized for hint in DETAIL_HINTS),
    )


def _finalize_process_group(accumulator: dict[str, object]) -> ProcessGroupSummary:
    statuses: Counter[str] = accumulator["statuses"]  # type: ignore[assignment]
    top_statuses = statuses.most_common(2)
    status_summary = ", ".join(
        f"{_humanize_status(status)} x{count}"
        for status, count in top_statuses
    ) or "status tidak diketahui"
    oldest_create_time = float(accumulator["oldest_create_time"])
    if oldest_create_time == float("inf"):
        oldest_create_time = 0.0
    usernames = tuple(sorted(str(username) for username in accumulator["usernames"]))
    return ProcessGroupSummary(
        label=str(accumulator["label"]),
        process_count=int(accumulator["process_count"]),
        total_memory_bytes=int(accumulator["total_memory_bytes"]),
        oldest_create_time=oldest_create_time,
        sample_pid=int(accumulator["sample_pid"]),
        status_summary=status_summary,
        sample_command=str(accumulator["sample_command"]),
        usernames=usernames,
        tracked_by_codi=bool(accumulator["tracked_by_codi"]),
    )


def _current_username() -> str:
    try:
        return getpass.getuser()
    except OSError:
        return "unknown"


def _looks_like_desktop_process(
    *,
    name: str,
    command: str,
    username: str,
    current_user: str,
    terminal: str | None,
    tracked_label: str | None,
) -> bool:
    if tracked_label:
        return True
    if username != current_user:
        return False
    if terminal:
        return False
    lowered_name = name.lower()
    lowered_command = command.lower()
    if lowered_name in DESKTOP_HELPER_NAMES:
        return False
    if any(flag in lowered_command for flag in DESKTOP_HELPER_FLAGS):
        return False
    return True


def _should_skip_process(name: str, command: str, username: str) -> bool:
    lowered_name = name.lower()
    lowered_command = command.lower()
    if lowered_name in DESKTOP_HELPER_NAMES:
        return True
    if any(flag in lowered_command for flag in DESKTOP_HELPER_FLAGS):
        return True
    if lowered_name in LOW_SIGNAL_BACKGROUND_NAMES:
        return True
    if lowered_name.startswith(("kworker", "rcu_", "migration/")):
        return True
    if username == "root" and lowered_name.startswith(("kthread", "watchdog")):
        return True
    if lowered_command.startswith("[") and lowered_command.endswith("]"):
        return True
    return False


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _coerce_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _derive_name_from_cmdline(cmdline: object) -> str:
    if not isinstance(cmdline, (list, tuple)) or not cmdline:
        return ""
    return Path(str(cmdline[0])).name


def _stringify_command(cmdline: object) -> str:
    if isinstance(cmdline, (list, tuple)):
        parts = [str(part).strip() for part in cmdline if str(part).strip()]
        command = " ".join(parts)
    else:
        command = _safe_text(cmdline)
    if len(command) > 140:
        return f"{command[:137].rstrip()}..."
    return command


def _humanize_process_name(name: str) -> str:
    cleaned = name.replace("_", " ").replace("-", " ").strip()
    if not cleaned:
        return "Proses tanpa nama"
    return " ".join(word.capitalize() for word in cleaned.split())


def _humanize_status(status: str) -> str:
    mapping = {
        "disk-sleep": "disk sleep",
        "running": "running",
        "sleeping": "sleeping",
        "stopped": "stopped",
        "tracing-stop": "trace stop",
        "waiting": "waiting",
        "waking": "waking",
        "zombie": "zombie",
    }
    return mapping.get(status.lower(), status)
