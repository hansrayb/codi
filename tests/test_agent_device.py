"""Tests for local device-agent task execution helpers."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agent.main import _default_capabilities, _resolve_sqlite_path, _sqlite_query


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

    def test_default_capabilities_skip_natural_query_without_claude(self) -> None:
        with mock.patch("agent.main.shutil.which", return_value=None):
            capabilities = _default_capabilities("server").split(",")

        self.assertIn("business_readonly", capabilities)
        self.assertNotIn("natural_query", capabilities)


if __name__ == "__main__":
    unittest.main()
