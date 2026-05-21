"""Codi self-awareness: inject bot state into Claude execution context."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config import Settings
    from core.device_registry import DeviceRegistryManager
    from core.session_manager import SessionManager


def _git_version(project_root: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=project_root,
            timeout=3,
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


class CodiSelfContext:
    """Provides a runtime state snapshot for injection into Claude prompts."""

    def __init__(
        self,
        settings: "Settings",
        session_manager: "SessionManager",
        device_registry_manager: "DeviceRegistryManager",
        project_root: str,
    ) -> None:
        self._settings = settings
        self._session_manager = session_manager
        self._device_registry_manager = device_registry_manager
        self._project_root = project_root

    def get_state_block(self) -> str:
        """Return a concise state block suitable for inclusion in a system prompt."""
        name = self._settings.assistant_name
        version = _git_version(self._project_root)
        model = self._settings.claude_model

        try:
            active_count = self._session_manager.active_session_count()
        except Exception:
            active_count = "?"

        try:
            devices = self._device_registry_manager.list_devices()
            online = [d for d in devices if getattr(d, "status", None) == "online"]
            device_info = f"{len(online)}/{len(devices)} online"
        except Exception:
            device_info = "unknown"

        hr_enabled = getattr(self._settings, "hr_enabled", False)
        hr_line = f"HR system integration: {'enabled (' + self._settings.hr_api_url + ')' if hr_enabled else 'disabled'}"

        return (
            f"Bot identity:\n"
            f"- Name: {name}\n"
            f"- Version (git): {version}\n"
            f"- Model: {model}\n"
            f"- Active sessions: {active_count}\n"
            f"- Devices: {device_info}\n"
            f"- {hr_line}"
        )
