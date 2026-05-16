"""Rule-based prompt routing for the orchestrated Codex bot."""

from __future__ import annotations

import re
from dataclasses import dataclass

from models.session import Session

CONTINUATION_HINTS = (
    "lanjutkan",
    "yang tadi",
    "perbaiki lagi",
    "tambahkan lagi",
    "lanjut",
    "teruskan",
)

KEYWORDS: dict[str, tuple[str, ...]] = {
    "reviewer": (
        "review",
        "review pr",
        "review commit",
        "audit",
        "cek bug",
        "cek diff",
        "cek perubahan",
        "cek repo",
        "analisis repo",
        "ringkas repo",
        "pelajari repo",
        "pull request",
        "merge request",
        "risk",
        "risiko",
        "security",
    ),
    "builder": (
        "buat",
        "implement",
        "refactor",
        "tambahkan test",
        "endpoint",
        "commit message",
        "pesan commit",
        "buat commit",
        "siapkan commit",
        "pr description",
        "deskripsi pr",
        "buat pr",
        "siapkan pr",
        "ringkas diff",
        "ganti",
        "ubah",
        "edit",
        "update",
        "hapus",
        "tambah",
        "pindahkan",
        "rename",
        "tulis",
        "perbarui",
        "modifikasi",
        "replace",
        "insert",
        "delete",
    ),
    "advisor": (
        "saran",
        "rekomendasi",
        "strategi bisnis",
        "analisis bisnis",
        "performa bisnis",
        "kinerja bisnis",
        "omzet",
        "pendapatan",
        "pertumbuhan",
        "tren penjualan",
        "trend penjualan",
        "optimasi bisnis",
        "potensi bisnis",
        "peluang bisnis",
        "evaluasi bisnis",
        "insight bisnis",
        "konsultasi",
        "cara meningkatkan",
        "bagaimana meningkatkan",
        "tingkatkan penjualan",
        "tingkatkan mitra",
        "konversi",
        "retention",
        "churn",
        "akuisisi mitra",
    ),
    "debugger": ("error", "traceback", "kenapa gagal", "debug", "crash", "flaky"),
    "ops": (
        "status",
        "service",
        "log",
        "deploy",
        "uptime",
        "systemd",
        "aplikasi aktif",
        "proses aktif",
        "background process",
        "running process",
        "running app",
        "sedang menjalankan",
        "yang berjalan",
    ),
}

ROLE_NAMES = ("builder", "reviewer", "debugger", "ops", "general", "advisor")
OVERRIDE_PATTERNS = (
    re.compile(r"\bpakai\s+(builder|reviewer|debugger|ops|general|advisor)\b"),
    re.compile(r"\bsebagai\s+(builder|reviewer|debugger|ops|general|advisor)\b"),
    re.compile(r"\btask\s+(builder|reviewer|debugger|ops|general|advisor)\b"),
    re.compile(r"\brole\s+(builder|reviewer|debugger|ops|general|advisor)\b"),
)
STOPWORDS = {
    "yang",
    "dan",
    "atau",
    "untuk",
    "dengan",
    "lagi",
    "task",
    "kode",
    "this",
    "that",
    "please",
    "pakai",
}


@dataclass(frozen=True)
class RoutingDecision:
    """Decision produced by the rule-based router."""

    role: str
    confidence: float
    reason: str
    override_applied: bool = False
    continuation_hint: bool = False


class IntentRouter:
    """Route prompts to the most suitable internal role."""

    def __init__(self, default_role: str = "general") -> None:
        self._default_role = default_role

    def route(self, prompt: str, active_session: Session | None = None) -> RoutingDecision:
        """Return a role decision for the given user prompt."""

        normalized = _normalize(prompt)
        if not normalized:
            return RoutingDecision(
                role=self._default_role,
                confidence=0.0,
                reason="empty_prompt",
            )

        override = self._extract_override(normalized)
        if override:
            return RoutingDecision(
                role=override,
                confidence=1.0,
                reason="explicit_override",
                override_applied=True,
            )

        continuation_hint = self._has_continuation_hint(normalized)
        if continuation_hint and active_session is not None:
            return RoutingDecision(
                role=active_session.role,
                confidence=0.88,
                reason="continuation_hint",
                continuation_hint=True,
            )

        scores = {role: 0 for role in KEYWORDS}
        for role, keywords in KEYWORDS.items():
            for keyword in keywords:
                if keyword in normalized:
                    scores[role] += 1

        best_role = max(scores, key=scores.get, default=self._default_role)
        best_score = scores.get(best_role, 0)
        if best_score <= 0:
            if self._is_question(normalized):
                return RoutingDecision(
                    role=self._default_role,
                    confidence=0.7,
                    reason="question_pattern",
                )
            return RoutingDecision(
                role=self._default_role,
                confidence=0.35,
                reason="fallback_general",
            )

        confidence = min(0.95, 0.5 + (best_score * 0.15))
        return RoutingDecision(
            role=best_role,
            confidence=confidence,
            reason="keyword_match",
        )

    def should_reuse(
        self,
        prompt: str,
        decision: RoutingDecision,
        active_session: Session | None,
    ) -> bool:
        """Return whether the active session should likely be reused."""

        if active_session is None or active_session.role != decision.role:
            return False
        normalized = _normalize(prompt)
        if decision.continuation_hint:
            return True
        if self._has_continuation_hint(normalized):
            return True
        if not active_session.summary.strip():
            return False
        return _topic_overlap(normalized, active_session.summary) >= 2

    def _extract_override(self, normalized_prompt: str) -> str | None:
        for pattern in OVERRIDE_PATTERNS:
            match = pattern.search(normalized_prompt)
            if match:
                role = match.group(1)
                if role in ROLE_NAMES:
                    return role
        return None

    @staticmethod
    def _has_continuation_hint(normalized_prompt: str) -> bool:
        return any(hint in normalized_prompt for hint in CONTINUATION_HINTS)

    @staticmethod
    def _is_question(normalized_prompt: str) -> bool:
        if normalized_prompt.endswith("?"):
            return True
        question_starters = (
            "apa ", "apakah ", "kenapa ", "mengapa ", "bagaimana ", "gimana ",
            "kapan ", "dimana ", "di mana ", "siapa ", "berapa ",
            "what ", "why ", "how ", "when ", "where ", "who ",
            "jelaskan ", "tampilkan ", "tunjukkan ", "lihat ", "cek ",
        )
        question_phrases = ("cara kerja", "cara kerjanya", "cara pakai")
        return (
            normalized_prompt.startswith(question_starters)
            or any(phrase in normalized_prompt for phrase in question_phrases)
        )


def _normalize(prompt: str) -> str:
    return re.sub(r"\s+", " ", prompt.strip().lower())


def _topic_overlap(prompt: str, summary: str) -> int:
    prompt_tokens = _tokenize(prompt)
    summary_tokens = _tokenize(summary)
    return len(prompt_tokens & summary_tokens)


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9_-]{4,}", text.lower())
        if token not in STOPWORDS
    }
