"""Formatter tests for Telegram payload generation."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from telegram.constants import ParseMode

from core.desktop_screenshot import DesktopScreenshot
from core.env_config import EnvConfigUpdateResult
from core.local_shell import LocalShellResult
from core.system_activity import (
    LogSnapshot,
    ProcessGroupSummary,
    SystemActivityReport,
    SystemActivityRequest,
)
from utils.formatter import (
    format_desktop_screenshot_payload,
    format_env_config_update_payload,
    format_error_payload,
    format_execution_payload,
    format_local_shell_payload,
    format_system_activity_payload,
)


class FormatterTests(unittest.TestCase):
    """Validate formatting behavior for normal and oversized outputs."""

    def test_success_payload_uses_html_pre_block(self) -> None:
        payload = format_execution_payload(
            assistant_name="Codi",
            role="builder",
            session_id="s-01",
            exit_code=0,
            stdout="print('hello')",
            stderr="",
            max_output_length=200,
        )

        self.assertIn("<b>Codi selesai mengerjakan task ini</b>", payload.text)
        self.assertIn("print(&#x27;hello&#x27;)", payload.text)
        self.assertEqual(payload.parse_mode, ParseMode.HTML)
        self.assertFalse(payload.has_attachment)

    def test_large_output_becomes_attachment(self) -> None:
        payload = format_execution_payload(
            assistant_name="Codi",
            role="reviewer",
            session_id="s-02",
            exit_code=0,
            stdout="x" * 250,
            stderr="",
            max_output_length=100,
        )

        self.assertTrue(payload.has_attachment)
        self.assertIn("Versi lengkap saya kirim sebagai file.", payload.text)
        self.assertEqual(payload.attachment_filename, "s-02-reviewer-output.txt")

    def test_error_payload_is_html_safe(self) -> None:
        payload = format_error_payload("gagal <fatal>", assistant_name="Codi")
        self.assertIn("&lt;fatal&gt;", payload.text)
        self.assertIn("Codi belum sempat menyelesaikan task ini.", payload.text)
        self.assertEqual(payload.parse_mode, ParseMode.HTML)

    def test_desktop_screenshot_payload_contains_photo(self) -> None:
        payload = format_desktop_screenshot_payload(
            assistant_name="Codi",
            screenshot=DesktopScreenshot(
                captured_at=datetime(2026, 4, 8, 5, 0, tzinfo=timezone.utc),
                source="spectacle",
                mode="fullscreen",
                image_bytes=b"png-bytes",
            ),
        )

        self.assertIn("Codi sudah ambil screenshot layar penuh laptop ini.", payload.text)
        self.assertTrue(payload.has_photo)
        self.assertEqual(payload.photo_filename, "desktop-screenshot.png")
        self.assertEqual(payload.parse_mode, ParseMode.HTML)

    def test_desktop_screenshot_payload_can_include_scene_summary(self) -> None:
        payload = format_desktop_screenshot_payload(
            assistant_name="Codi",
            screenshot=DesktopScreenshot(
                captured_at=datetime(2026, 4, 8, 5, 0, tzinfo=timezone.utc),
                source="spectacle",
                mode="current_monitor",
                image_bytes=b"png-bytes",
                filename="monitor-screenshot.png",
            ),
            report=SystemActivityReport(
                captured_at=datetime(2026, 4, 8, 5, 0, tzinfo=timezone.utc),
                current_user="hans",
                cpu_percent=10.0,
                memory_used_bytes=1,
                memory_total_bytes=2,
                memory_percent=50.0,
                swap_percent=0.0,
                host_uptime_seconds=60,
                desktop_apps=(
                    ProcessGroupSummary(
                        label="Firefox",
                        process_count=2,
                        total_memory_bytes=200,
                        oldest_create_time=0.0,
                        sample_pid=1,
                        status_summary="running x2",
                        sample_command="firefox",
                        usernames=("hans",),
                    ),
                ),
                background_apps=(),
                logs=None,
            ),
        )

        self.assertIn("Ringkasan isi layar:", payload.text)
        self.assertIn("Aplikasi yang paling kelihatan saat ini antara lain Firefox.", payload.text)

    def test_desktop_screenshot_payload_mentions_when_summary_is_unavailable(self) -> None:
        payload = format_desktop_screenshot_payload(
            assistant_name="Codi",
            screenshot=DesktopScreenshot(
                captured_at=datetime(2026, 4, 8, 5, 0, tzinfo=timezone.utc),
                source="spectacle",
                mode="fullscreen",
                image_bytes=b"png-bytes",
            ),
            include_summary_requested=True,
        )

        self.assertIn("Ringkasan isi layar:", payload.text)
        self.assertIn("ringkasan isi layar belum kebaca jelas", payload.text)

    def test_local_shell_payload_includes_command_context(self) -> None:
        payload = format_local_shell_payload(
            assistant_name="Codi",
            result=LocalShellResult(
                shell="bash",
                shell_path="/usr/bin/bash",
                command="git status --short",
                cwd=Path("/home/hans/AI-Agent-Telegram"),
                exit_code=0,
                stdout=" M main.py\n",
                stderr="",
            ),
            max_output_length=3000,
        )

        self.assertIn("Codi sudah menjalankan perintah shell lokal.", payload.text)
        self.assertIn("git status --short", payload.text)
        self.assertIn("/usr/bin/bash", payload.text)
        self.assertIn("M main.py", payload.text)
        self.assertEqual(payload.parse_mode, ParseMode.HTML)

    def test_local_shell_payload_large_output_becomes_attachment(self) -> None:
        payload = format_local_shell_payload(
            assistant_name="Codi",
            result=LocalShellResult(
                shell="bash",
                shell_path="/usr/bin/bash",
                command="journalctl -n 500",
                cwd=Path("/home/hans"),
                exit_code=0,
                stdout="x" * 500,
                stderr="",
            ),
            max_output_length=120,
        )

        self.assertTrue(payload.has_attachment)
        self.assertEqual(payload.attachment_filename, "shell-bash-output.txt")
        self.assertIn("Versi lengkap saya kirim sebagai file.", payload.text)

    def test_env_config_update_payload_can_schedule_restart(self) -> None:
        payload = format_env_config_update_payload(
            assistant_name="Codi",
            result=EnvConfigUpdateResult(
                key="CLAUDE_TIMEOUT",
                display_name="Codex timeout",
                old_value="180",
                new_value="600",
                env_path=Path("/home/hans/AI-Agent-Telegram/.env"),
                changed=True,
                restart_required=True,
            ),
        )

        self.assertIn("Codi sudah merapikan konfigurasi lokal ini.", payload.text)
        self.assertIn("CLAUDE_TIMEOUT", payload.text)
        self.assertIn("600", payload.text)
        self.assertEqual(payload.post_send_action, "restart_self")
        self.assertEqual(payload.parse_mode, ParseMode.HTML)

    def test_system_activity_payload_includes_sections(self) -> None:
        report = SystemActivityReport(
            captured_at=datetime(2026, 4, 5, 12, 0, tzinfo=timezone.utc),
            current_user="hans",
            cpu_percent=24.0,
            memory_used_bytes=4 * 1024 * 1024 * 1024,
            memory_total_bytes=8 * 1024 * 1024 * 1024,
            memory_percent=50.0,
            swap_percent=5.0,
            host_uptime_seconds=7200,
            desktop_apps=(
                ProcessGroupSummary(
                    label="LibreOffice Writer",
                    process_count=1,
                    total_memory_bytes=210 * 1024 * 1024,
                    oldest_create_time=datetime(2026, 4, 5, 11, 30, tzinfo=timezone.utc).timestamp(),
                    sample_pid=4242,
                    status_summary="running x1",
                    sample_command="/usr/bin/libreoffice --writer",
                    usernames=("hans",),
                    tracked_by_codi=True,
                ),
            ),
            background_apps=(
                ProcessGroupSummary(
                    label="Postgres",
                    process_count=2,
                    total_memory_bytes=320 * 1024 * 1024,
                    oldest_create_time=datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc).timestamp(),
                    sample_pid=99,
                    status_summary="sleeping x2",
                    sample_command="/usr/bin/postgres -D /var/lib/pgsql/data",
                    usernames=("postgres",),
                    tracked_by_codi=False,
                ),
            ),
            logs=LogSnapshot(
                source="file:/tmp/codi.log",
                lines=("2026-04-05 12:00:00 | INFO | bot started",),
            ),
        )

        payload = format_system_activity_payload(
            assistant_name="Codi",
            request=SystemActivityRequest(
                include_processes=True,
                include_logs=True,
            ),
            report=report,
            max_output_length=4000,
        )

        self.assertIn("Ini yang saya lihat di laptopmu, plus catatan terbaru dari Codi.", payload.text)
        self.assertIn("Yang paling kelihatan sekarang ada LibreOffice Writer.", payload.text)
        self.assertIn("Sekilas kondisi laptopmu:", payload.text)
        self.assertIn("Yang lagi kebuka:", payload.text)
        self.assertIn("Yang jalan di belakang layar:", payload.text)
        self.assertIn("Catatan terbaru dari Codi (diambil dari file log lokal):", payload.text)
        self.assertNotIn("pid contoh", payload.text)
        self.assertNotIn("cmd:", payload.text)
        self.assertEqual(payload.parse_mode, ParseMode.HTML)

    def test_log_only_payload_skips_process_sections(self) -> None:
        report = SystemActivityReport(
            captured_at=datetime(2026, 4, 5, 12, 0, tzinfo=timezone.utc),
            current_user="hans",
            cpu_percent=24.0,
            memory_used_bytes=4 * 1024 * 1024 * 1024,
            memory_total_bytes=8 * 1024 * 1024 * 1024,
            memory_percent=50.0,
            swap_percent=5.0,
            host_uptime_seconds=7200,
            desktop_apps=(),
            background_apps=(),
            logs=LogSnapshot(
                source="journal:codex-agent.service",
                lines=("2026-04-05 12:00:00 | INFO | bot started",),
            ),
        )

        payload = format_system_activity_payload(
            assistant_name="Codi",
            request=SystemActivityRequest(
                include_processes=False,
                include_logs=True,
            ),
            report=report,
            max_output_length=4000,
        )

        self.assertIn("Ini catatan terbaru dari Codi.", payload.text)
        self.assertIn("Saya ambil catatan terbaru dari Codi di bawah ini.", payload.text)
        self.assertIn("Catatan terbaru dari Codi (diambil dari service log):", payload.text)
        self.assertNotIn("Yang lagi kebuka:", payload.text)

    def test_process_only_payload_prioritizes_app_list(self) -> None:
        report = SystemActivityReport(
            captured_at=datetime(2026, 4, 5, 12, 0, tzinfo=timezone.utc),
            current_user="hans",
            cpu_percent=24.0,
            memory_used_bytes=4 * 1024 * 1024 * 1024,
            memory_total_bytes=8 * 1024 * 1024 * 1024,
            memory_percent=50.0,
            swap_percent=5.0,
            host_uptime_seconds=7200,
            desktop_apps=(
                ProcessGroupSummary(
                    label="Code",
                    process_count=8,
                    total_memory_bytes=int(1.3 * 1024 * 1024 * 1024),
                    oldest_create_time=datetime(2026, 4, 5, 11, 30, tzinfo=timezone.utc).timestamp(),
                    sample_pid=109261,
                    status_summary="sleeping x6, running x2",
                    sample_command="/usr/share/code/code",
                    usernames=("hans",),
                    tracked_by_codi=False,
                ),
            ),
            background_apps=(),
            logs=None,
        )

        payload = format_system_activity_payload(
            assistant_name="Codi",
            request=SystemActivityRequest(
                include_processes=True,
                include_logs=False,
            ),
            report=report,
            max_output_length=4000,
        )

        self.assertIn("Ini yang lagi kelihatan di laptopmu.", payload.text)
        self.assertIn("Yang lagi kebuka:", payload.text)
        self.assertIn("Saya cek ini pada", payload.text)
        self.assertNotIn("Sekilas kondisi laptopmu:", payload.text)
        self.assertNotIn("Yang jalan di belakang layar:", payload.text)


if __name__ == "__main__":
    unittest.main()
