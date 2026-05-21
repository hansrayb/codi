"""Helpers for safe, natural-language `.env` configuration updates."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


class EnvConfigError(RuntimeError):
    """Raised when a `.env` config update cannot be parsed or applied safely."""


@dataclass(frozen=True)
class EnvConfigUpdateRequest:
    """A structured request to update an allowlisted `.env` setting."""

    key: str
    value: str
    display_name: str
    original_prompt: str
    restart_required: bool = True


@dataclass(frozen=True)
class EnvConfigUpdateResult:
    """The result of applying a `.env` config update."""

    key: str
    display_name: str
    old_value: str | None
    new_value: str
    env_path: Path
    changed: bool
    restart_required: bool


_ENV_SETTING_ALIASES: dict[str, tuple[str, ...]] = {
    "CLAUDE_TIMEOUT": (
        "claude timeout",
        "timeout claude",
        "timeout codi",
    ),
    "LOCAL_SHELL_TIMEOUT": (
        "local shell timeout",
        "timeout local shell",
        "timeout shell lokal",
        "shell timeout lokal",
    ),
}

_DISPLAY_NAMES = {
    "CLAUDE_TIMEOUT": "Claude timeout",
    "LOCAL_SHELL_TIMEOUT": "Local shell timeout",
}


def match_env_config_update_query(prompt: str) -> EnvConfigUpdateRequest | None:
    """Parse natural-language prompts that safely update allowlisted `.env` keys."""

    condensed_prompt = " ".join(prompt.strip().split())
    if not condensed_prompt:
        return None

    direct_match = re.match(
        r"^(?:ubah|ganti|set)\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:jadi|ke|menjadi|=)\s*([0-9]+)\s*$",
        condensed_prompt,
        re.IGNORECASE,
    )
    if direct_match:
        key = direct_match.group(1).upper()
        if key in _ENV_SETTING_ALIASES:
            return EnvConfigUpdateRequest(
                key=key,
                value=_validate_env_value(key, direct_match.group(2)),
                display_name=_DISPLAY_NAMES.get(key, key),
                original_prompt=condensed_prompt,
            )

    natural_match = re.match(
        r"^(?:ubah|ganti|set)\s+(.+?)\s+(?:jadi|ke|menjadi)\s+([0-9]+)\s*$",
        condensed_prompt,
        re.IGNORECASE,
    )
    if natural_match is None:
        return None

    raw_alias = " ".join(natural_match.group(1).strip().lower().split())
    key = _resolve_setting_alias(raw_alias)
    if key is None:
        return None
    return EnvConfigUpdateRequest(
        key=key,
        value=_validate_env_value(key, natural_match.group(2)),
        display_name=_DISPLAY_NAMES.get(key, key),
        original_prompt=condensed_prompt,
    )


def apply_env_config_update(
    request: EnvConfigUpdateRequest,
    *,
    env_path: Path,
) -> EnvConfigUpdateResult:
    """Apply an allowlisted config update to a local `.env` file."""

    target_path = env_path.expanduser().resolve()
    existing_text = ""
    if target_path.exists():
        existing_text = target_path.read_text(encoding="utf-8")

    old_value = _find_env_value(existing_text, request.key)
    changed = old_value != request.value
    if not changed:
        return EnvConfigUpdateResult(
            key=request.key,
            display_name=request.display_name,
            old_value=old_value,
            new_value=request.value,
            env_path=target_path,
            changed=False,
            restart_required=False,
        )

    pattern = re.compile(rf"^{re.escape(request.key)}=.*$", re.MULTILINE)
    replacement_line = f"{request.key}={request.value}"
    if pattern.search(existing_text):
        updated_text = pattern.sub(replacement_line, existing_text, count=1)
    else:
        separator = "\n" if existing_text and not existing_text.endswith("\n") else ""
        updated_text = f"{existing_text}{separator}{replacement_line}\n"

    target_path.write_text(updated_text, encoding="utf-8")
    return EnvConfigUpdateResult(
        key=request.key,
        display_name=request.display_name,
        old_value=old_value,
        new_value=request.value,
        env_path=target_path,
        changed=True,
        restart_required=request.restart_required,
    )


def _resolve_setting_alias(raw_alias: str) -> str | None:
    for key, aliases in _ENV_SETTING_ALIASES.items():
        if raw_alias == key.lower() or raw_alias in aliases:
            return key
    return None


def _validate_env_value(key: str, raw_value: str) -> str:
    if key in {"CLAUDE_TIMEOUT", "LOCAL_SHELL_TIMEOUT"}:
        return _validate_positive_int(raw_value, key)
    raise EnvConfigError(f"Pengaturan `{key}` belum didukung untuk update natural ini.")


def _validate_positive_int(raw_value: str, key: str) -> str:
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise EnvConfigError(f"Nilai `{key}` harus berupa angka bulat positif.") from exc
    if value <= 0:
        raise EnvConfigError(f"Nilai `{key}` harus lebih besar dari 0.")
    return str(value)


def _find_env_value(content: str, key: str) -> str | None:
    pattern = re.compile(rf"^{re.escape(key)}=(.*)$", re.MULTILINE)
    match = pattern.search(content)
    if match is None:
        return None
    return match.group(1).strip()
