"""Logging helpers for the orchestrated Codi Telegram bot."""

from __future__ import annotations

import logging
import re
import sys

SENSITIVE_PATTERNS = (
    re.compile(r"(sk-[A-Za-z0-9_-]{10,})"),
    re.compile(r"(token=)([^&\s]+)", re.IGNORECASE),
    re.compile(r"(authorization:\s*bearer\s+)(\S+)", re.IGNORECASE),
)


def configure_logging(level: str, log_file: str | None = None) -> logging.Logger:
    """Configure stdout and optional file logging for the application."""

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    for handler in handlers:
        handler.setFormatter(formatter)

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=handlers,
        force=True,
    )
    logger = logging.getLogger("codi")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    return logger


def redact_prompt(prompt: str, max_length: int = 200) -> str:
    """Mask common secrets and cap the prompt length for logs."""

    cleaned = re.sub(r"\s+", " ", prompt.strip())
    for pattern in SENSITIVE_PATTERNS:
        cleaned = pattern.sub(_mask_match, cleaned)
    if len(cleaned) > max_length:
        return f"{cleaned[: max_length - 3]}..."
    return cleaned


def _mask_match(match: re.Match[str]) -> str:
    if match.lastindex and match.lastindex > 1:
        prefix = match.group(1)
        return f"{prefix}[redacted]"
    return "[redacted]"
