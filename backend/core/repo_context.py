"""Natural-language helpers for active-repo context queries."""

from __future__ import annotations

import re

_REPO_CONTEXT_STATUS_PATTERNS = (
    re.compile(
        r"^(?:repo|project|proyek|workspace|folder)\s+aktif"
        r"(?:\s+(?:saat\s+ini|sekarang))?(?:\s+apa)?\??$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:apa|yang mana)\s+(?:repo|project|proyek|workspace|folder)\s+aktif"
        r"(?:\s+(?:saat\s+ini|sekarang))?\??$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:sekarang|saat ini)\s+(?:repo|project|proyek|workspace|folder)\s+aktif(?:\s+apa)?\??$",
        re.IGNORECASE,
    ),
)

_REPO_CONTEXT_SELECTION_PATTERNS = (
    re.compile(
        r"^(?:pakai|gunakan|pilih|switch(?:\s+ke)?|ganti|set)\s+"
        r"(?:repo|project|proyek|workspace|folder)"
        r"(?:\s+aktif)?(?:\s+ke)?\s+"
        r"(?P<target>.+?)\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:pakai|gunakan|pilih|switch(?:\s+ke)?|ganti|set)\s+"
        r"(?P<target>(?:~|/).+?)\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:jadikan|setel)\s+"
        r"(?P<target>.+?)\s+"
        r"sebagai\s+(?:repo|project|proyek|workspace|folder)\s+aktif\s*$",
        re.IGNORECASE,
    ),
)


def is_repo_context_status_query(text: str) -> bool:
    """Return whether the prompt asks which repo is currently active."""

    normalized = " ".join(text.strip().split())
    if not normalized:
        return False
    return any(pattern.match(normalized) for pattern in _REPO_CONTEXT_STATUS_PATTERNS)


def extract_repo_context_selection(text: str) -> str | None:
    """Return the requested repo target when the prompt explicitly switches context."""

    normalized = " ".join(text.strip().split())
    if not normalized:
        return None
    for pattern in _REPO_CONTEXT_SELECTION_PATTERNS:
        match = pattern.match(normalized)
        if match is None:
            continue
        target = (match.group("target") or "").strip(" \"'`")
        if target:
            return target
    return None
