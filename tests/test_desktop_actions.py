"""Desktop action tests for explicit GUI app launch support."""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import ANY, AsyncMock, patch

from core.desktop_actions import (
    DesktopActionError,
    DesktopActionManager,
    DesktopAppCatalog,
    FIREFOX_ACTION,
    TrackedDesktopProcess,
    WRITER_ACTION,
    match_desktop_action,
)


class DesktopActionTests(unittest.IsolatedAsyncioTestCase):
    """Validate matching and safety checks for desktop actions."""

    def test_explicit_writer_open_prompt_matches(self) -> None:
        request = match_desktop_action("buka libreoffice writer")
        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.action.action_id, WRITER_ACTION.action_id)
        self.assertEqual(request.operation, "open")

    def test_explicit_writer_close_prompt_matches(self) -> None:
        request = match_desktop_action("tutup libreoffice writer")
        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.action.action_id, WRITER_ACTION.action_id)
        self.assertEqual(request.operation, "close")

    def test_firefox_aliases_match_profile(self) -> None:
        firefox_request = match_desktop_action("buka firefox")
        mozilla_request = match_desktop_action("buka mozilla")

        self.assertIsNotNone(firefox_request)
        self.assertIsNotNone(mozilla_request)
        assert firefox_request is not None
        assert mozilla_request is not None
        self.assertEqual(firefox_request.action.action_id, FIREFOX_ACTION.action_id)
        self.assertEqual(mozilla_request.action.action_id, FIREFOX_ACTION.action_id)

    def test_generic_catalog_matches_desktop_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            desktop_dir = Path(temp_dir)
            (desktop_dir / "code.desktop").write_text(
                "\n".join(
                    (
                        "[Desktop Entry]",
                        "Type=Application",
                        "Name=Visual Studio Code",
                        "Exec=code --unity-launch %F",
                    )
                ),
                encoding="utf-8",
            )
            catalog = DesktopAppCatalog((desktop_dir,), refresh_interval_seconds=999)

            request = match_desktop_action("buka code", catalog=catalog)

        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual(request.action.action_id, "desktop:code.desktop")
        self.assertEqual(request.action.command, ("code", "--unity-launch"))

    def test_partial_word_does_not_match_writer_alias(self) -> None:
        self.assertIsNone(match_desktop_action("buka ghostwriter"))
        self.assertIsNone(match_desktop_action("buka typewriter app"))

    def test_non_desktop_prompt_does_not_match(self) -> None:
        request = match_desktop_action("review writer module ini")
        self.assertIsNone(request)

    async def test_launch_requires_gui_session(self) -> None:
        manager = DesktopActionManager()
        request = match_desktop_action("buka libreoffice writer")
        assert request is not None

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(DesktopActionError):
                await manager.perform(request)

    async def test_firefox_launch_uses_new_window_command(self) -> None:
        manager = DesktopActionManager()
        request = match_desktop_action("buka mozilla")
        assert request is not None

        process = AsyncMock()
        process.pid = 4545
        process.stderr.read = AsyncMock(return_value=b"")
        process.wait = AsyncMock(return_value=None)

        async def fake_exec(*args, **kwargs):
            return process

        async def fake_wait_for(awaitable, timeout):
            await awaitable
            raise asyncio.TimeoutError

        with patch("core.desktop_actions.shutil.which", return_value="/usr/bin/firefox"):
            with patch.dict(
                os.environ,
                {
                    "DISPLAY": ":0",
                    "WAYLAND_DISPLAY": "wayland-0",
                    "XDG_RUNTIME_DIR": "/run/user/1000",
                },
                clear=True,
            ):
                with patch(
                    "core.desktop_actions.asyncio.create_subprocess_exec",
                    side_effect=fake_exec,
                ) as create_exec:
                    with patch(
                        "core.desktop_actions.asyncio.wait_for",
                        side_effect=fake_wait_for,
                    ):
                        message = await manager.perform(request)

        self.assertIn("sedang saya buka", message)
        create_exec.assert_called_once()
        args = create_exec.call_args.args
        self.assertEqual(args[:2], ("/usr/bin/firefox", "--new-window"))

    async def test_close_requires_session_opened_by_codi(self) -> None:
        manager = DesktopActionManager()
        request = match_desktop_action("tutup libreoffice writer")
        assert request is not None

        with self.assertRaises(DesktopActionError) as captured:
            await manager.perform(request)

        self.assertIn("dibuka oleh Codi", str(captured.exception))

    async def test_close_targets_latest_tracked_process_group(self) -> None:
        manager = DesktopActionManager()
        request = match_desktop_action("tutup libreoffice writer")
        assert request is not None
        manager._launched_groups[WRITER_ACTION.action_id] = [
            TrackedDesktopProcess(
                action_id=WRITER_ACTION.action_id,
                label=WRITER_ACTION.label,
                process_group=4242,
            ),
            TrackedDesktopProcess(
                action_id=WRITER_ACTION.action_id,
                label=WRITER_ACTION.label,
                process_group=4343,
            ),
        ]

        with patch(
            "core.desktop_actions._is_process_group_alive",
            side_effect=[True, True, False, True],
        ):
            with patch("core.desktop_actions.os.killpg") as killpg:
                message = await manager.perform(request)

        killpg.assert_called_once_with(4343, ANY)
        self.assertIn("minta tutup secara normal", message)

    async def test_get_tracked_processes_prunes_dead_entries(self) -> None:
        manager = DesktopActionManager()
        manager._launched_groups[WRITER_ACTION.action_id] = [
            TrackedDesktopProcess(
                action_id=WRITER_ACTION.action_id,
                label=WRITER_ACTION.label,
                process_group=1111,
            ),
            TrackedDesktopProcess(
                action_id=WRITER_ACTION.action_id,
                label=WRITER_ACTION.label,
                process_group=2222,
            ),
        ]

        with patch(
            "core.desktop_actions._is_process_group_alive",
            side_effect=[True, False, True],
        ):
            tracked = await manager.get_tracked_processes()

        self.assertEqual(len(tracked), 1)
        self.assertEqual(tracked[0].process_group, 1111)


if __name__ == "__main__":
    unittest.main()
