"""Tests for explicit active-repo context parsing."""

from __future__ import annotations

import unittest

from core.repo_context import extract_repo_context_selection, is_repo_context_status_query


class RepoContextTests(unittest.TestCase):
    """Validate active-repo helper parsing for Telegram prompts."""

    def test_status_queries_are_detected(self) -> None:
        self.assertTrue(is_repo_context_status_query("repo aktif saat ini"))
        self.assertTrue(is_repo_context_status_query("repo aktif apa?"))
        self.assertTrue(is_repo_context_status_query("apa repo aktif sekarang"))

    def test_non_status_queries_are_ignored(self) -> None:
        self.assertFalse(is_repo_context_status_query("cek repo payroll"))
        self.assertFalse(is_repo_context_status_query("edit repo aktif sekarang"))

    def test_explicit_selection_is_extracted(self) -> None:
        self.assertEqual(
            extract_repo_context_selection("pakai repo AI-Agent-Telegram"),
            "AI-Agent-Telegram",
        )
        self.assertEqual(
            extract_repo_context_selection("ganti repo aktif ke /tmp/work/app"),
            "/tmp/work/app",
        )
        self.assertEqual(
            extract_repo_context_selection("jadikan web-dashboard-payroll sebagai repo aktif"),
            "web-dashboard-payroll",
        )

    def test_non_selection_prompts_return_none(self) -> None:
        self.assertIsNone(extract_repo_context_selection("review repo AI-Agent-Telegram"))
        self.assertIsNone(extract_repo_context_selection("pakai builder untuk cek bug login"))


if __name__ == "__main__":
    unittest.main()
