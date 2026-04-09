"""Session manager tests for limits, reuse, and resets."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from config import Settings
from core.session_manager import QueueFullError, SessionManager


class SessionManagerTests(unittest.IsolatedAsyncioTestCase):
    """Validate session acquisition and cleanup behavior."""

    async def asyncSetUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        workspace = Path(self.tempdir.name).resolve()
        self.settings = Settings(
            assistant_name="Codi",
            enable_desktop_actions=True,
            enable_local_shell=True,
            telegram_bot_token="token",
            allowed_user_ids=(1,),
            codex_bin="codex",
            codex_timeout=180,
            codex_reasoning_effort="medium",
            codex_work_dir=workspace,
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
            max_watched_repos_per_user=5,
            important_services=("codex-agent.service",),
            enable_device_registry=False,
            device_registry_path=workspace / "codi-devices.json",
            device_api_host="127.0.0.1",
            device_api_port=8787,
            device_api_shared_token=None,
            device_heartbeat_ttl_seconds=90,
        )
        self.manager = SessionManager(self.settings)

    async def asyncTearDown(self) -> None:
        self.tempdir.cleanup()

    async def test_reuse_returns_same_session(self) -> None:
        lease_one = await self.manager.acquire_session(
            user_id=1,
            role="builder",
            cwd=self.settings.codex_work_dir,
            prefer_reuse=False,
        )
        await lease_one.release("- first task")

        lease_two = await self.manager.acquire_session(
            user_id=1,
            role="builder",
            cwd=self.settings.codex_work_dir,
            prefer_reuse=True,
        )

        self.assertEqual(lease_one.session.session_id, lease_two.session.session_id)
        await lease_two.release("- second task")

    async def test_queue_full_raises(self) -> None:
        lease_one = await self.manager.acquire_session(
            user_id=1,
            role="builder",
            cwd=self.settings.codex_work_dir,
            prefer_reuse=False,
        )

        queued_task = asyncio.create_task(
            self.manager.acquire_session(
                user_id=1,
                role="builder",
                cwd=self.settings.codex_work_dir,
                prefer_reuse=True,
            )
        )
        await asyncio.sleep(0)

        with self.assertRaises(QueueFullError):
            await self.manager.acquire_session(
                user_id=1,
                role="builder",
                cwd=self.settings.codex_work_dir,
                prefer_reuse=True,
            )

        await lease_one.release("- queued test")
        lease_two = await queued_task
        await lease_two.release("- queued task")

    async def test_reset_clears_sessions(self) -> None:
        lease = await self.manager.acquire_session(
            user_id=1,
            role="reviewer",
            cwd=self.settings.codex_work_dir,
            prefer_reuse=False,
        )
        await lease.release("- summary")

        removed = await self.manager.reset_user(1)
        stats = await self.manager.get_stats(1)

        self.assertEqual(removed, 1)
        self.assertEqual(stats.active_sessions, 0)
        self.assertIsNone(stats.active_role)

    async def test_idle_session_with_same_role_is_reused(self) -> None:
        lease_one = await self.manager.acquire_session(
            user_id=1,
            role="debugger",
            cwd=self.settings.codex_work_dir,
            prefer_reuse=False,
        )
        await lease_one.release("- first debugger task")

        lease_two = await self.manager.acquire_session(
            user_id=1,
            role="debugger",
            cwd=self.settings.codex_work_dir,
            prefer_reuse=False,
        )

        self.assertEqual(lease_one.session.session_id, lease_two.session.session_id)
        await lease_two.release("- second debugger task")

    async def test_same_role_with_different_cwd_creates_new_session(self) -> None:
        other_repo = self.settings.codex_work_dir / "other-repo"
        other_repo.mkdir()

        lease_one = await self.manager.acquire_session(
            user_id=1,
            role="builder",
            cwd=self.settings.codex_work_dir,
            prefer_reuse=False,
        )
        await lease_one.release("- first repo task")

        lease_two = await self.manager.acquire_session(
            user_id=1,
            role="builder",
            cwd=other_repo,
            prefer_reuse=True,
        )

        self.assertNotEqual(lease_one.session.session_id, lease_two.session.session_id)
        self.assertEqual(lease_two.session.cwd, str(other_repo))
        await lease_two.release("- second repo task")

    async def test_same_repo_role_but_different_case_creates_new_session(self) -> None:
        lease_one = await self.manager.acquire_session(
            user_id=1,
            role="builder",
            cwd=self.settings.codex_work_dir,
            prefer_reuse=False,
            case_id="c-01",
        )
        await lease_one.release("- first case task")

        lease_two = await self.manager.acquire_session(
            user_id=1,
            role="builder",
            cwd=self.settings.codex_work_dir,
            prefer_reuse=True,
            case_id="c-02",
        )

        self.assertNotEqual(lease_one.session.session_id, lease_two.session.session_id)
        self.assertEqual(lease_two.session.case_id, "c-02")
        await lease_two.release("- second case task")

    async def test_close_case_sessions_removes_related_sessions(self) -> None:
        lease_one = await self.manager.acquire_session(
            user_id=1,
            role="builder",
            cwd=self.settings.codex_work_dir,
            prefer_reuse=False,
            case_id="c-01",
        )
        await lease_one.release("- first case task")
        lease_two = await self.manager.acquire_session(
            user_id=1,
            role="reviewer",
            cwd=self.settings.codex_work_dir,
            prefer_reuse=False,
            case_id="c-01",
        )
        await lease_two.release("- review case task")

        closed = await self.manager.close_case_sessions("c-01")
        stats = await self.manager.get_stats(1)

        self.assertEqual(closed, 2)
        self.assertEqual(stats.active_sessions, 0)


if __name__ == "__main__":
    unittest.main()
