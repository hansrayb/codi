"""Executor tests for progress event parsing."""

from __future__ import annotations

import unittest
from pathlib import Path

from utils.executor import _build_codex_args, _extract_thread_id, _parse_progress_line


class ExecutorProgressParsingTests(unittest.TestCase):
    """Validate progress extraction from Codex JSONL events."""

    def test_agent_message_progress_is_ignored(self) -> None:
        line = (
            '{"type":"item.completed","item":{"id":"item_0","type":"agent_message",'
            '"text":"Saya akan cek repo dulu."}}'
        )
        self.assertIsNone(_parse_progress_line(line))

    def test_command_started_progress_is_humanized(self) -> None:
        line = (
            '{"type":"item.started","item":{"id":"item_1","type":"command_execution",'
            '"command":"/bin/bash -lc \\"git -C /home/repo status --short --branch\\"",'
            '"aggregated_output":"","exit_code":null,"status":"in_progress"}}'
        )
        self.assertEqual(
            _parse_progress_line(line),
            "Mengecek status git repo.",
        )

    def test_command_completed_includes_first_output_line(self) -> None:
        line = (
            '{"type":"item.completed","item":{"id":"item_2","type":"command_execution",'
            '"command":"/bin/bash -lc \\"find /home -maxdepth 3 -type d -name aplikasi\\"",'
            '"aggregated_output":"/home/hans/aplikasi\\n/home/other\\n","exit_code":0,'
            '"status":"completed"}}'
        )
        self.assertEqual(
            _parse_progress_line(line),
            "Repo ditemukan di /home/hans/aplikasi.",
        )

    def test_non_json_line_is_ignored(self) -> None:
        self.assertIsNone(_parse_progress_line("Reading additional input from stdin..."))

    def test_file_read_is_humanized(self) -> None:
        line = (
            '{"type":"item.started","item":{"id":"item_3","type":"command_execution",'
            '"command":"/bin/bash -lc \\"sed -n \'1,120p\' /home/hans/repo/backend/src/app.ts\\"",'
            '"aggregated_output":"","exit_code":null,"status":"in_progress"}}'
        )
        self.assertEqual(
            _parse_progress_line(line),
            "Membaca app.ts di src.",
        )

    def test_extract_thread_id_from_thread_started_event(self) -> None:
        line = '{"type":"thread.started","thread_id":"019d6151-6eb2-7850-b350-792ea04302e0"}'
        self.assertEqual(
            _extract_thread_id(line),
            "019d6151-6eb2-7850-b350-792ea04302e0",
        )

    def test_build_args_for_new_persistent_session(self) -> None:
        args = _build_codex_args(
            prompt="cek repo",
            cwd="/home/hans/repo",
            output_path=Path("/tmp/out.txt"),
            codex_bin="codex",
            model_reasoning_effort="medium",
            sandbox_mode="read-only",
            codex_thread_id=None,
            persist_session=True,
        )
        self.assertIn("--sandbox", args)
        self.assertIn("--cd", args)
        self.assertNotIn("--ephemeral", args)
        self.assertNotIn("resume", args)

    def test_build_args_for_resume_session(self) -> None:
        args = _build_codex_args(
            prompt="lanjut",
            cwd="/home/hans/repo",
            output_path=Path("/tmp/out.txt"),
            codex_bin="codex",
            model_reasoning_effort="medium",
            sandbox_mode="workspace-write",
            codex_thread_id="thread-123",
            persist_session=True,
        )
        self.assertIn("resume", args)
        self.assertIn("thread-123", args)
        self.assertNotIn("--cd", args)
        self.assertNotIn("--sandbox", args)


if __name__ == "__main__":
    unittest.main()
