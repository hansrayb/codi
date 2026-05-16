"""Safe, explicit desktop actions that bypass Claude for GUI app launch."""

from __future__ import annotations

import asyncio
import os
import re
import shlex
import shutil
import signal
import time
from dataclasses import dataclass
from pathlib import Path


class DesktopActionError(RuntimeError):
    """Raised when a desktop action cannot be completed."""


@dataclass(frozen=True)
class DesktopAction:
    """A single allowlisted desktop action."""

    action_id: str
    label: str
    aliases: tuple[str, ...]
    command: tuple[str, ...]


@dataclass(frozen=True)
class DesktopActionRequest:
    """A requested open/close action for an allowlisted app."""

    action: DesktopAction
    operation: str


@dataclass(frozen=True)
class TrackedDesktopProcess:
    """A desktop process group launched by Codi during this runtime."""

    action_id: str
    label: str
    process_group: int


WRITER_ACTION = DesktopAction(
    action_id="profile:libreoffice_writer",
    label="LibreOffice Writer",
    aliases=(
        "document writer",
        "libreoffice writer",
        "writer",
        "writer libreoffice",
    ),
    command=("libreoffice", "--writer"),
)

FIREFOX_ACTION = DesktopAction(
    action_id="profile:firefox",
    label="Firefox",
    aliases=(
        "firefox",
        "mozilla",
        "mozilla firefox",
    ),
    command=("firefox", "--new-window"),
)

PROFILED_ACTIONS: tuple[DesktopAction, ...] = (
    WRITER_ACTION,
    FIREFOX_ACTION,
)
GUI_ENV_KEYS = ("DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS")
DEFAULT_DESKTOP_ENTRY_DIRS: tuple[Path, ...] = (
    Path("/usr/share/applications"),
    Path("/usr/local/share/applications"),
    Path.home() / ".local/share/applications",
)
OPERATION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "open",
        re.compile(r"\b(?:buka(?:kan)?|open|launch|jalankan)\b(?P<target>.+)", re.IGNORECASE),
    ),
    (
        "close",
        re.compile(r"\b(?:tutup|close|keluarkan|exit)\b(?P<target>.+)", re.IGNORECASE),
    ),
)
DESKTOP_ID_STOP_WORDS = {
    "app",
    "application",
    "desktop",
    "io",
    "net",
    "org",
}
TARGET_LEADING_FILLERS = {
    "app",
    "aplikasi",
    "program",
}
TARGET_TRAILING_FILLERS = {
    "dong",
    "lagi",
    "please",
    "tolong",
    "ya",
    "yah",
}
EXEC_FIELD_CODE_PATTERN = re.compile(r"%[fFuUdDnNickvm]")
DESKTOP_SECTION_NAME = "[Desktop Entry]"


class DesktopAppCatalog:
    """Resolve app names to safe desktop launch actions from local desktop entries."""

    def __init__(
        self,
        search_dirs: tuple[Path, ...] = DEFAULT_DESKTOP_ENTRY_DIRS,
        refresh_interval_seconds: int = 60,
    ) -> None:
        self._search_dirs = tuple(search_dirs)
        self._refresh_interval_seconds = refresh_interval_seconds
        self._cached_actions: tuple[DesktopAction, ...] = ()
        self._last_refresh = 0.0

    def resolve(self, app_hint: str) -> DesktopAction | None:
        """Resolve a prompt target to a profiled or indexed desktop action."""

        normalized_hint = _normalize_phrase(app_hint)
        if not normalized_hint:
            return None

        for action in PROFILED_ACTIONS:
            if normalized_hint in action.aliases:
                return action

        indexed_actions = self._get_indexed_actions()
        exact_matches = [
            action
            for action in indexed_actions
            if normalized_hint == action.label.lower() or normalized_hint in action.aliases
        ]
        if len(exact_matches) == 1:
            return exact_matches[0]

        compact_hint = _compact(normalized_hint)
        compact_matches = [
            action
            for action in indexed_actions
            if compact_hint
            and (
                compact_hint == _compact(action.label)
                or compact_hint in {_compact(alias) for alias in action.aliases}
            )
        ]
        if len(compact_matches) == 1:
            return compact_matches[0]
        return None

    def _get_indexed_actions(self) -> tuple[DesktopAction, ...]:
        now = time.monotonic()
        if self._cached_actions and (now - self._last_refresh) < self._refresh_interval_seconds:
            return self._cached_actions

        profiled_ids = {action.action_id for action in PROFILED_ACTIONS}
        actions: dict[str, DesktopAction] = {}
        for search_dir in self._search_dirs:
            if not search_dir.exists() or not search_dir.is_dir():
                continue

            for desktop_file in sorted(search_dir.glob("*.desktop")):
                action = _parse_desktop_entry(desktop_file)
                if action is None or action.action_id in profiled_ids:
                    continue
                actions.setdefault(action.action_id, action)

        self._cached_actions = tuple(sorted(actions.values(), key=lambda action: action.label.lower()))
        self._last_refresh = now
        return self._cached_actions


DEFAULT_APP_CATALOG = DesktopAppCatalog()


class DesktopActionManager:
    """Launch and safely close allowlisted desktop apps."""

    def __init__(self) -> None:
        self._launched_groups: dict[str, list[TrackedDesktopProcess]] = {}
        self._lock = asyncio.Lock()

    async def perform(self, request: DesktopActionRequest) -> str:
        """Execute a desktop action request and return a user-facing message."""

        if request.operation == "open":
            return await self._launch(request.action)
        if request.operation == "close":
            return await self._close(request.action)
        raise DesktopActionError("Operasi desktop action tidak dikenali.")

    async def get_tracked_processes(self) -> tuple[TrackedDesktopProcess, ...]:
        """Return live process groups launched by Codi in this runtime."""

        async with self._lock:
            snapshot = [
                tracked
                for tracked_list in self._launched_groups.values()
                for tracked in tracked_list
            ]

        tracked_processes: list[TrackedDesktopProcess] = []
        dead_entries: list[tuple[str, int]] = []
        for tracked in snapshot:
            if _is_process_group_alive(tracked.process_group):
                tracked_processes.append(tracked)
            else:
                dead_entries.append((tracked.action_id, tracked.process_group))

        if dead_entries:
            async with self._lock:
                for action_id, process_group in dead_entries:
                    self._prune_process_group_locked(action_id, process_group)

        return tuple(tracked_processes)

    async def _launch(self, action: DesktopAction) -> str:
        executable = shutil.which(action.command[0])
        if executable is None:
            raise DesktopActionError(f"{action.label} tidak ditemukan di sistem ini.")
        if not _has_gui_session():
            raise DesktopActionError(
                "Codi tidak menemukan sesi desktop aktif. "
                "Jalankan Codi dari sesi desktop Linux atau pastikan DISPLAY/Wayland tersedia."
            )

        process = await asyncio.create_subprocess_exec(
            executable,
            *action.command[1:],
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
            env=_build_gui_env(),
            start_new_session=True,
        )

        try:
            await asyncio.wait_for(process.wait(), timeout=2)
        except asyncio.TimeoutError:
            tracked = TrackedDesktopProcess(
                action_id=action.action_id,
                label=action.label,
                process_group=process.pid,
            )
            async with self._lock:
                self._launched_groups.setdefault(action.action_id, []).append(tracked)
            return f"{action.label} sedang saya buka di desktop ini."

        stderr = await process.stderr.read() if process.stderr is not None else b""
        if process.returncode and process.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace").strip()
            if detail:
                raise DesktopActionError(f"Gagal membuka {action.label}: {detail}")
            raise DesktopActionError(
                f"Gagal membuka {action.label}. Exit code: {process.returncode}."
            )

        return (
            f"{action.label} sudah saya minta buka. "
            "Kalau aplikasinya mengalihkan perintah ke instance yang sudah aktif, "
            "Codi mungkin tidak bisa melacak window ini untuk ditutup aman."
        )

    async def _close(self, action: DesktopAction) -> str:
        async with self._lock:
            tracked_candidates = list(self._launched_groups.get(action.action_id, []))

        if not tracked_candidates:
            raise DesktopActionError(
                f"Untuk keamanan, Codi hanya bisa menutup {action.label} yang dibuka oleh Codi "
                "pada sesi runtime ini."
            )

        live_candidates = [
            tracked
            for tracked in tracked_candidates
            if _is_process_group_alive(tracked.process_group)
        ]
        if not live_candidates:
            async with self._lock:
                self._launched_groups.pop(action.action_id, None)
            raise DesktopActionError(f"{action.label} tidak terlihat sedang aktif.")

        target = live_candidates[-1]
        os.killpg(target.process_group, signal.SIGTERM)

        deadline = asyncio.get_running_loop().time() + 5
        while asyncio.get_running_loop().time() < deadline:
            if not _is_process_group_alive(target.process_group):
                async with self._lock:
                    self._prune_process_group_locked(action.action_id, target.process_group)
                return f"{action.label} sudah saya minta tutup secara normal."
            await asyncio.sleep(0.2)

        return (
            f"{action.label} sudah saya kirimi permintaan tutup. "
            "Kalau ada data yang belum disimpan, aplikasi mungkin sedang menunggu konfirmasi di desktop."
        )

    def _prune_process_group_locked(self, action_id: str, process_group: int) -> None:
        tracked_list = self._launched_groups.get(action_id, [])
        remaining = [
            tracked
            for tracked in tracked_list
            if tracked.process_group != process_group and _is_process_group_alive(tracked.process_group)
        ]
        if remaining:
            self._launched_groups[action_id] = remaining
            return
        self._launched_groups.pop(action_id, None)


def match_desktop_action(
    prompt: str,
    catalog: DesktopAppCatalog | None = None,
) -> DesktopActionRequest | None:
    """Return the matching desktop action request for an explicit app prompt."""

    extracted = _extract_desktop_action_target(prompt)
    if extracted is None:
        return None

    operation, app_hint = extracted
    action = (catalog or DEFAULT_APP_CATALOG).resolve(app_hint)
    if action is None:
        return None
    return DesktopActionRequest(action=action, operation=operation)


def _extract_desktop_action_target(prompt: str) -> tuple[str, str] | None:
    compact_prompt = " ".join(prompt.strip().split())
    if not compact_prompt:
        return None

    best_match: tuple[int, str, str] | None = None
    for operation, pattern in OPERATION_PATTERNS:
        match = pattern.search(compact_prompt)
        if match is None:
            continue
        target = _clean_target_phrase(match.group("target"))
        if not target:
            continue
        if best_match is None or match.start() < best_match[0]:
            best_match = (match.start(), operation, target)

    if best_match is None:
        return None
    return best_match[1], best_match[2]


def _clean_target_phrase(target: str) -> str:
    words = _normalize_phrase(target).split()
    while words and words[0] in TARGET_LEADING_FILLERS:
        words.pop(0)
    while words and words[-1] in TARGET_TRAILING_FILLERS:
        words.pop()
    if len(words) >= 2 and words[-2:] in (["window", "baru"], ["jendela", "baru"], ["new", "window"]):
        words = words[:-2]
    return " ".join(words)


def _parse_desktop_entry(desktop_file: Path) -> DesktopAction | None:
    try:
        lines = desktop_file.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None

    in_desktop_entry = False
    is_application = False
    hidden = False
    no_display = False
    terminal = False
    name: str | None = None
    exec_line: str | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_desktop_entry = line == DESKTOP_SECTION_NAME
            continue
        if not in_desktop_entry or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key.startswith("Name["):
            continue
        if key == "Type":
            is_application = value == "Application"
        elif key == "Name" and not name:
            name = value
        elif key == "Exec" and not exec_line:
            exec_line = value
        elif key == "Hidden":
            hidden = value.lower() == "true"
        elif key == "NoDisplay":
            no_display = value.lower() == "true"
        elif key == "Terminal":
            terminal = value.lower() == "true"

    if not is_application or hidden or no_display or terminal or not name or not exec_line:
        return None

    command = _parse_exec_command(exec_line)
    if command is None:
        return None

    normalized_name = _normalize_phrase(name)
    if normalized_name in {action.label.lower() for action in PROFILED_ACTIONS}:
        return None

    aliases = tuple(sorted(_derive_aliases(name, desktop_file.stem)))
    return DesktopAction(
        action_id=f"desktop:{desktop_file.name}",
        label=name.strip(),
        aliases=aliases,
        command=command,
    )


def _parse_exec_command(exec_line: str) -> tuple[str, ...] | None:
    try:
        tokens = shlex.split(exec_line, posix=True)
    except ValueError:
        return None

    cleaned: list[str] = []
    for token in tokens:
        if EXEC_FIELD_CODE_PATTERN.fullmatch(token):
            continue
        token = EXEC_FIELD_CODE_PATTERN.sub("", token).strip()
        if token:
            cleaned.append(token)

    if not cleaned:
        return None
    if cleaned[0] == "env":
        cleaned = cleaned[1:]
        while cleaned and "=" in cleaned[0] and not cleaned[0].startswith(("/", ".")):
            cleaned = cleaned[1:]
    if not cleaned:
        return None
    return tuple(cleaned)


def _derive_aliases(name: str, desktop_stem: str) -> set[str]:
    aliases = {_normalize_phrase(name)}
    normalized_stem = _normalize_phrase(desktop_stem.replace(".", " "))
    if normalized_stem:
        aliases.add(normalized_stem)

    stem_tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", desktop_stem.lower())
        if token not in DESKTOP_ID_STOP_WORDS
    ]
    if stem_tokens:
        aliases.add(" ".join(stem_tokens))
        if len(stem_tokens[-1]) >= 4:
            aliases.add(stem_tokens[-1])
        if len(stem_tokens) >= 2:
            aliases.add(" ".join(stem_tokens[-2:]))
    return {alias for alias in aliases if alias}


def _normalize_phrase(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _has_gui_session() -> bool:
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _build_gui_env() -> dict[str, str]:
    env = dict(os.environ)
    for key in GUI_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            env[key] = value
    return env


def _is_process_group_alive(process_group: int) -> bool:
    try:
        os.killpg(process_group, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
