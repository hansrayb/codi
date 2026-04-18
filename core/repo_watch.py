"""In-memory repository watch manager with git-based change detection."""

from __future__ import annotations

import asyncio
import hashlib
import itertools
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from config import Settings
from models.result import MessagePayload
from models.watch import RepoWatch, RepoWatchSnapshot, RepoWatchStats

WATCH_LIST_HINTS = (
    "list repo watch",
    "repo yang dipantau",
    "repo dipantau",
    "watch aktif",
    "pantauan repo",
)
WATCH_START_HINTS = ("pantau", "watch", "monitor")
WATCH_STOP_HINTS = (
    "berhenti pantau",
    "berhenti watch",
    "stop pantau",
    "stop watch",
    "unwatch",
    "hapus pantauan",
    "jangan pantau",
)
WATCH_SCOPE_HINTS = ("repo", "project", "proyek", "folder", "workspace")
WATCH_START_PATTERN = re.compile(
    r"^\s*(?:(?:tolong|coba|please|bisa)\s+)?(?:(?:mulai)\s+)?(?:pantau|watch|monitor)\b",
    re.IGNORECASE,
)
WATCH_STOP_PATTERN = re.compile(
    r"^\s*(?:(?:tolong|coba|please|bisa)\s+)?(?:berhenti\s+pantau|berhenti\s+watch|stop\s+pantau|stop\s+watch|unwatch|hapus\s+pantauan|jangan\s+pantau)\b",
    re.IGNORECASE,
)


class RepoWatchError(RuntimeError):
    """Raised when a repo watch operation cannot proceed."""


@dataclass(frozen=True)
class RepoWatchAlert:
    """An outbound Telegram alert produced by the watch loop."""

    user_id: int
    chat_id: int
    payload: MessagePayload


class RepoWatchManager:
    """Manage repo watch registrations and periodic git-state snapshots."""

    def __init__(
        self,
        settings: Settings,
        *,
        snapshot_reader=None,
    ) -> None:
        self._settings = settings
        self._snapshot_reader = snapshot_reader or _read_git_snapshot
        self._watches: dict[str, RepoWatch] = {}
        self._watch_ids_by_user: dict[int, set[str]] = {}
        self._counter = itertools.count(1)
        self._lock = asyncio.Lock()

    @staticmethod
    def classify_message(text: str) -> str | None:
        """Classify a natural-language repo watch request."""

        normalized = " ".join(text.strip().lower().split())
        if not normalized:
            return None
        if any(hint in normalized for hint in WATCH_LIST_HINTS):
            return "list"
        if WATCH_STOP_PATTERN.search(normalized):
            return "stop"
        if WATCH_START_PATTERN.search(normalized) and any(
            scope in normalized for scope in WATCH_SCOPE_HINTS
        ):
            return "start"
        return None

    async def add_watch(
        self,
        *,
        user_id: int,
        chat_id: int,
        repo_root: Path,
        repo_label: str,
        assistant_name: str,
    ) -> MessagePayload:
        """Start watching a repo for git changes."""

        resolved_root = repo_root.resolve()
        snapshot = await asyncio.to_thread(self._snapshot_reader, resolved_root)
        async with self._lock:
            watch_ids = self._watch_ids_by_user.setdefault(user_id, set())
            for watch_id in watch_ids:
                existing = self._watches.get(watch_id)
                if existing is not None and Path(existing.repo_root) == resolved_root:
                    return MessagePayload(
                        text=(
                            f"<b>{escape(assistant_name)} sudah memantau repo ini.</b>\n\n"
                            f"Repo: <code>{escape(str(resolved_root))}</code>\n"
                            "Saya akan kabari kalau branch, HEAD, atau status kerja berubah."
                        ),
                        parse_mode="HTML",
                    )

            if len(watch_ids) >= self._settings.max_watched_repos_per_user:
                raise RepoWatchError(
                    f"Batas pantauan repo kamu sudah penuh. Maksimum {self._settings.max_watched_repos_per_user} repo."
                )

            watch_id = f"w-{next(self._counter):02d}"
            watch = RepoWatch(
                watch_id=watch_id,
                owner_user_id=user_id,
                chat_id=chat_id,
                repo_root=str(resolved_root),
                repo_label=repo_label,
                snapshot=snapshot,
            )
            self._watches[watch_id] = watch
            watch_ids.add(watch_id)

        dirty_text = (
            f"Status awal: {snapshot.status_count} perubahan lokal."
            if snapshot.is_dirty
            else "Status awal: working tree bersih."
        )
        return MessagePayload(
            text=(
                f"<b>{escape(assistant_name)} mulai memantau repo ini.</b>\n\n"
                f"Repo: <code>{escape(str(resolved_root))}</code>\n"
                f"Branch: <code>{escape(snapshot.branch)}</code>\n"
                f"HEAD: <code>{escape(snapshot.head)}</code>\n"
                f"{escape(dirty_text)}"
            ),
            parse_mode="HTML",
        )

    async def remove_watch(
        self,
        *,
        user_id: int,
        assistant_name: str,
        repo_root: Path | None = None,
    ) -> MessagePayload:
        """Stop watching a repo."""

        async with self._lock:
            watch_ids = list(self._watch_ids_by_user.get(user_id, set()))
            if not watch_ids:
                raise RepoWatchError("Belum ada repo yang sedang dipantau.")

            target: RepoWatch | None = None
            if repo_root is not None:
                resolved_root = repo_root.resolve()
                for watch_id in watch_ids:
                    watch = self._watches.get(watch_id)
                    if watch is not None and Path(watch.repo_root) == resolved_root:
                        target = watch
                        break
                if target is None:
                    raise RepoWatchError(f"Saya belum memantau repo {resolved_root}.")
            elif len(watch_ids) == 1:
                target = self._watches.get(watch_ids[0])
            else:
                raise RepoWatchError(
                    "Saya memantau lebih dari satu repo. Sebutkan repo yang ingin dihentikan, misalnya `stop pantau repo ini`."
                )

            if target is None:
                raise RepoWatchError("Repo pantauan itu tidak lagi tersedia di memori Codi.")

            self._watches.pop(target.watch_id, None)
            user_watches = self._watch_ids_by_user.get(user_id)
            if user_watches is not None:
                user_watches.discard(target.watch_id)
                if not user_watches:
                    self._watch_ids_by_user.pop(user_id, None)

        return MessagePayload(
            text=(
                f"<b>{escape(assistant_name)} menghentikan pantauan repo ini.</b>\n\n"
                f"Repo: <code>{escape(target.repo_root)}</code>"
            ),
            parse_mode="HTML",
        )

    async def list_watches(self, *, user_id: int, assistant_name: str) -> MessagePayload:
        """List the repos currently watched for the user."""

        async with self._lock:
            watches = sorted(
                (
                    self._watches[watch_id]
                    for watch_id in self._watch_ids_by_user.get(user_id, set())
                    if watch_id in self._watches
                ),
                key=lambda watch: watch.repo_label.lower(),
            )

        if not watches:
            return MessagePayload(
                text=f"<b>{escape(assistant_name)}</b>\n\nBelum ada repo yang sedang dipantau.",
                parse_mode="HTML",
            )

        lines = [f"<b>{escape(assistant_name)} sedang memantau repo ini:</b>", ""]
        for watch in watches:
            lines.append(
                f"- <b>{escape(watch.repo_label)}</b> <code>{escape(watch.repo_root)}</code>"
            )
        return MessagePayload(text="\n".join(lines), parse_mode="HTML")

    async def get_stats(self, user_id: int) -> RepoWatchStats:
        """Return a lightweight status summary for watched repos."""

        async with self._lock:
            watches = [
                self._watches[watch_id]
                for watch_id in self._watch_ids_by_user.get(user_id, set())
                if watch_id in self._watches
            ]
        labels = tuple(sorted(watch.repo_label for watch in watches))
        return RepoWatchStats(
            watched_repos=len(watches),
            watched_labels=labels,
        )

    async def scan_once(self, *, assistant_name: str) -> tuple[RepoWatchAlert, ...]:
        """Poll all watched repos once and return any outbound alerts."""

        async with self._lock:
            watches = tuple(self._watches.values())

        alerts: list[RepoWatchAlert] = []
        for watch in watches:
            try:
                current_snapshot = await asyncio.to_thread(
                    self._snapshot_reader,
                    Path(watch.repo_root),
                )
            except RepoWatchError as exc:
                await self._remove_watch_by_id(watch.watch_id)
                alerts.append(
                    RepoWatchAlert(
                        user_id=watch.owner_user_id,
                        chat_id=watch.chat_id,
                        payload=MessagePayload(
                            text=(
                                f"<b>{escape(assistant_name)} menghentikan pantauan repo.</b>\n\n"
                                f"Repo: <code>{escape(watch.repo_root)}</code>\n"
                                f"Alasan: {escape(str(exc))}"
                            ),
                            parse_mode="HTML",
                        ),
                    )
                )
                continue

            payload = _build_repo_watch_alert(
                assistant_name=assistant_name,
                repo_root=watch.repo_root,
                repo_label=watch.repo_label,
                previous=watch.snapshot,
                current=current_snapshot,
            )
            await self._update_snapshot(watch.watch_id, current_snapshot)
            if payload is None:
                continue
            alerts.append(
                RepoWatchAlert(
                    user_id=watch.owner_user_id,
                    chat_id=watch.chat_id,
                    payload=payload,
                )
            )

        return tuple(alerts)

    async def _update_snapshot(self, watch_id: str, snapshot: RepoWatchSnapshot) -> None:
        async with self._lock:
            watch = self._watches.get(watch_id)
            if watch is None:
                return
            watch.snapshot = snapshot
            watch.last_checked_at = _utcnow()

    async def _remove_watch_by_id(self, watch_id: str) -> None:
        async with self._lock:
            watch = self._watches.pop(watch_id, None)
            if watch is None:
                return
            user_watches = self._watch_ids_by_user.get(watch.owner_user_id)
            if user_watches is not None:
                user_watches.discard(watch_id)
                if not user_watches:
                    self._watch_ids_by_user.pop(watch.owner_user_id, None)


def _read_git_snapshot(repo_root: Path) -> RepoWatchSnapshot:
    repo_root = repo_root.resolve()
    if not repo_root.exists() or not repo_root.is_dir():
        raise RepoWatchError(f"Repo {repo_root} tidak bisa diakses lagi.")
    if not _run_git(repo_root, "rev-parse", "--is-inside-work-tree").strip() == "true":
        raise RepoWatchError(f"{repo_root} bukan repo Git yang valid untuk dipantau.")

    branch = _safe_git_output(repo_root, "rev-parse", "--abbrev-ref", "HEAD") or "(detached)"
    head = _safe_git_output(repo_root, "rev-parse", "--short", "HEAD") or "(belum ada commit)"
    status_output = _run_git(
        repo_root,
        "status",
        "--short",
        "--untracked-files=all",
    )
    status_lines = tuple(
        line.rstrip()
        for line in status_output.splitlines()
        if line.strip()
    )
    fingerprint = hashlib.sha1("\n".join(status_lines).encode("utf-8")).hexdigest()
    return RepoWatchSnapshot(
        branch=branch,
        head=head,
        status_fingerprint=fingerprint,
        status_count=len(status_lines),
        status_preview=status_lines[:6],
    )


def _run_git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=8,
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        raise RepoWatchError(stderr or f"Perintah git gagal di {repo_root}.")
    return completed.stdout.strip()


def _safe_git_output(repo_root: Path, *args: str) -> str | None:
    try:
        return _run_git(repo_root, *args)
    except RepoWatchError:
        return None


def _build_repo_watch_alert(
    *,
    assistant_name: str,
    repo_root: str,
    repo_label: str,
    previous: RepoWatchSnapshot,
    current: RepoWatchSnapshot,
) -> MessagePayload | None:
    changes: list[str] = []
    if previous.branch != current.branch:
        changes.append(
            f"Branch berubah: <code>{escape(previous.branch)}</code> -> <code>{escape(current.branch)}</code>"
        )
    if previous.head != current.head:
        changes.append(
            f"HEAD berubah: <code>{escape(previous.head)}</code> -> <code>{escape(current.head)}</code>"
        )
    if previous.status_fingerprint != current.status_fingerprint:
        if not previous.is_dirty and current.is_dirty:
            changes.append(
                f"Working tree sekarang kotor: {current.status_count} item berubah."
            )
        elif previous.is_dirty and not current.is_dirty:
            changes.append("Working tree kembali bersih.")
        else:
            changes.append(
                "Status kerja lokal berubah: "
                f"{previous.status_count} -> {current.status_count} item."
            )

    if not changes:
        return None

    lines = [
        f"<b>{escape(assistant_name)} mendeteksi perubahan repo yang dipantau.</b>",
        "",
        f"Repo: <b>{escape(repo_label)}</b>",
        f"Path: <code>{escape(repo_root)}</code>",
        "",
    ]
    lines.extend(f"- {change}" for change in changes)
    if current.status_preview:
        lines.extend(
            (
                "",
                "<b>Cuplikan status saat ini:</b>",
                f"<pre>{escape(chr(10).join(current.status_preview))}</pre>",
            )
        )
    return MessagePayload(text="\n".join(lines), parse_mode="HTML")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
