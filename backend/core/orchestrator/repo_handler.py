"""Repo-watch handler mixin for the Codi orchestrator."""

from __future__ import annotations

from pathlib import Path

from core.repo_resolver import RepoResolution, RepoResolverError
from core.repo_watch import RepoWatchError
from models.result import MessagePayload
from utils.formatter import format_error_payload


class RepoHandlerMixin:
    """Mixin providing repo-watch control and repo-list queries."""

    def list_indexed_repos(self) -> tuple:
        """Return all currently indexed repos sorted by name."""
        return self._repo_resolver._get_indexed_repos()

    def list_business_repos(self) -> tuple:
        """Return indexed repos that are within business_allowed_dirs."""
        return tuple(
            r for r in self._repo_resolver._get_indexed_repos()
            if self._settings.is_business_dir(r.root)
        )

    async def select_repo(self, user_id: int, repo_path: str) -> MessagePayload:
        """Switch the active repo context to the given absolute path."""
        return await self.try_handle_direct_query(user_id, f"pakai repo {repo_path}")

    async def try_handle_repo_watch_message(
        self,
        user_id: int,
        chat_id: int,
        text: str,
    ) -> MessagePayload | None:
        """Handle repo watch control messages without invoking Claude."""

        action = self._repo_watch_manager.classify_message(text)
        if action is None:
            return None

        if action == "list":
            return await self._repo_watch_manager.list_watches(
                user_id=user_id,
                assistant_name=self._settings.assistant_name,
            )

        active_case = await self._case_manager.get_active_case(user_id)
        active_session = await self._session_manager.get_active_session(user_id)
        repo_resolution: RepoResolution | None = None
        try:
            repo_resolution = self._repo_resolver.resolve(
                text,
                active_session,
                active_case,
            )
        except RepoResolverError as exc:
            return format_error_payload(
                str(exc),
                assistant_name=self._settings.assistant_name,
            )

        try:
            if action == "start":
                return await self._repo_watch_manager.add_watch(
                    user_id=user_id,
                    chat_id=chat_id,
                    repo_root=repo_resolution.root,
                    repo_label=repo_resolution.label,
                    assistant_name=self._settings.assistant_name,
                )

            target_root: Path | None = None
            if (
                repo_resolution.explicit
                or repo_resolution.used_active_case
                or repo_resolution.used_active_session
            ):
                target_root = repo_resolution.root
            return await self._repo_watch_manager.remove_watch(
                user_id=user_id,
                repo_root=target_root,
                assistant_name=self._settings.assistant_name,
            )
        except RepoWatchError as exc:
            return format_error_payload(
                str(exc),
                assistant_name=self._settings.assistant_name,
            )
