"""Tests for Codi self-maintenance checks and restart scheduling."""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.self_maintenance import SelfCheckResult, SelfMaintenanceManager


class SelfMaintenanceManagerTests(unittest.IsolatedAsyncioTestCase):
    """Validate self-check and restart workflow helpers."""

    async def asyncSetUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.tempdir.name).resolve()
        (self.project_root / "main.py").write_text("print('ok')\n", encoding="utf-8")
        self.logger = SimpleNamespace(info=lambda *args, **kwargs: None, exception=lambda *args, **kwargs: None)
        self.manager = SelfMaintenanceManager(
            project_root=self.project_root,
            python_bin="/usr/bin/python3",
            entrypoint=self.project_root / "main.py",
            logger=self.logger,
            restart_delay_seconds=10,
        )

    async def asyncTearDown(self) -> None:
        self.manager.cancel_restart()
        self.tempdir.cleanup()
        os.environ.pop("CODI_RESTART_NOTICE_CHAT_ID", None)
        os.environ.pop("CODI_RESTART_NOTICE_TEXT", None)

    def test_is_self_repo(self) -> None:
        self.assertTrue(self.manager.is_self_repo(self.project_root))
        self.assertFalse(self.manager.is_self_repo(self.project_root / "other"))

    async def test_verify_self_update_reports_success(self) -> None:
        with patch.object(
            self.manager,
            "_run_command",
            side_effect=[("compile ok", True), ("tests ok", True)],
        ):
            result = await self.manager.verify_self_update()

        self.assertIsInstance(result, SelfCheckResult)
        self.assertTrue(result.ready_for_restart)
        self.assertEqual(result.compile_output, "compile ok")
        self.assertEqual(result.test_output, "tests ok")

    async def test_schedule_restart_is_idempotent(self) -> None:
        first = self.manager.schedule_restart()
        second = self.manager.schedule_restart()

        self.assertTrue(first)
        self.assertFalse(second)
        await asyncio.sleep(0)

    async def test_schedule_restart_can_store_notice_for_next_boot(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            scheduled = self.manager.schedule_restart(
                notify_chat_id=42,
                notify_text="Codi sudah aktif lagi.",
            )
            notice = self.manager.consume_restart_notice()

        self.assertTrue(scheduled)
        self.assertEqual(notice, (42, "Codi sudah aktif lagi."))

    async def test_consume_restart_notice_returns_none_without_pending_notice(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            notice = self.manager.consume_restart_notice()

        self.assertIsNone(notice)


if __name__ == "__main__":
    unittest.main()
