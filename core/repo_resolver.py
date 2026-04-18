"""Resolve the most likely target repository for a Telegram task."""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from config import Settings
from models.case import Case
from models.session import Session

REPO_HINT_PATTERNS = (
    re.compile(
        r"\b(?:repo|project|proyek|folder)\s+([a-zA-Z0-9_./-]+(?:\s+[a-zA-Z0-9_./-]+){0,4})",
        re.IGNORECASE,
    ),
)
ABSOLUTE_PATH_PATTERN = re.compile(r"(?P<path>(?:~|/)[^\s'\"`]+)")
SKIP_DIR_NAMES = {
    ".cache",
    ".git",
    ".hg",
    ".idea",
    ".next",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "out",
    "target",
    "venv",
}
PROJECT_MARKERS = {
    ".env.example",
    ".git",
    "Cargo.toml",
    "Gemfile",
    "Makefile",
    "README.md",
    "build.gradle",
    "composer.json",
    "go.mod",
    "main.py",
    "package.json",
    "pnpm-workspace.yaml",
    "pom.xml",
    "pubspec.yaml",
    "pyproject.toml",
    "requirements.txt",
    "setup.py",
    "spec.md",
    "tsconfig.json",
}
CONTEXTUAL_HINT_WORDS = {
    "aktif",
    "current",
    "folder",
    "ini",
    "itu",
    "project",
    "proyek",
    "repo",
    "saat",
    "sekarang",
    "tadi",
    "terakhir",
    "tersebut",
    "this",
    "workspace",
}


class RepoResolverError(RuntimeError):
    """Raised when the prompt targets an invalid or ambiguous repository."""


@dataclass(frozen=True)
class RepoResolution:
    """A resolved working location for the upcoming task."""

    root: Path
    label: str
    confidence: float
    reason: str
    explicit: bool = False
    used_active_case: bool = False
    used_active_session: bool = False


@dataclass(frozen=True)
class IndexedRepo:
    """Indexed metadata for a repository candidate."""

    root: Path
    name: str
    normalized_name: str
    compact_name: str
    tokens: frozenset[str]


class RepoResolver:
    """Resolve a repo path from an explicit prompt, active session, or default workspace."""

    def __init__(self, settings: Settings, refresh_interval_seconds: int = 30) -> None:
        self._settings = settings
        self._refresh_interval_seconds = refresh_interval_seconds
        self._indexed_repos: tuple[IndexedRepo, ...] = ()
        self._last_refresh = 0.0

    def resolve(
        self,
        prompt: str,
        active_session: Session | None = None,
        active_case: Case | None = None,
    ) -> RepoResolution:
        """Resolve the best working directory for a task."""

        normalized_prompt = _normalize(prompt)
        if not normalized_prompt:
            return self._default_resolution()

        path_resolution = self._resolve_from_path(prompt)
        if path_resolution is not None:
            return path_resolution

        indexed_repos = self._get_indexed_repos()
        repo_hint = _extract_repo_hint(prompt)
        if repo_hint:
            active_context_resolution = self._resolve_active_context(
                active_case=active_case,
                active_session=active_session,
                confidence=0.82,
            )
            if _is_contextual_repo_hint(repo_hint) and active_context_resolution is not None:
                return active_context_resolution
            return self._resolve_from_hint(repo_hint, indexed_repos, explicit=True)

        prompt_matches = self._match_prompt_against_repo_names(normalized_prompt, indexed_repos)
        if len(prompt_matches) == 1:
            match = prompt_matches[0]
            return RepoResolution(
                root=match.root,
                label=match.name,
                confidence=0.9,
                reason="prompt_name_match",
                explicit=True,
            )
        if len(prompt_matches) > 1:
            raise RepoResolverError(self._build_ambiguous_message(prompt_matches))

        active_context_resolution = self._resolve_active_context(
            active_case=active_case,
            active_session=active_session,
            confidence=0.78,
        )
        if active_context_resolution is not None:
            return active_context_resolution

        return self._default_resolution()

    def _default_resolution(self) -> RepoResolution:
        root = self._settings.codex_work_dir
        return RepoResolution(
            root=root,
            label=root.name or str(root),
            confidence=0.3,
            reason="default_workdir",
        )

    def _resolve_active_context(
        self,
        *,
        active_case: Case | None,
        active_session: Session | None,
        confidence: float,
    ) -> RepoResolution | None:
        if active_case is not None:
            active_root = Path(active_case.repo_root).resolve()
            if self._settings.is_workdir_allowed(active_root):
                return RepoResolution(
                    root=active_root,
                    label=active_root.name or str(active_root),
                    confidence=confidence,
                    reason="active_case",
                    used_active_case=True,
                )
        if active_session is not None:
            active_root = Path(active_session.cwd).resolve()
            if self._settings.is_workdir_allowed(active_root):
                return RepoResolution(
                    root=active_root,
                    label=active_root.name or str(active_root),
                    confidence=confidence,
                    reason="active_session",
                    used_active_session=True,
                )
        return None

    def _resolve_from_path(self, prompt: str) -> RepoResolution | None:
        for raw_candidate in ABSOLUTE_PATH_PATTERN.findall(prompt):
            cleaned = raw_candidate.rstrip(".,:;!?)[]}")
            candidate = Path(cleaned).expanduser()
            if not candidate.exists():
                corrected = self._resolve_missing_path_candidate(candidate)
                if corrected is None:
                    continue
                candidate = corrected
            resolved = candidate.resolve()
            if not self._settings.is_workdir_allowed(resolved):
                raise RepoResolverError(
                    f"Path {resolved} ada, tapi di luar workspace yang diizinkan untuk Codi."
                )

            repo_root = self._find_project_root(resolved)
            if repo_root is not None:
                return RepoResolution(
                    root=repo_root,
                    label=repo_root.name or str(repo_root),
                    confidence=1.0,
                    reason="absolute_path_repo",
                    explicit=True,
                )

            if resolved.is_dir():
                return RepoResolution(
                    root=resolved,
                    label=resolved.name or str(resolved),
                    confidence=0.75,
                    reason="absolute_path_workspace",
                    explicit=True,
                )

            raise RepoResolverError(
                f"Saya menemukan {resolved}, tapi belum bisa memastikan repo/folder kerjanya."
            )
        return None

    def _resolve_from_hint(
        self,
        hint: str,
        indexed_repos: tuple[IndexedRepo, ...],
        *,
        explicit: bool,
    ) -> RepoResolution:
        scored_matches = self._score_hint_matches(hint, indexed_repos)
        if not scored_matches:
            raise RepoResolverError(
                f"Saya belum menemukan repo yang cocok untuk '{hint}' di workspace yang diizinkan."
            )

        top_score, top_repo = scored_matches[0]
        if len(scored_matches) > 1:
            second_score = scored_matches[1][0]
            if top_score - second_score < 15:
                ambiguous_matches = [repo for score, repo in scored_matches if top_score - score < 15]
                raise RepoResolverError(self._build_ambiguous_message(ambiguous_matches))

        return RepoResolution(
            root=top_repo.root,
            label=top_repo.name,
            confidence=min(1.0, top_score / 100),
            reason="repo_hint_match",
            explicit=explicit,
        )

    def _score_hint_matches(
        self,
        hint: str,
        indexed_repos: tuple[IndexedRepo, ...],
    ) -> list[tuple[int, IndexedRepo]]:
        normalized_hint = _normalize(hint)
        compact_hint = _compact(normalized_hint)
        hint_tokens = _tokenize(normalized_hint)
        scored: list[tuple[int, IndexedRepo]] = []

        for repo in indexed_repos:
            score = 0
            if normalized_hint == repo.normalized_name:
                score = 100
            elif compact_hint and compact_hint == repo.compact_name:
                score = 95
            elif normalized_hint and normalized_hint in repo.normalized_name:
                score = 82

            overlap = hint_tokens & repo.tokens
            if overlap:
                score = max(score, len(overlap) * 20)
                if hint_tokens and overlap == hint_tokens:
                    score += 10
                if any(len(token) >= 6 for token in overlap):
                    score += 5

            if compact_hint and len(compact_hint) >= 4:
                ratio = SequenceMatcher(None, compact_hint, repo.compact_name).ratio()
                if ratio >= 0.72:
                    score = max(score, int(ratio * 70))

            if score >= 25:
                scored.append((score, repo))

        scored.sort(key=lambda item: (item[0], len(item[1].tokens), item[1].name), reverse=True)
        return scored

    def _match_prompt_against_repo_names(
        self,
        normalized_prompt: str,
        indexed_repos: tuple[IndexedRepo, ...],
    ) -> list[IndexedRepo]:
        matches: list[IndexedRepo] = []
        for repo in indexed_repos:
            if repo.normalized_name and repo.normalized_name in normalized_prompt:
                matches.append(repo)
                continue
            if repo.compact_name and repo.compact_name in _compact(normalized_prompt):
                matches.append(repo)
        return matches

    def _get_indexed_repos(self) -> tuple[IndexedRepo, ...]:
        now = time.monotonic()
        if self._indexed_repos and (now - self._last_refresh) < self._refresh_interval_seconds:
            return self._indexed_repos

        repos: dict[Path, IndexedRepo] = {}
        for allowed_root in self._settings.allowed_work_dirs:
            for repo_path in self._walk_repos(allowed_root):
                name = repo_path.name or str(repo_path)
                normalized_name = _normalize(name)
                repos[repo_path] = IndexedRepo(
                    root=repo_path,
                    name=name,
                    normalized_name=normalized_name,
                    compact_name=_compact(normalized_name),
                    tokens=frozenset(_tokenize(normalized_name)),
                )

        self._indexed_repos = tuple(
            sorted(repos.values(), key=lambda repo: (repo.name.lower(), str(repo.root)))
        )
        self._last_refresh = now
        return self._indexed_repos

    def _walk_repos(self, root: Path) -> list[Path]:
        if self._is_project_root(root):
            return [root]

        repos: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(root, topdown=True):
            dirnames[:] = [dirname for dirname in dirnames if not _should_skip_dir(dirname)]
            current = Path(dirpath).resolve()
            if self._is_project_root(current, filenames, dirnames):
                repos.append(current)
                dirnames[:] = []
        return repos

    def _find_project_root(self, candidate: Path) -> Path | None:
        current = candidate if candidate.is_dir() else candidate.parent
        while True:
            if self._is_project_root(current):
                return current
            if not self._settings.is_workdir_allowed(current):
                return None
            if current == current.parent:
                return None
            current = current.parent

    def _resolve_missing_path_candidate(self, candidate: Path) -> Path | None:
        parent = candidate.parent.expanduser()
        if not parent.exists() or not parent.is_dir():
            return None
        resolved_parent = parent.resolve()
        if not self._settings.is_workdir_allowed(resolved_parent):
            return None

        target_name = candidate.name
        target_compact = _compact(target_name)
        matches: list[Path] = []
        for child in resolved_parent.iterdir():
            if child.name.lower() == target_name.lower():
                matches.append(child)
                continue
            if target_compact and _compact(child.name) == target_compact:
                matches.append(child)

        if len(matches) == 1:
            return matches[0]
        return None

    @staticmethod
    def _is_project_root(
        path: Path,
        filenames: list[str] | None = None,
        dirnames: list[str] | None = None,
    ) -> bool:
        if dirnames is not None and ".git" in dirnames:
            return True
        if filenames is not None and ".git" in filenames:
            return True
        if filenames is not None and any(marker in filenames for marker in PROJECT_MARKERS):
            return True
        if dirnames is not None and any(marker in dirnames for marker in PROJECT_MARKERS):
            return True
        return any((path / marker).exists() for marker in PROJECT_MARKERS)

    @staticmethod
    def _build_ambiguous_message(repos: list[IndexedRepo]) -> str:
        preview = ", ".join(f"{repo.name} ({repo.root})" for repo in repos[:3])
        return (
            "Saya menemukan beberapa repo yang mirip: "
            f"{preview}. Sebutkan path penuh atau nama repo yang lebih spesifik."
        )


def _extract_repo_hint(prompt: str) -> str | None:
    for pattern in REPO_HINT_PATTERNS:
        match = pattern.search(prompt)
        if match:
            hint = match.group(1).strip().rstrip(".,:;!?")
            if hint:
                return hint
    return None


def _is_contextual_repo_hint(hint: str) -> bool:
    normalized = _normalize(hint)
    if not normalized:
        return False
    tokens = [token for token in normalized.split() if token]
    return bool(tokens) and all(token in CONTEXTUAL_HINT_WORDS for token in tokens)


def _normalize(text: str) -> str:
    lowered = text.strip().lower().replace("_", " ").replace("-", " ").replace("/", " ")
    return re.sub(r"\s+", " ", lowered)


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]{3,}", text.lower())}


def _should_skip_dir(dirname: str) -> bool:
    return dirname in SKIP_DIR_NAMES or dirname.startswith(".")
