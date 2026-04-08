"""Application configuration for the orchestrated Codex Telegram bot."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
VALID_ROLES = {"builder", "reviewer", "debugger", "ops", "general"}
VALID_REASONING_EFFORTS = {"low", "medium", "high", "xhigh"}


class ConfigError(ValueError):
    """Raised when the environment configuration is invalid."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated runtime settings for the application."""

    assistant_name: str
    enable_desktop_actions: bool
    enable_local_shell: bool
    telegram_bot_token: str
    allowed_user_ids: tuple[int, ...]
    codex_bin: str
    codex_timeout: int
    codex_reasoning_effort: str
    codex_work_dir: Path
    allowed_work_dirs: tuple[Path, ...]
    default_role: str
    max_active_sessions: int
    max_sessions_per_user: int
    session_idle_ttl_minutes: int
    max_queue_per_session: int
    max_output_length: int
    local_shell_timeout: int
    log_level: str
    log_file: str | None
    max_requests_per_minute: int
    repo_watch_poll_seconds: int
    max_watched_repos_per_user: int

    @property
    def session_idle_ttl_seconds(self) -> int:
        """Return the idle TTL converted to seconds."""

        return self.session_idle_ttl_minutes * 60

    def is_workdir_allowed(self, candidate: Path) -> bool:
        """Return whether the path is within the configured allowlist."""

        resolved = candidate.resolve()
        return any(
            resolved == allowed or allowed in resolved.parents
            for allowed in self.allowed_work_dirs
        )


def load_settings(env_file: str | os.PathLike[str] = ".env") -> Settings:
    """Load, validate, and return application settings."""

    load_dotenv(env_file, override=False)

    assistant_name = (os.getenv("ASSISTANT_NAME") or "Codi").strip() or "Codi"
    enable_desktop_actions = _parse_bool(os.getenv("ENABLE_DESKTOP_ACTIONS", "true"))
    enable_local_shell = _parse_bool(os.getenv("ENABLE_LOCAL_SHELL", "false"))
    token = _require_env("TELEGRAM_BOT_TOKEN")
    allowed_user_ids = _parse_int_list(_require_env("ALLOWED_USER_IDS"), "ALLOWED_USER_IDS")
    codex_bin = os.getenv("CODEX_BIN", "codex").strip() or "codex"
    codex_timeout = _parse_positive_int(os.getenv("CODEX_TIMEOUT", "180"), "CODEX_TIMEOUT")
    codex_reasoning_effort = (
        os.getenv("CODEX_REASONING_EFFORT", "medium").strip().lower() or "medium"
    )
    codex_work_dir = _parse_existing_dir(
        os.getenv("CODEX_WORK_DIR", os.getcwd()),
        "CODEX_WORK_DIR",
    )
    allowed_work_dirs_raw = os.getenv("ALLOWED_WORK_DIRS", str(codex_work_dir))
    allowed_work_dirs = tuple(
        _parse_existing_dir(item, "ALLOWED_WORK_DIRS")
        for item in _split_csv(allowed_work_dirs_raw)
    )
    default_role = os.getenv("DEFAULT_ROLE", "general").strip().lower() or "general"
    max_active_sessions = _parse_positive_int(
        os.getenv("MAX_ACTIVE_SESSIONS", "4"),
        "MAX_ACTIVE_SESSIONS",
    )
    max_sessions_per_user = _parse_positive_int(
        os.getenv("MAX_SESSIONS_PER_USER", "3"),
        "MAX_SESSIONS_PER_USER",
    )
    session_idle_ttl_minutes = _parse_positive_int(
        os.getenv("SESSION_IDLE_TTL_MINUTES", "60"),
        "SESSION_IDLE_TTL_MINUTES",
    )
    max_queue_per_session = _parse_non_negative_int(
        os.getenv("MAX_QUEUE_PER_SESSION", "1"),
        "MAX_QUEUE_PER_SESSION",
    )
    max_output_length = _parse_positive_int(
        os.getenv("MAX_OUTPUT_LENGTH", "3000"),
        "MAX_OUTPUT_LENGTH",
    )
    local_shell_timeout = _parse_positive_int(
        os.getenv("LOCAL_SHELL_TIMEOUT", "120"),
        "LOCAL_SHELL_TIMEOUT",
    )
    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"
    log_file = (os.getenv("LOG_FILE") or "").strip() or None
    max_requests_per_minute = _parse_positive_int(
        os.getenv("MAX_REQUESTS_PER_MINUTE", "5"),
        "MAX_REQUESTS_PER_MINUTE",
    )
    repo_watch_poll_seconds = _parse_positive_int(
        os.getenv("REPO_WATCH_POLL_SECONDS", "30"),
        "REPO_WATCH_POLL_SECONDS",
    )
    max_watched_repos_per_user = _parse_positive_int(
        os.getenv("MAX_WATCHED_REPOS_PER_USER", "5"),
        "MAX_WATCHED_REPOS_PER_USER",
    )

    if default_role not in VALID_ROLES:
        raise ConfigError(
            f"DEFAULT_ROLE must be one of {sorted(VALID_ROLES)}, got {default_role!r}."
        )
    if codex_reasoning_effort not in VALID_REASONING_EFFORTS:
        raise ConfigError(
            "CODEX_REASONING_EFFORT must be one of "
            f"{sorted(VALID_REASONING_EFFORTS)}, got {codex_reasoning_effort!r}."
        )
    if log_level not in VALID_LOG_LEVELS:
        raise ConfigError(
            f"LOG_LEVEL must be one of {sorted(VALID_LOG_LEVELS)}, got {log_level!r}."
        )
    if not any(
        codex_work_dir == allowed or allowed in codex_work_dir.parents
        for allowed in allowed_work_dirs
    ):
        raise ConfigError("CODEX_WORK_DIR must be inside ALLOWED_WORK_DIRS.")
    if max_sessions_per_user > max_active_sessions:
        raise ConfigError("MAX_SESSIONS_PER_USER cannot exceed MAX_ACTIVE_SESSIONS.")

    return Settings(
        assistant_name=assistant_name,
        enable_desktop_actions=enable_desktop_actions,
        enable_local_shell=enable_local_shell,
        telegram_bot_token=token,
        allowed_user_ids=allowed_user_ids,
        codex_bin=codex_bin,
        codex_timeout=codex_timeout,
        codex_reasoning_effort=codex_reasoning_effort,
        codex_work_dir=codex_work_dir,
        allowed_work_dirs=allowed_work_dirs,
        default_role=default_role,
        max_active_sessions=max_active_sessions,
        max_sessions_per_user=max_sessions_per_user,
        session_idle_ttl_minutes=session_idle_ttl_minutes,
        max_queue_per_session=max_queue_per_session,
        max_output_length=max_output_length,
        local_shell_timeout=local_shell_timeout,
        log_level=log_level,
        log_file=log_file,
        max_requests_per_minute=max_requests_per_minute,
        repo_watch_poll_seconds=repo_watch_poll_seconds,
        max_watched_repos_per_user=max_watched_repos_per_user,
    )


def _require_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise ConfigError(f"{name} is required.")
    return value


def _parse_int_list(raw: str, name: str) -> tuple[int, ...]:
    values: list[int] = []
    for item in _split_csv(raw):
        try:
            values.append(int(item))
        except ValueError as exc:
            raise ConfigError(f"{name} must contain only integers.") from exc
    if not values:
        raise ConfigError(f"{name} must contain at least one user ID.")
    return tuple(values)


def _parse_positive_int(raw: str, name: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer.") from exc
    if value <= 0:
        raise ConfigError(f"{name} must be greater than 0.")
    return value


def _parse_non_negative_int(raw: str, name: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer.") from exc
    if value < 0:
        raise ConfigError(f"{name} must be 0 or greater.")
    return value


def _parse_existing_dir(raw: str, name: str) -> Path:
    path = Path(raw).expanduser().resolve()
    if not path.exists():
        raise ConfigError(f"{name} path does not exist: {path}")
    if not path.is_dir():
        raise ConfigError(f"{name} must point to a directory: {path}")
    return path


def _split_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _parse_bool(raw: str | None) -> bool:
    value = (raw or "").strip().lower()
    return value not in {"0", "false", "no", "off", ""}
