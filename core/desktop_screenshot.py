"""Helpers for taking a desktop screenshot on the local host."""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

GUI_ENV_KEYS = ("DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS")
SCREENSHOT_NOUN_HINTS = (
    "screenshot",
    "screen shot",
    "tangkapan layar",
    "capture layar",
    "capture screen",
)
SCREENSHOT_CONTEXT_HINTS = (
    "layar",
    "screen",
    "desktop",
    "monitor",
    "laptop",
    "komputer",
    "pc",
)
SCREENSHOT_ACTION_HINTS = (
    "ambil",
    "capture",
    "kirim",
    "tampilkan",
    "lihatkan",
    "lihatin",
    "foto",
)
SCREENSHOT_SUMMARY_HINTS = (
    "ringkasan",
    "ringkas",
    "summary",
    "jelaskan",
    "deskripsikan",
    "apa yang terlihat",
    "isi layar",
    "yang terlihat",
)
WINDOW_MODE_HINTS = (
    "jendela aktif",
    "window aktif",
    "active window",
    "jendela ini",
)
MONITOR_MODE_HINTS = (
    "monitor aktif",
    "monitor ini",
    "current monitor",
    "layar aktif",
)
FULLSCREEN_MODE_HINTS = (
    "layar penuh",
    "fullscreen",
    "full screen",
    "seluruh layar",
    "satu desktop",
)


class DesktopScreenshotError(RuntimeError):
    """Raised when a screenshot cannot be captured."""


@dataclass(frozen=True)
class DesktopScreenshotRequest:
    """A parsed screenshot request from the user."""

    mode: str = "fullscreen"
    include_summary: bool = False


@dataclass(frozen=True)
class ActiveWindowInfo:
    """A lightweight snapshot of the active window, when available."""

    caption: str | None = None
    app_id: str | None = None
    resource_class: str | None = None
    active_output_name: str | None = None


@dataclass(frozen=True)
class DesktopScreenshot:
    """A screenshot captured from the local desktop."""

    captured_at: datetime
    source: str
    mode: str
    image_bytes: bytes
    filename: str = "desktop-screenshot.png"
    active_window: ActiveWindowInfo | None = None


class DesktopScreenshotService:
    """Capture a screenshot from the current desktop session."""

    async def capture(self, request: DesktopScreenshotRequest | None = None) -> DesktopScreenshot:
        """Capture a fresh screenshot asynchronously."""

        effective_request = request or DesktopScreenshotRequest()
        return await asyncio.to_thread(self._capture_sync, effective_request)

    def _capture_sync(self, request: DesktopScreenshotRequest) -> DesktopScreenshot:
        if not _has_gui_session():
            raise DesktopScreenshotError(
                "Codi tidak menemukan sesi desktop aktif untuk mengambil screenshot."
            )

        with tempfile.TemporaryDirectory(prefix="codi-screenshot-") as temp_dir:
            output_path = Path(temp_dir) / _filename_for_mode(request.mode)
            env = _build_gui_env()
            errors: list[str] = []

            if _try_capture_with_spectacle(request, output_path, env, errors):
                return DesktopScreenshot(
                    captured_at=datetime.now(timezone.utc),
                    source="spectacle",
                    mode=request.mode,
                    image_bytes=output_path.read_bytes(),
                    filename=output_path.name,
                    active_window=_read_active_window_info(env),
                )

            if _try_capture_with_import(request, output_path, env, errors):
                return DesktopScreenshot(
                    captured_at=datetime.now(timezone.utc),
                    source="import",
                    mode=request.mode,
                    image_bytes=output_path.read_bytes(),
                    filename=output_path.name,
                    active_window=_read_active_window_info(env),
                )

            if _try_capture_with_gnome_screenshot(request, output_path, env, errors):
                return DesktopScreenshot(
                    captured_at=datetime.now(timezone.utc),
                    source="gnome-screenshot",
                    mode=request.mode,
                    image_bytes=output_path.read_bytes(),
                    filename=output_path.name,
                    active_window=_read_active_window_info(env),
                )

        if errors:
            raise DesktopScreenshotError(errors[-1])
        raise DesktopScreenshotError(
            "Codi belum menemukan tool screenshot yang bisa dipakai di laptop ini."
        )


def match_desktop_screenshot_query(prompt: str) -> DesktopScreenshotRequest | None:
    """Return a structured request when the user asks for a screenshot."""

    normalized = " ".join(prompt.strip().lower().split())
    if not normalized:
        return None
    tokens = set(re.findall(r"[a-z0-9]+", normalized))
    has_context_token = any(hint in tokens for hint in SCREENSHOT_CONTEXT_HINTS)
    has_action_token = any(hint in tokens for hint in SCREENSHOT_ACTION_HINTS)
    has_time_hint = "sekarang" in tokens or "saat ini" in normalized
    has_noun_hint = any(hint in normalized for hint in SCREENSHOT_NOUN_HINTS)
    has_mode_hint = any(
        hint in normalized for hint in WINDOW_MODE_HINTS + MONITOR_MODE_HINTS + FULLSCREEN_MODE_HINTS
    )
    has_summary_hint = any(hint in normalized for hint in SCREENSHOT_SUMMARY_HINTS)

    if has_noun_hint and not (has_action_token or has_context_token or has_time_hint or has_mode_hint):
        return None

    if not has_noun_hint and not (has_context_token and has_action_token and has_time_hint):
        return None

    return DesktopScreenshotRequest(
        mode=_resolve_mode(normalized),
        include_summary=has_summary_hint,
    )


def _try_capture_with_spectacle(
    request: DesktopScreenshotRequest,
    output_path: Path,
    env: dict[str, str],
    errors: list[str],
) -> bool:
    spectacle_bin = shutil.which("spectacle")
    if spectacle_bin is None:
        return False
    mode_flag = _spectacle_mode_flag(request.mode)

    try:
        completed = subprocess.run(
            [
                spectacle_bin,
                "--background",
                "--nonotify",
                mode_flag,
                "--output",
                str(output_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        errors.append(f"Gagal menjalankan spectacle: {exc}")
        return False

    if completed.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
        return True

    stderr = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
    errors.append(f"Spectacle tidak berhasil mengambil screenshot: {stderr}")
    return False


def _try_capture_with_gnome_screenshot(
    request: DesktopScreenshotRequest,
    output_path: Path,
    env: dict[str, str],
    errors: list[str],
) -> bool:
    gnome_bin = shutil.which("gnome-screenshot")
    if gnome_bin is None:
        return False

    cmd = [gnome_bin, "--file", str(output_path)]
    if request.mode == "active_window":
        cmd.append("--window")

    try:
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        errors.append(f"Gagal menjalankan gnome-screenshot: {exc}")
        return False

    if completed.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
        return True

    stderr = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
    errors.append(f"gnome-screenshot tidak berhasil mengambil screenshot: {stderr}")
    return False


def _try_capture_with_import(
    request: DesktopScreenshotRequest,
    output_path: Path,
    env: dict[str, str],
    errors: list[str],
) -> bool:
    import_bin = shutil.which("import")
    if import_bin is None:
        return False
    if request.mode != "fullscreen":
        errors.append(
            "Mode screenshot ini butuh tool yang mendukung monitor aktif atau jendela aktif."
        )
        return False

    try:
        completed = subprocess.run(
            [
                import_bin,
                "-silent",
                "-window",
                "root",
                str(output_path),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        errors.append(f"Gagal menjalankan import: {exc}")
        return False

    if completed.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
        return True

    stderr = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
    errors.append(f"Import tidak berhasil mengambil screenshot: {stderr}")
    return False


def _has_gui_session() -> bool:
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _build_gui_env() -> dict[str, str]:
    env = dict(os.environ)
    for key in GUI_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            env[key] = value
    return env


def _read_active_window_info(env: dict[str, str]) -> ActiveWindowInfo | None:
    qdbus_bin = shutil.which("qdbus-qt6") or shutil.which("qdbus6")
    if qdbus_bin is None:
        return None

    output_name = _run_qdbus_text(
        qdbus_bin,
        ["org.kde.KWin", "/KWin", "org.kde.KWin.activeOutputName"],
        env,
    )
    window_info_raw = _run_qdbus_text(
        qdbus_bin,
        ["org.kde.KWin", "/KWin", "org.kde.KWin.queryWindowInfo"],
        env,
    )
    if output_name is None and window_info_raw is None:
        return None

    window_info = _parse_qdbus_map(window_info_raw or "")
    caption = _clean_text(window_info.get("caption"))
    app_id = _clean_text(window_info.get("desktopFile"))
    resource_class = _clean_text(window_info.get("resourceClass"))
    active_output_name = _clean_text(output_name)

    return ActiveWindowInfo(
        caption=caption,
        app_id=app_id,
        resource_class=resource_class,
        active_output_name=active_output_name,
    )


def _run_qdbus_text(
    qdbus_bin: str,
    args: list[str],
    env: dict[str, str],
) -> str | None:
    try:
        completed = subprocess.run(
            [qdbus_bin, *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=4,
            env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    text = completed.stdout.strip()
    return text or None


def _parse_qdbus_map(raw_text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in raw_text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()
    return values


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _resolve_mode(normalized_prompt: str) -> str:
    if any(hint in normalized_prompt for hint in WINDOW_MODE_HINTS):
        return "active_window"
    if any(hint in normalized_prompt for hint in MONITOR_MODE_HINTS):
        return "current_monitor"
    if any(hint in normalized_prompt for hint in FULLSCREEN_MODE_HINTS):
        return "fullscreen"
    return "fullscreen"


def _spectacle_mode_flag(mode: str) -> str:
    mapping = {
        "fullscreen": "--fullscreen",
        "current_monitor": "--current",
        "active_window": "--activewindow",
    }
    return mapping.get(mode, "--fullscreen")


def _filename_for_mode(mode: str) -> str:
    mapping = {
        "fullscreen": "desktop-screenshot.png",
        "current_monitor": "monitor-screenshot.png",
        "active_window": "window-screenshot.png",
    }
    return mapping.get(mode, "desktop-screenshot.png")
