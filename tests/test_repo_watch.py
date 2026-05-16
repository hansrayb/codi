"""Tests for repo watch registration and change detection."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from config import Settings
from core.repo_watch import RepoWatchManager
from models.watch import RepoWatchSnapshot


def _snapshot(branch: str, head: str, *status_lines: str) -> RepoWatchSnapshot:
    joined = "\n".join(status_lines)
    return RepoWatchSnapshot(
        branch=branch,
        head=head,
        status_fingerprint=joined or "clean",
        status_count=len(status_lines),
        status_preview=tuple(status_lines[:6]),
    )


class RepoWatchManagerTests(unittest.IsolatedAsyncioTestCase):
    """Validate watch registration, listing, and alerts."""

    async def asyncSetUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        workspace = Path(self.tempdir.name).resolve()
        self.settings = Settings(
            assistant_name="Codi",
            enable_desktop_actions=True,
            enable_local_shell=True,
            telegram_bot_token="token",
            allowed_user_ids=(1,),
            admin_user_ids=(),
            viewer_user_ids=(),
            business_user_ids=(),
            business_allowed_dirs=(),
            business_database_paths=(),
            business_database_urls=(),
            ai_backend="codex",
            codex_bin="codex",
            claude_timeout=180,
            codex_reasoning_effort="medium",
            codex_write_sandbox_mode="workspace-write",
            claude_work_dir=workspace,
            claude_bin="claude",
            claude_model="claude-sonnet-4-6",
            allowed_work_dirs=(workspace,),
            default_role="general",
            max_active_sessions=4,
            max_sessions_per_user=3,
            session_idle_ttl_minutes=60,
            max_queue_per_session=1,
            max_output_length=3000,
            local_shell_timeout=120,
            log_level="INFO",
            log_file=None,
            max_requests_per_minute=5,
            repo_watch_poll_seconds=30,
            service_watch_poll_seconds=30,
            max_watched_repos_per_user=5,
            important_services=("codi.service",),
            important_pm2_apps=(),
            alert_targets_path=workspace / "codi-alert-targets.json",
            enable_device_registry=False,
            device_registry_path=workspace / "codi-devices.json",
            device_api_host="127.0.0.1",
            device_api_port=8787,
            device_api_shared_token=None,
            device_heartbeat_ttl_seconds=90,
        )
        self.repo = workspace / "repo-a"
        self.repo.mkdir()
        self.snapshots = {
            self.repo.resolve(): _snapshot("main", "abc123"),
        }
        self.manager = RepoWatchManager(
            self.settings,
            snapshot_reader=lambda repo_root: self.snapshots[repo_root.resolve()],
        )

    async def asyncTearDown(self) -> None:
        self.tempdir.cleanup()

    def test_classify_messages(self) -> None:
        self.assertEqual(self.manager.classify_message("pantau repo ini"), "start")
        self.assertEqual(self.manager.classify_message("stop pantau repo ini"), "stop")
        self.assertEqual(self.manager.classify_message("repo yang dipantau apa"), "list")
        self.assertIsNone(self.manager.classify_message("review repo ini"))
        self.assertIsNone(self.manager.classify_message("review repo watch feature"))

    async def test_add_watch_and_list(self) -> None:
        payload = await self.manager.add_watch(
            user_id=1,
            chat_id=99,
            repo_root=self.repo,
            repo_label="repo-a",
            assistant_name="Codi",
        )
        listing = await self.manager.list_watches(user_id=1, assistant_name="Codi")
        stats = await self.manager.get_stats(1)

        self.assertIn("mulai memantau repo ini", payload.text)
        self.assertIn("repo-a", listing.text)
        self.assertEqual(stats.watched_repos, 1)

    async def test_remove_watch_without_explicit_repo_when_single_watch(self) -> None:
        await self.manager.add_watch(
            user_id=1,
            chat_id=99,
            repo_root=self.repo,
            repo_label="repo-a",
            assistant_name="Codi",
        )

        payload = await self.manager.remove_watch(user_id=1, assistant_name="Codi")
        stats = await self.manager.get_stats(1)

        self.assertIn("menghentikan pantauan", payload.text)
        self.assertEqual(stats.watched_repos, 0)

    async def test_scan_once_emits_alert_when_head_changes(self) -> None:
        await self.manager.add_watch(
            user_id=1,
            chat_id=99,
            repo_root=self.repo,
            repo_label="repo-a",
            assistant_name="Codi",
        )
        self.snapshots[self.repo.resolve()] = _snapshot("main", "def456", " M README.md")

        alerts = await self.manager.scan_once(assistant_name="Codi")

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].chat_id, 99)
        self.assertIn("HEAD berubah", alerts[0].payload.text)
        self.assertIn("Working tree sekarang kotor", alerts[0].payload.text)

    async def test_scan_once_without_changes_emits_no_alert(self) -> None:
        await self.manager.add_watch(
            user_id=1,
            chat_id=99,
            repo_root=self.repo,
            repo_label="repo-a",
            assistant_name="Codi",
        )

        alerts = await self.manager.scan_once(assistant_name="Codi")

        self.assertEqual(alerts, ())


if __name__ == "__main__":
    unittest.main()
