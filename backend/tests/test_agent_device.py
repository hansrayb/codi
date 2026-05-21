"""Tests for local device-agent task execution helpers."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agent.main import (
    _default_capabilities,
    _repo_readonly_query,
    _repo_readonly_snapshot,
    _resolve_sqlite_path,
    _sqlite_query,
)


class AgentDeviceExecutionTests(unittest.TestCase):
    """Validate agent-side SQLite discovery from device context."""

    def test_resolve_sqlite_path_discovers_database_under_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "data" / "absen.sqlite3"
            db_path.parent.mkdir()
            db_path.write_text("", encoding="utf-8")

            with mock.patch.dict(os.environ, {"CODI_BUSINESS_DATABASE_PATHS": ""}, clear=False):
                self.assertEqual(_resolve_sqlite_path(str(root)), str(db_path))

    def test_sqlite_query_uses_context_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "absen.sqlite3"
            conn = sqlite3.connect(db_path)
            try:
                conn.execute("CREATE TABLE absensi (id INTEGER PRIMARY KEY, nama TEXT)")
                conn.execute("INSERT INTO absensi (nama) VALUES ('Ayu')")
                conn.commit()
            finally:
                conn.close()

            with mock.patch.dict(os.environ, {"CODI_BUSINESS_DATABASE_PATHS": ""}, clear=False):
                output = _sqlite_query("select nama from absensi", str(root))

            self.assertIn("Ayu", output)

    def test_default_capabilities_advertise_available_handlers(self) -> None:
        with mock.patch("agent.main.shutil.which", return_value="/usr/bin/claude"):
            capabilities = _default_capabilities("server").split(",")

        self.assertIn("system_activity", capabilities)
        self.assertIn("business_readonly", capabilities)
        self.assertIn("natural_query", capabilities)
        self.assertIn("repo_readonly", capabilities)

    def test_default_capabilities_skip_natural_query_without_claude(self) -> None:
        with mock.patch("agent.main.shutil.which", return_value=None):
            capabilities = _default_capabilities("server").split(",")

        self.assertIn("business_readonly", capabilities)
        self.assertNotIn("natural_query", capabilities)
        self.assertNotIn("repo_readonly", capabilities)

    def test_repo_readonly_snapshot_lists_relevant_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "package.json").write_text('{"scripts":{}}', encoding="utf-8")
            (root / "app").mkdir()
            (root / "app" / "page.tsx").write_text("export default function Page() {}", encoding="utf-8")

            snapshot = _repo_readonly_snapshot(str(root))

        self.assertIn("package.json", snapshot)
        self.assertIn("app/page.tsx", snapshot)

    def test_repo_readonly_query_invokes_claude_with_readonly_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "package.json").write_text('{"scripts":{}}', encoding="utf-8")

            completed = mock.Mock(returncode=0, stdout="Ringkasan gaji bulan ini", stderr="")
            with mock.patch("subprocess.run", return_value=completed) as run_mock:
                output = _repo_readonly_query("data gaji bulan ini", str(root))

        self.assertIn("Ringkasan gaji", output)
        args, kwargs = run_mock.call_args
        self.assertEqual(args[0], ["claude", "--print", "--allowedTools", "Bash"])
        self.assertEqual(kwargs["cwd"], str(root))
        self.assertIn("Jangan mengubah file", kwargs["input"])


if __name__ == "__main__":
    unittest.main()
