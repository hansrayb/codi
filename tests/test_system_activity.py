"""Tests for local host-observability helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from core.desktop_actions import TrackedDesktopProcess
from core.system_activity import (
    SystemActivityInspector,
    SystemActivityRequest,
    match_system_activity_query,
)


class SystemActivityQueryTests(unittest.TestCase):
    """Validate natural-language detection for direct activity queries."""

    def test_running_apps_query_is_detected(self) -> None:
        request = match_system_activity_query(
            "Codi laptop ku sedang menjalankan aplikasi apa"
        )
        self.assertIsNotNone(request)
        assert request is not None
        self.assertTrue(request.include_processes)
        self.assertFalse(request.include_logs)

    def test_log_query_is_detected(self) -> None:
        request = match_system_activity_query("tampilkan log Codi terbaru dengan detail")
        self.assertIsNotNone(request)
        assert request is not None
        self.assertTrue(request.include_logs)
        self.assertFalse(request.include_processes)
        self.assertTrue(request.detail_hint)

    def test_generic_repo_log_query_is_not_intercepted(self) -> None:
        request = match_system_activity_query("cek log error service di repo ini")
        self.assertIsNone(request)


class SystemActivityInspectorTests(unittest.IsolatedAsyncioTestCase):
    """Validate process grouping and log collection."""

    async def test_inspector_groups_desktop_background_and_logs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "codi.log"
            log_path.write_text(
                "line 1\nline 2\n2026-04-05 10:00:00 | INFO | bot started\n",
                encoding="utf-8",
            )
            desktop_manager = AsyncMock()
            desktop_manager.get_tracked_processes.return_value = (
                TrackedDesktopProcess(
                    action_id="libreoffice_writer",
                    label="LibreOffice Writer",
                    process_group=200,
                ),
            )
            inspector = SystemActivityInspector(
                log_file=str(log_path),
                desktop_action_manager=desktop_manager,
                process_limit=4,
                log_lines=5,
            )
            fake_processes = [
                SimpleNamespace(
                    info={
                        "pid": 200,
                        "name": "libreoffice",
                        "username": "hans",
                        "cmdline": ["/usr/bin/libreoffice", "--writer"],
                        "terminal": None,
                        "status": "sleeping",
                        "create_time": 1000.0,
                        "memory_info": SimpleNamespace(rss=220 * 1024 * 1024),
                    }
                ),
                SimpleNamespace(
                    info={
                        "pid": 201,
                        "name": "code",
                        "username": "hans",
                        "cmdline": ["/usr/share/code/code", "."],
                        "terminal": None,
                        "status": "running",
                        "create_time": 1200.0,
                        "memory_info": SimpleNamespace(rss=510 * 1024 * 1024),
                    }
                ),
                SimpleNamespace(
                    info={
                        "pid": 301,
                        "name": "postgres",
                        "username": "postgres",
                        "cmdline": ["/usr/bin/postgres", "-D", "/var/lib/pgsql/data"],
                        "terminal": None,
                        "status": "sleeping",
                        "create_time": 900.0,
                        "memory_info": SimpleNamespace(rss=310 * 1024 * 1024),
                    }
                ),
                SimpleNamespace(
                    info={
                        "pid": 401,
                        "name": "python",
                        "username": "hans",
                        "cmdline": ["python", "main.py"],
                        "terminal": "pts/1",
                        "status": "running",
                        "create_time": 1300.0,
                        "memory_info": SimpleNamespace(rss=80 * 1024 * 1024),
                    }
                ),
            ]

            with patch("core.system_activity.getpass.getuser", return_value="hans"):
                with patch("core.system_activity.psutil.process_iter", return_value=fake_processes):
                    with patch(
                        "core.system_activity.psutil.virtual_memory",
                        return_value=SimpleNamespace(
                            used=4 * 1024 * 1024 * 1024,
                            total=8 * 1024 * 1024 * 1024,
                            percent=50.0,
                        ),
                    ):
                        with patch(
                            "core.system_activity.psutil.swap_memory",
                            return_value=SimpleNamespace(percent=12.0),
                        ):
                            with patch(
                                "core.system_activity.psutil.cpu_percent",
                                return_value=18.0,
                            ):
                                with patch(
                                    "core.system_activity.psutil.boot_time",
                                    return_value=100.0,
                                ):
                                    report = await inspector.inspect(
                                        SystemActivityRequest(
                                            include_processes=True,
                                            include_logs=True,
                                            detail_hint=False,
                                        )
                                    )

        self.assertGreaterEqual(len(report.desktop_apps), 2)
        self.assertEqual(report.desktop_apps[0].label, "LibreOffice Writer")
        self.assertTrue(report.desktop_apps[0].tracked_by_codi)
        self.assertEqual(report.desktop_apps[1].label, "Code")
        self.assertEqual(report.background_apps[0].label, "Postgres")
        self.assertIsNotNone(report.logs)
        assert report.logs is not None
        self.assertTrue(report.logs.source.startswith("file:"))
        self.assertIn("bot started", report.logs.lines[-1])


if __name__ == "__main__":
    unittest.main()
