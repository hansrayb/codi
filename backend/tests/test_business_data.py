"""Tests for read-only business data helpers."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.business_data import BusinessDataService, _database_target_from_url, _is_readonly_sql


class BusinessDataServiceTests(unittest.TestCase):
    """Validate SQLite read-only and business-logic inspection flows."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name).resolve()
        self.db_path = self.root / "business.sqlite"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT)")
            conn.execute("INSERT INTO customers (name) VALUES ('Ayu'), ('Bima')")
        self.service = BusinessDataService(SimpleNamespace(business_database_paths=()))

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_schema_request_lists_tables(self) -> None:
        request = self.service.match("schema database bisnis")

        payload = self.service.handle(request, self.root, assistant_name="Codi")

        self.assertIn("customers", payload.text)
        self.assertIn("name TEXT", payload.text)

    def test_select_query_returns_rows(self) -> None:
        request = self.service.match("select id, name from customers order by id")

        payload = self.service.handle(request, self.root, assistant_name="Codi")

        self.assertIn("Ayu", payload.text)
        self.assertIn("Bima", payload.text)

    def test_write_query_is_rejected(self) -> None:
        request = self.service.match("query: delete from customers")

        payload = self.service.handle(request, self.root, assistant_name="Codi")

        self.assertIn("hanya boleh SELECT", payload.text)
        with sqlite3.connect(self.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        self.assertEqual(count, 2)

    def test_postgresql_schema_requires_configured_url(self) -> None:
        request = self.service.match("schema postgresql database")

        payload = self.service.handle(request, self.root, assistant_name="Codi")

        self.assertIn("PostgreSQL URL", payload.text)

    def test_database_url_label_hides_credentials(self) -> None:
        target = _database_target_from_url("postgresql://user:secret@db.local:5432/app")

        self.assertEqual(target.kind, "postgresql")
        self.assertEqual(target.label, "postgresql://db.local:5432/app")
        self.assertNotIn("secret", target.label)

    def test_non_sqlite_rejects_pragma_and_multiple_statements(self) -> None:
        self.assertTrue(_is_readonly_sql("select * from customers", "postgresql"))
        self.assertTrue(_is_readonly_sql("with recent as (select 1) select * from recent", "mysql"))
        self.assertFalse(_is_readonly_sql("pragma table_info(customers)", "postgresql"))
        self.assertFalse(_is_readonly_sql("select 1; delete from customers", "mysql"))
        self.assertFalse(_is_readonly_sql("with old as (select 1) delete from customers", "sqlite"))

    def test_business_logic_summary_lists_candidate_files(self) -> None:
        service_file = self.root / "app" / "services" / "order_service.py"
        service_file.parent.mkdir(parents=True)
        service_file.write_text(
            "class OrderService:\n"
            "    def calculate_total(self):\n"
            "        return 42\n",
            encoding="utf-8",
        )

        request = self.service.match("baca logika bisnis project ini")
        payload = self.service.handle(request, self.root, assistant_name="Codi")

        self.assertIn("app/services/order_service.py", payload.text)
        self.assertIn("OrderService", payload.text)


if __name__ == "__main__":
    unittest.main()
