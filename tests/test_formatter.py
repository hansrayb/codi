"""Formatter tests for Telegram payload generation."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from telegram.constants import ParseMode

from core.system_activity import LogSnapshot, ProcessGroupSummary, SystemActivityReport
from utils.formatter import (
    format_error_payload,
    format_execution_payload,
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
            report=report,
            max_output_length=4000,
        )

        self.assertIn("Codi melihat aktivitas laptop ini.", payload.text)
        self.assertIn("Aplikasi desktop aktif:", payload.text)
        self.assertIn("Background atau service menonjol:", payload.text)
        self.assertIn("Log terbaru", payload.text)
        self.assertEqual(payload.parse_mode, ParseMode.HTML)


if __name__ == "__main__":
    unittest.main()
