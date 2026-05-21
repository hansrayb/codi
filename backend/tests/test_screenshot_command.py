"""Tests for the Telegram screenshot command."""

from __future__ import annotations

import unittest

from handlers.screenshot import parse_screenshot_command_args


class ScreenshotCommandTests(unittest.TestCase):
    """Validate parsing for optional `/screenshot` arguments."""

    def test_default_screenshot_command_uses_fullscreen(self) -> None:
        request = parse_screenshot_command_args("")

        self.assertEqual(request.mode, "fullscreen")
        self.assertFalse(request.include_summary)

    def test_screenshot_command_supports_monitor_mode(self) -> None:
        request = parse_screenshot_command_args("monitor")

        self.assertEqual(request.mode, "current_monitor")

    def test_screenshot_command_supports_window_mode(self) -> None:
        request = parse_screenshot_command_args("jendela aktif")

        self.assertEqual(request.mode, "active_window")

    def test_screenshot_command_supports_summary(self) -> None:
        request = parse_screenshot_command_args("ringkas isi layar")

        self.assertEqual(request.mode, "fullscreen")
        self.assertTrue(request.include_summary)


if __name__ == "__main__":
    unittest.main()
