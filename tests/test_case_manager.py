"""Case manager tests for multi-prompt work context."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from config import Settings
from core.case_manager import CaseManager


class CaseManagerTests(unittest.IsolatedAsyncioTestCase):
    """Validate case reuse, close, and reset behavior."""

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
        self.manager = CaseManager(self.settings)
        self.repo_a = workspace / "repo-a"
        self.repo_b = workspace / "repo-b"
        self.repo_a.mkdir()
        self.repo_b.mkdir()

    async def asyncTearDown(self) -> None:
        self.tempdir.cleanup()

    def test_classify_done_message(self) -> None:
        self.assertEqual(self.manager.classify_control_message("selesai"), "close_case")
        self.assertEqual(self.manager.classify_control_message("close case"), "close_case")
        self.assertIsNone(self.manager.classify_control_message("selesaikan bug login"))

    async def test_reuse_same_repo_case(self) -> None:
        case_one, created_one = await self.manager.open_or_reuse_case(
            1,
            self.repo_a,
            prompt="cek repo A",
            role="reviewer",
        )
        case_two, created_two = await self.manager.open_or_reuse_case(
            1,
            self.repo_a,
            prompt="edit README di repo ini",
            role="builder",
        )

        self.assertTrue(created_one)
        self.assertFalse(created_two)
        self.assertEqual(case_one.case_id, case_two.case_id)
        self.assertEqual(case_two.last_role, "builder")

    async def test_new_repo_opens_new_case(self) -> None:
        case_one, _ = await self.manager.open_or_reuse_case(
            1,
            self.repo_a,
            prompt="cek repo A",
            role="reviewer",
        )
        case_two, created_two = await self.manager.open_or_reuse_case(
            1,
            self.repo_b,
            prompt="cek repo B",
            role="reviewer",
        )

        self.assertTrue(created_two)
        self.assertNotEqual(case_one.case_id, case_two.case_id)

    async def test_close_active_case_marks_it_closed(self) -> None:
        case, _ = await self.manager.open_or_reuse_case(
            1,
            self.repo_a,
            prompt="cek repo A",
            role="reviewer",
        )

        closed = await self.manager.close_active_case(1)
        stats = await self.manager.get_stats(1)

        self.assertIsNotNone(closed)
        assert closed is not None
        self.assertEqual(closed.case_id, case.case_id)
        self.assertEqual(closed.status, "closed")
        self.assertIsNone(stats.active_case_id)

    async def test_update_case_summary(self) -> None:
        case, _ = await self.manager.open_or_reuse_case(
            1,
            self.repo_a,
            prompt="cek repo A",
            role="reviewer",
        )

        await self.manager.update_case(case.case_id, role="builder", prompt="edit README")
        active = await self.manager.get_active_case(1)

        self.assertIsNotNone(active)
        assert active is not None
        self.assertIn("edit README", active.summary)
        self.assertEqual(active.last_role, "builder")


if __name__ == "__main__":
    unittest.main()
