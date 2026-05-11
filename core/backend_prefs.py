"""Per-user AI backend preference store."""

from __future__ import annotations

import re

VALID_BACKENDS = {"claude"}
BACKEND_LABELS = {"claude": "Claude"}

_SWITCH_TO_CLAUDE = re.compile(
    r"\b(pakai|ganti(\s+ke?)?|switch(\s+ke?)?|gunakan|pindah(\s+ke?)?)\s+claude\b",
    re.IGNORECASE,
)
_BACKEND_QUERY = re.compile(
    r"\b(backend|ai\s+backend|mode\s+ai|engine)\b",
    re.IGNORECASE,
)


class BackendPrefs:
    """In-memory per-user AI backend preference."""

    def __init__(self, default_backend: str = "claude") -> None:
        self._default = default_backend
        self._prefs: dict[int, str] = {}

    def get(self, user_id: int) -> str:
        return self._prefs.get(user_id, self._default)

    def set(self, user_id: int, backend: str) -> None:
        if backend not in VALID_BACKENDS:
            raise ValueError(f"Backend tidak valid: {backend!r}")
        self._prefs[user_id] = backend


def match_backend_switch(text: str) -> str | None:
    """Return target backend name if text is a backend switch request, else None."""
    if _SWITCH_TO_CLAUDE.search(text):
        return "claude"
    return None


def is_backend_query(text: str) -> bool:
    return bool(_BACKEND_QUERY.search(text))
