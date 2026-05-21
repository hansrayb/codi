"""Tests for desktop screenshot helpers."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

from core.desktop_screenshot import (
    DesktopScreenshotError,
    DesktopScreenshotRequest,
    DesktopScreenshotService,
    match_desktop_screenshot_query,
)


class DesktopScreenshotQueryTests(unittest.TestCase):
    """Validate natural-language detection for screenshot prompts."""

    def test_screenshot_query_is_detected(self) -> None:
        request = match_desktop_screenshot_query("kirim screenshot laptop sekarang")
        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.mode, "fullscreen")

        request = match_desktop_screenshot_query("ambil tangkapan layar desktop saat ini")
        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.mode, "fullscreen")

    def test_screenshot_mode_query_is_detected(self) -> None:
        request = match_desktop_screenshot_query("kirim screenshot jendela aktif sekarang")
        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.mode, "active_window")

        request = match_desktop_screenshot_query("ambil screenshot monitor aktif sekarang")
        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.mode, "current_monitor")

    def test_screenshot_summary_query_is_detected(self) -> None:
        request = match_desktop_screenshot_query(
            "kirim screenshot laptop sekarang dan ringkas isi layar"
        )
        self.assertIsNotNone(request)
        assert request is not None
        self.assertTrue(request.include_summary)

    def test_non_screenshot_query_is_not_detected(self) -> None:
        self.assertIsNone(match_desktop_screenshot_query("buat fitur screenshot di repo ini"))
        self.assertIsNone(match_desktop_screenshot_query("review dashboard payroll"))


class DesktopScreenshotServiceTests(unittest.IsolatedAsyncioTestCase):
    """Validate screenshot capture fallback behavior."""

    async def test_capture_uses_spectacle_when_available(self) -> None:
        service = DesktopScreenshotService()
        seen_args: list[str] = []

        def fake_run(args, **kwargs):
            seen_args.extend(args)
            output_path = Path(args[-1])
            output_path.write_bytes(b"png-data")
            return SimpleNamespace(returncode=0, stderr="", stdout="")

        with patch("core.desktop_screenshot._has_gui_session", return_value=True):
            with patch("core.desktop_screenshot.shutil.which", side_effect=lambda name: f"/usr/bin/{name}" if name == "spectacle" else None):
                with patch("core.desktop_screenshot.subprocess.run", side_effect=fake_run):
                    screenshot = await service.capture()

        self.assertEqual(screenshot.source, "spectacle")
        self.assertEqual(screenshot.mode, "fullscreen")
        self.assertEqual(screenshot.image_bytes, b"png-data")
        self.assertIn("--fullscreen", seen_args)

    async def test_capture_active_window_uses_correct_spectacle_flag(self) -> None:
        service = DesktopScreenshotService()
        seen_args: list[str] = []

        def fake_run(args, **kwargs):
            seen_args.extend(args)
            output_path = Path(args[-1])
            output_path.write_bytes(b"png-data")
            return SimpleNamespace(returncode=0, stderr="", stdout="")

        with patch("core.desktop_screenshot._has_gui_session", return_value=True):
            with patch("core.desktop_screenshot.shutil.which", side_effect=lambda name: f"/usr/bin/{name}" if name == "spectacle" else None):
                with patch("core.desktop_screenshot.subprocess.run", side_effect=fake_run):
                    screenshot = await service.capture(DesktopScreenshotRequest(mode="active_window"))

        self.assertEqual(screenshot.mode, "active_window")
        self.assertIn("--activewindow", seen_args)

    async def test_capture_includes_active_window_metadata_when_available(self) -> None:
        service = DesktopScreenshotService()

        def fake_run(args, **kwargs):
            if "spectacle" in args[0]:
                output_path = Path(args[-1])
                output_path.write_bytes(b"png-data")
                return SimpleNamespace(returncode=0, stderr="", stdout="")
            if any("activeOutputName" in arg for arg in args):
                return SimpleNamespace(returncode=0, stderr="", stdout="eDP-1\n")
            return SimpleNamespace(
                returncode=0,
                stderr="",
                stdout="caption: Dashboard Payroll\nresourceClass: firefox\ndesktopFile: firefox\n",
            )

        with patch("core.desktop_screenshot._has_gui_session", return_value=True):
            with patch("core.desktop_screenshot.shutil.which", side_effect=lambda name: f"/usr/bin/{name}"):
                with patch("core.desktop_screenshot.subprocess.run", side_effect=fake_run):
                    screenshot = await service.capture(DesktopScreenshotRequest(include_summary=True))

        assert screenshot.active_window is not None
        self.assertEqual(screenshot.active_window.caption, "Dashboard Payroll")
        self.assertEqual(screenshot.active_window.app_id, "firefox")
        self.assertEqual(screenshot.active_window.active_output_name, "eDP-1")

    async def test_capture_raises_without_gui_session(self) -> None:
        service = DesktopScreenshotService()

        with patch("core.desktop_screenshot._has_gui_session", return_value=False):
            with self.assertRaises(DesktopScreenshotError):
                await service.capture()


if __name__ == "__main__":
    unittest.main()
