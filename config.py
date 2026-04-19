"""Application configuration for the orchestrated Codex Telegram bot."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
VALID_ROLES = {"builder", "reviewer", "debugger", "ops", "general"}
VALID_REASONING_EFFORTS = {"low", "medium", "high", "xhigh"}
VALID_BACKENDS = {"codex", "claude"}


class ConfigError(ValueError):
    """Raised when the environment configuration is invalid."""


@dataclass(frozen=True)
class Settings:
    """Validated runtime settings for the application."""

    assistant_name: str
    enable_desktop_actions: bool
    enable_local_shell: bool
    telegram_bot_token: str
    allowed_user_ids: tuple[int, ...]
    admin_user_ids: tuple[int, ...]
    viewer_user_ids: tuple[int, ...]
    business_user_ids: tuple[int, ...]
    business_allowed_dirs: tuple[Path, ...]
    business_database_paths: tuple[Path, ...]
    business_database_urls: tuple[str, ...]
    ai_backend: str
    codex_bin: str
    codex_timeout: int
    codex_reasoning_effort: str
    codex_write_sandbox_mode: str
    codex_work_dir: Path
    claude_bin: str
    claude_model: str
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
    service_watch_poll_seconds: int
    max_watched_repos_per_user: int
    important_services: tuple[str, ...]
    important_pm2_apps: tuple[str, ...]
    alert_targets_path: Path
    enable_device_registry: bool
    device_registry_path: Path
    device_api_host: str
    device_api_port: int
    device_api_shared_token: str | None
    device_heartbeat_ttl_seconds: int

    @property
    def session_idle_ttl_seconds(self) -> int:
        """Return the idle TTL converted to seconds."""

        return self.session_idle_ttl_minutes * 60

    @property
    def all_search_dirs(self) -> tuple[Path, ...]:
        """Union of allowed_work_dirs and business_allowed_dirs for repo indexing."""
        seen: set[Path] = set()
        result: list[Path] = []
        for p in (*self.allowed_work_dirs, *self.business_allowed_dirs):
            if p not in seen:
                seen.add(p)
                result.append(p)
        return tuple(result)

    def is_business_dir(self, path: Path) -> bool:
        """Return whether the path is within a configured business directory."""
        resolved = path.resolve()
        return any(
            resolved == b or b in resolved.parents
            for b in self.business_allowed_dirs
        )

    def is_search_dir_allowed(self, candidate: Path) -> bool:
        """Return whether the path is inside any indexed work or business directory."""

        resolved = candidate.resolve()
        return any(
            resolved == allowed or allowed in resolved.parents
            for allowed in self.all_search_dirs
        )

    @property
    def operator_user_ids(self) -> tuple[int, ...]:
        """Users with operator role (whitelisted but not admin or viewer)."""
        admin_set = set(self.admin_user_ids)
        viewer_set = set(self.viewer_user_ids)
        return tuple(uid for uid in self.allowed_user_ids if uid not in admin_set and uid not in viewer_set)

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
    admin_user_ids = _parse_int_list_optional(os.getenv("ADMIN_USER_IDS", ""), "ADMIN_USER_IDS")
    viewer_user_ids = _parse_int_list_optional(os.getenv("VIEWER_USER_IDS", ""), "VIEWER_USER_IDS")
    business_user_ids = _parse_int_list_optional(os.getenv("BUSINESS_USER_IDS", ""), "BUSINESS_USER_IDS")
    business_allowed_dirs_raw = os.getenv("BUSINESS_ALLOWED_DIRS", "")
    business_allowed_dirs = _parse_dir_list_optional(business_allowed_dirs_raw, "BUSINESS_ALLOWED_DIRS")
    business_database_paths = _parse_path_list_optional(
        os.getenv("BUSINESS_DATABASE_PATHS", ""),
        "BUSINESS_DATABASE_PATHS",
    )
    business_database_urls = _parse_str_list_optional(
        os.getenv("BUSINESS_DATABASE_URLS", ""),
    )
    ai_backend = os.getenv("AI_BACKEND", "codex").strip().lower() or "codex"
    codex_bin = os.getenv("CODEX_BIN", "codex").strip() or "codex"
    codex_timeout = _parse_positive_int(os.getenv("CODEX_TIMEOUT", "600"), "CODEX_TIMEOUT")
    codex_reasoning_effort = (
        os.getenv("CODEX_REASONING_EFFORT", "medium").strip().lower() or "medium"
    )
    codex_write_sandbox_mode = (
        os.getenv("CODEX_WRITE_SANDBOX_MODE", "workspace-write").strip() or "workspace-write"
    )
    claude_bin = os.getenv("CLAUDE_BIN", "claude").strip() or "claude"
    claude_model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6").strip() or "claude-sonnet-4-6"
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
    service_watch_poll_seconds = _parse_positive_int(
        os.getenv("SERVICE_WATCH_POLL_SECONDS", "30"),
        "SERVICE_WATCH_POLL_SECONDS",
    )
    max_watched_repos_per_user = _parse_positive_int(
        os.getenv("MAX_WATCHED_REPOS_PER_USER", "5"),
        "MAX_WATCHED_REPOS_PER_USER",
    )
    enable_device_registry = _parse_bool(os.getenv("ENABLE_DEVICE_REGISTRY", "false"))
    device_registry_path = Path(
        os.getenv("DEVICE_REGISTRY_PATH", str(codex_work_dir / "codi-devices.json"))
    ).expanduser().resolve()
    device_api_host = (os.getenv("DEVICE_API_HOST", "127.0.0.1").strip() or "127.0.0.1")
    device_api_port = _parse_port(os.getenv("DEVICE_API_PORT", "8787"), "DEVICE_API_PORT")
    device_api_shared_token = (os.getenv("DEVICE_API_SHARED_TOKEN") or "").strip() or None
    device_heartbeat_ttl_seconds = _parse_positive_int(
        os.getenv("DEVICE_HEARTBEAT_TTL_SECONDS", "90"),
        "DEVICE_HEARTBEAT_TTL_SECONDS",
    )
    important_services = tuple(
        item.strip()
        for item in _split_csv(os.getenv("IMPORTANT_SERVICES", "codi.service"))
        if item.strip()
    ) or ("codi.service",)
    important_pm2_apps = tuple(
        item.strip()
        for item in _split_csv(os.getenv("IMPORTANT_PM2_APPS", ""))
        if item.strip()
    )
    alert_targets_path = Path(
        os.getenv("ALERT_TARGETS_PATH", str(codex_work_dir / "codi-alert-targets.json"))
    ).expanduser().resolve()

    allowed_set = set(allowed_user_ids)
    for uid in admin_user_ids:
        if uid not in allowed_set:
            raise ConfigError(f"ADMIN_USER_IDS contains {uid} which is not in ALLOWED_USER_IDS.")
    for uid in viewer_user_ids:
        if uid not in allowed_set:
            raise ConfigError(f"VIEWER_USER_IDS contains {uid} which is not in ALLOWED_USER_IDS.")
    overlap = set(admin_user_ids) & set(viewer_user_ids)
    if overlap:
        raise ConfigError(f"User IDs {overlap} appear in both ADMIN_USER_IDS and VIEWER_USER_IDS.")
    for uid in business_user_ids:
        if uid not in allowed_set:
            raise ConfigError(f"BUSINESS_USER_IDS contains {uid} which is not in ALLOWED_USER_IDS.")
    biz_overlap = set(business_user_ids) & (set(admin_user_ids) | set(viewer_user_ids))
    if biz_overlap:
        raise ConfigError(f"User IDs {biz_overlap} appear in BUSINESS_USER_IDS and another role list.")
    if business_user_ids and not business_allowed_dirs:
        raise ConfigError("BUSINESS_ALLOWED_DIRS is required when BUSINESS_USER_IDS is set.")

    if default_role not in VALID_ROLES:
        raise ConfigError(
            f"DEFAULT_ROLE must be one of {sorted(VALID_ROLES)}, got {default_role!r}."
        )
    if ai_backend not in VALID_BACKENDS:
        raise ConfigError(
            f"AI_BACKEND must be one of {sorted(VALID_BACKENDS)}, got {ai_backend!r}."
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
    if enable_device_registry and not device_api_shared_token:
        raise ConfigError(
            "DEVICE_API_SHARED_TOKEN is required when ENABLE_DEVICE_REGISTRY is enabled."
        )

    return Settings(
        assistant_name=assistant_name,
        enable_desktop_actions=enable_desktop_actions,
        enable_local_shell=enable_local_shell,
        telegram_bot_token=token,
        allowed_user_ids=allowed_user_ids,
        admin_user_ids=admin_user_ids,
        viewer_user_ids=viewer_user_ids,
        business_user_ids=business_user_ids,
        business_allowed_dirs=business_allowed_dirs,
        business_database_paths=business_database_paths,
        business_database_urls=business_database_urls,
        ai_backend=ai_backend,
        codex_bin=codex_bin,
        codex_timeout=codex_timeout,
        codex_reasoning_effort=codex_reasoning_effort,
        codex_write_sandbox_mode=codex_write_sandbox_mode,
        codex_work_dir=codex_work_dir,
        claude_bin=claude_bin,
        claude_model=claude_model,
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
        service_watch_poll_seconds=service_watch_poll_seconds,
        max_watched_repos_per_user=max_watched_repos_per_user,
        important_services=important_services,
        important_pm2_apps=important_pm2_apps,
        alert_targets_path=alert_targets_path,
        enable_device_registry=enable_device_registry,
        device_registry_path=device_registry_path,
        device_api_host=device_api_host,
        device_api_port=device_api_port,
        device_api_shared_token=device_api_shared_token,
        device_heartbeat_ttl_seconds=device_heartbeat_ttl_seconds,
    )


def _require_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise ConfigError(f"{name} is required.")
    return value


def _parse_dir_list_optional(raw: str, name: str) -> tuple[Path, ...]:
    if not raw.strip():
        return ()
    return tuple(_parse_existing_dir(item, name) for item in _split_csv(raw))


def _parse_path_list_optional(raw: str, name: str) -> tuple[Path, ...]:
    if not raw.strip():
        return ()
    return tuple(Path(item).expanduser().resolve() for item in _split_csv(raw))


def _parse_str_list_optional(raw: str) -> tuple[str, ...]:
    if not raw.strip():
        return ()
    return tuple(_split_csv(raw))


def _parse_int_list_optional(raw: str, name: str) -> tuple[int, ...]:
    if not raw.strip():
        return ()
    return _parse_int_list(raw, name)


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


def _parse_port(raw: str, name: str) -> int:
    value = _parse_positive_int(raw, name)
    if value > 65535:
        raise ConfigError(f"{name} must be between 1 and 65535.")
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
