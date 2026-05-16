"""Approval-gated edit workflow for write-capable Claude tasks."""

from __future__ import annotations

import asyncio
import difflib
import hashlib
import itertools
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

APPROVE_WORDS = {
    "apply",
    "approve",
    "lanjutkan",
    "setujui",
    "ya lanjut",
    "ok lanjut",
}
REJECT_WORDS = {
    "batal",
    "cancel",
    "jangan jadi",
    "reject",
    "tolak",
}
COPY_IGNORE_NAMES = {
    ".git",
    ".hg",
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
DIFF_IGNORE_NAMES = COPY_IGNORE_NAMES | {
    ".cache",
    ".idea",
}


class EditApprovalError(RuntimeError):
    """Raised when the approval flow cannot continue safely."""


@dataclass(frozen=True)
class FileChange:
    """A single file-level change prepared for approval."""

    relative_path: str
    change_type: str
    before_hash: str | None
    after_hash: str | None


@dataclass
class PendingApproval:
    """An edit proposal waiting for the user to approve or reject."""

    approval_id: str
    case_id: str
    user_id: int
    role: str
    repo_root: Path
    draft_root: Path
    prompt: str
    summary_text: str
    diff_text: str
    changes: tuple[FileChange, ...]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_expired(self, ttl_minutes: int, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        return current - self.created_at > timedelta(minutes=ttl_minutes)


@dataclass
class DraftWorkspace:
    """A persistent draft workspace that lives for the duration of a case."""

    case_id: str
    user_id: int
    repo_root: Path
    draft_root: Path
    claude_thread_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_expired(self, ttl_seconds: int, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        return current - self.last_activity_at > timedelta(seconds=ttl_seconds)


class EditApprovalManager:
    """Keep a per-case draft workspace and apply it only after approval."""

    def __init__(self, ttl_minutes: int = 30, draft_ttl_seconds: int = 3600) -> None:
        self._ttl_minutes = ttl_minutes
        self._draft_ttl_seconds = draft_ttl_seconds
        self._lock = asyncio.Lock()
        self._counter = itertools.count(1)
        self._pending_by_user: dict[int, PendingApproval] = {}
        self._drafts_by_case: dict[str, DraftWorkspace] = {}

    @staticmethod
    def classify_control_message(text: str) -> str | None:
        normalized = " ".join(text.strip().lower().split())
        if normalized in APPROVE_WORDS:
            return "approve"
        if normalized in REJECT_WORDS:
            return "reject"
        return None

    async def has_pending(self, user_id: int) -> bool:
        async with self._lock:
            await self._prune_expired_locked()
            return user_id in self._pending_by_user

    async def open_or_reuse_draft(
        self,
        *,
        user_id: int,
        case_id: str,
        repo_root: Path,
    ) -> DraftWorkspace:
        resolved_repo = repo_root.resolve()
        async with self._lock:
            await self._prune_expired_locked()
            draft = self._drafts_by_case.get(case_id)
            if draft is not None and draft.repo_root == resolved_repo:
                draft.last_activity_at = datetime.now(timezone.utc)
                return draft

        draft_root = await asyncio.to_thread(self._copy_repo_to_draft, resolved_repo)
        async with self._lock:
            await self._prune_expired_locked()
            draft = self._drafts_by_case.get(case_id)
            if draft is not None and draft.repo_root == resolved_repo:
                await asyncio.to_thread(shutil.rmtree, draft_root, True)
                draft.last_activity_at = datetime.now(timezone.utc)
                return draft

            created = DraftWorkspace(
                case_id=case_id,
                user_id=user_id,
                repo_root=resolved_repo,
                draft_root=draft_root,
            )
            self._drafts_by_case[case_id] = created
            return created

    async def update_draft_thread(self, case_id: str, thread_id: str | None) -> None:
        async with self._lock:
            draft = self._drafts_by_case.get(case_id)
            if draft is None:
                return
            draft.claude_thread_id = thread_id
            draft.last_activity_at = datetime.now(timezone.utc)

    async def discard_draft_changes(self, case_id: str) -> None:
        async with self._lock:
            await self._reset_draft_locked(case_id)

    async def close_case(self, case_id: str) -> None:
        async with self._lock:
            pending_user_ids = [
                user_id
                for user_id, pending in self._pending_by_user.items()
                if pending.case_id == case_id
            ]
            for user_id in pending_user_ids:
                self._pending_by_user.pop(user_id, None)
            await self._remove_draft_locked(case_id)

    async def reset_user(self, user_id: int) -> None:
        async with self._lock:
            pending = self._pending_by_user.pop(user_id, None)
            if pending is not None:
                await self._reset_draft_locked(pending.case_id)
            owned_case_ids = [
                case_id
                for case_id, draft in self._drafts_by_case.items()
                if draft.user_id == user_id
            ]
            for case_id in owned_case_ids:
                await self._remove_draft_locked(case_id)

    async def build_pending(
        self,
        *,
        case_id: str,
        user_id: int,
        role: str,
        repo_root: Path,
        prompt: str,
        draft_root: Path,
        execution_output: str,
    ) -> PendingApproval | None:
        changes, diff_text = await asyncio.to_thread(
            self._collect_changes,
            repo_root,
            draft_root,
        )
        if not changes:
            return None

        pending = PendingApproval(
            approval_id=f"a-{next(self._counter):02d}",
            case_id=case_id,
            user_id=user_id,
            role=role,
            repo_root=repo_root,
            draft_root=draft_root,
            prompt=prompt,
            summary_text=_summarize_output(execution_output),
            diff_text=diff_text,
            changes=changes,
        )

        previous: PendingApproval | None = None
        async with self._lock:
            await self._prune_expired_locked()
            previous = self._pending_by_user.pop(user_id, None)
            self._pending_by_user[user_id] = pending
            draft = self._drafts_by_case.get(case_id)
            if draft is not None:
                draft.last_activity_at = datetime.now(timezone.utc)
        if previous is not None and previous.case_id != case_id:
            await self.discard_draft_changes(previous.case_id)
        return pending

    async def approve(self, user_id: int) -> PendingApproval:
        async with self._lock:
            await self._prune_expired_locked()
            pending = self._pending_by_user.pop(user_id, None)
        if pending is None:
            raise EditApprovalError("Tidak ada perubahan yang sedang menunggu approval.")

        try:
            await asyncio.to_thread(self._apply_pending, pending)
            async with self._lock:
                draft = self._drafts_by_case.get(pending.case_id)
                if draft is not None:
                    draft.last_activity_at = datetime.now(timezone.utc)
            return pending
        except EditApprovalError:
            await self.discard_draft_changes(pending.case_id)
            raise

    async def reject(self, user_id: int) -> PendingApproval:
        async with self._lock:
            await self._prune_expired_locked()
            pending = self._pending_by_user.pop(user_id, None)
        if pending is None:
            raise EditApprovalError("Tidak ada perubahan yang sedang menunggu approval.")
        await self.discard_draft_changes(pending.case_id)
        return pending

    async def _prune_expired_locked(self) -> None:
        expired = [
            user_id
            for user_id, pending in self._pending_by_user.items()
            if pending.is_expired(self._ttl_minutes)
        ]
        for user_id in expired:
            pending = self._pending_by_user.pop(user_id, None)
            if pending is not None:
                await self._reset_draft_locked(pending.case_id)

        now = datetime.now(timezone.utc)
        expired_case_ids = [
            case_id
            for case_id, draft in self._drafts_by_case.items()
            if draft.is_expired(self._draft_ttl_seconds, now)
        ]
        for case_id in expired_case_ids:
            await self._remove_draft_locked(case_id)

    def _copy_repo_to_draft(self, repo_root: Path) -> Path:
        temp_dir = Path(tempfile.mkdtemp(prefix="codi-draft-")).resolve()
        draft_root = temp_dir / repo_root.name
        _copy_repo_contents(repo_root, draft_root)
        return draft_root

    async def _reset_draft_locked(self, case_id: str) -> None:
        draft = self._drafts_by_case.get(case_id)
        if draft is None:
            return
        await asyncio.to_thread(self._sync_repo_to_draft, draft.repo_root, draft.draft_root)
        draft.claude_thread_id = None
        draft.last_activity_at = datetime.now(timezone.utc)

    async def _remove_draft_locked(self, case_id: str) -> None:
        draft = self._drafts_by_case.pop(case_id, None)
        if draft is None:
            return
        pending_user_ids = [
            user_id
            for user_id, pending in self._pending_by_user.items()
            if pending.case_id == case_id
        ]
        for user_id in pending_user_ids:
            self._pending_by_user.pop(user_id, None)
        await asyncio.to_thread(shutil.rmtree, draft.draft_root.parent, True)

    def _sync_repo_to_draft(self, repo_root: Path, draft_root: Path) -> None:
        if draft_root.exists() or draft_root.is_symlink():
            shutil.rmtree(draft_root, ignore_errors=True)
        _copy_repo_contents(repo_root, draft_root)

    def _collect_changes(
        self,
        repo_root: Path,
        draft_root: Path,
    ) -> tuple[tuple[FileChange, ...], str]:
        original_files = _collect_file_map(repo_root)
        staged_files = _collect_file_map(draft_root)
        changes: list[FileChange] = []
        diff_chunks: list[str] = []

        for relative_path in sorted(set(original_files) | set(staged_files)):
            original_path = original_files.get(relative_path)
            staged_path = staged_files.get(relative_path)
            if original_path is None and staged_path is not None:
                change = FileChange(
                    relative_path=relative_path,
                    change_type="added",
                    before_hash=None,
                    after_hash=_hash_path(staged_path),
                )
            elif original_path is not None and staged_path is None:
                change = FileChange(
                    relative_path=relative_path,
                    change_type="deleted",
                    before_hash=_hash_path(original_path),
                    after_hash=None,
                )
            elif original_path is not None and staged_path is not None:
                before_hash = _hash_path(original_path)
                after_hash = _hash_path(staged_path)
                if before_hash == after_hash:
                    continue
                change = FileChange(
                    relative_path=relative_path,
                    change_type="modified",
                    before_hash=before_hash,
                    after_hash=after_hash,
                )
            else:
                continue

            changes.append(change)
            diff_chunks.append(_build_diff_chunk(change, original_path, staged_path))

        diff_text = "\n\n".join(chunk for chunk in diff_chunks if chunk.strip()).strip()
        return tuple(changes), diff_text

    def _apply_pending(self, pending: PendingApproval) -> None:
        for change in pending.changes:
            target_path = pending.repo_root / change.relative_path
            current_hash = _hash_path(target_path) if target_path.exists() or target_path.is_symlink() else None
            if current_hash != change.before_hash:
                raise EditApprovalError(
                    f"File {change.relative_path} berubah sejak proposal dibuat. "
                    "Coba jalankan task lagi supaya Codi menyiapkan diff baru."
                )

        for change in pending.changes:
            target_path = pending.repo_root / change.relative_path
            staged_path = pending.draft_root / change.relative_path
            if change.change_type == "deleted":
                if target_path.is_symlink() or target_path.is_file():
                    target_path.unlink(missing_ok=True)
                elif target_path.is_dir():
                    shutil.rmtree(target_path, ignore_errors=True)
                continue

            target_path.parent.mkdir(parents=True, exist_ok=True)
            _copy_path(staged_path, target_path)


def rewrite_workspace_paths(text: str, original_root: Path, draft_root: Path) -> str:
    """Rewrite absolute workspace paths so Claude sees the current draft location."""

    return text.replace(str(original_root), str(draft_root))


def _copy_ignore_filter(directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in COPY_IGNORE_NAMES}


def _copy_repo_contents(repo_root: Path, draft_root: Path) -> None:
    draft_root.mkdir(parents=True, exist_ok=True)
    for relative_path, source_path in _collect_file_map(repo_root).items():
        target_path = draft_root / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        _copy_path(source_path, target_path)


def _collect_file_map(root: Path) -> dict[str, Path]:
    git_file_map = _collect_git_file_map(root)
    if git_file_map is not None:
        return git_file_map

    files: dict[str, Path] = {}
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = [dirname for dirname in dirnames if dirname not in DIFF_IGNORE_NAMES]
        current_dir = Path(dirpath)
        for filename in filenames:
            if filename in DIFF_IGNORE_NAMES:
                continue
            path = current_dir / filename
            relative_path = str(path.relative_to(root))
            files[relative_path] = path
    return files


def _collect_git_file_map(root: Path) -> dict[str, Path] | None:
    if not (root / ".git").exists():
        return None

    git_bin = shutil.which("git")
    if git_bin is None:
        return None

    try:
        completed = subprocess.run(
            [
                git_bin,
                "-C",
                str(root),
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            check=False,
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if completed.returncode != 0:
        return None

    files: dict[str, Path] = {}
    for raw_path in completed.stdout.split(b"\x00"):
        if not raw_path:
            continue
        relative_path = raw_path.decode("utf-8", errors="surrogateescape")
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            continue
        path = root / relative
        if not (path.exists() or path.is_symlink()):
            continue
        files[relative_path] = path
    return files


def _hash_path(path: Path) -> str:
    if path.is_symlink():
        target = os.readlink(path)
        return f"symlink:{target}"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _copy_path(source: Path, target: Path) -> None:
    if target.exists() or target.is_symlink():
        if target.is_symlink() or target.is_file():
            target.unlink(missing_ok=True)
        elif target.is_dir():
            shutil.rmtree(target, ignore_errors=True)

    if source.is_symlink():
        os.symlink(os.readlink(source), target)
        return

    if source.is_dir():
        shutil.copytree(source, target, symlinks=True)
        return

    shutil.copy2(source, target)


def _build_diff_chunk(
    change: FileChange,
    original_path: Path | None,
    staged_path: Path | None,
) -> str:
    if _is_binary_path(original_path) or _is_binary_path(staged_path):
        return f"# {change.change_type}: {change.relative_path} (binary or non-text)"

    before_lines = _read_text_lines(original_path)
    after_lines = _read_text_lines(staged_path)
    diff_lines = list(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=f"a/{change.relative_path}",
            tofile=f"b/{change.relative_path}",
            lineterm="",
        )
    )
    if diff_lines:
        return "\n".join(diff_lines)
    return f"# {change.change_type}: {change.relative_path}"


def _is_binary_path(path: Path | None) -> bool:
    if path is None or not path.exists():
        return False
    if path.is_symlink():
        return False
    with path.open("rb") as handle:
        sample = handle.read(2048)
    return b"\x00" in sample


def _read_text_lines(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    return text.splitlines(keepends=True)


def _summarize_output(text: str, max_length: int = 600) -> str:
    cleaned = " ".join(text.replace("```", "").replace("**", "").split())
    if len(cleaned) <= max_length:
        return cleaned
    return f"{cleaned[: max_length - 3].rstrip()}..."
