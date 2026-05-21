"""Module-level intent classification helpers shared across orchestrator sub-modules."""

from __future__ import annotations

import re

_SELF_MOD_VERBS = re.compile(
    r"\b(?:tambah\w*|buat\w*|implement\w*|refactor\w*|perbaiki?\w*|ubah\w*|modifik\w*|update\w*|perbarui?\w*|revisi?\w*|edit\w*|hapus\w*|ganti\w*|rename\w*)\b",
    re.IGNORECASE,
)
_SELF_MOD_REFS_TEMPLATE = (
    r"\b(?:kamu|dirimu|dirinya|diri\s*(?:kamu|mu|sendiri)|bot\s*ini|{name}|"
    r"repo\s*(?:kamu|{name})|kode\s*(?:kamu|{name}))\b"
)
_SELF_CAPABILITY_QUESTION = re.compile(
    r"(?:apakah|apa|bisa|bisakah|dapatkah|dapat|mampukah|mampu|sanggup|boleh)\b.{0,80}"
    r"(?:modifik\w*|ngubah\w*|ubah\w*|perbarui?\w*|revisi?\w*|ngedit\w*|edit\w*|update\w*|refactor\w*|"
    r"membuat\s+fitur|tambah\s+fitur)",
    re.IGNORECASE,
)


def _is_self_modification_action(text: str, assistant_name: str) -> bool:
    name = re.escape(assistant_name.lower())
    refs = re.compile(_SELF_MOD_REFS_TEMPLATE.replace("{name}", name), re.IGNORECASE)
    return bool(_SELF_MOD_VERBS.search(text)) and bool(refs.search(text))


def _is_self_capability_question(text: str, assistant_name: str) -> bool:
    return bool(_SELF_CAPABILITY_QUESTION.search(text))
