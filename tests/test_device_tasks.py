"""Tests for explicit multi-device task queue phase."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.device_tasks import (
    DeviceContextStore,
    DeviceTaskQueue,
    classify_device_task_for_dispatch,
    classify_device_task,
    is_active_device_query,
    parse_device_context_status_request,
    parse_explicit_device_request,
    parse_device_repo_request,
    parse_task_status_request,
    parse_use_device_request,
    parse_use_host_request,
    required_capability_for_task,
)


class DeviceTaskParsingTests(unittest.TestCase):
    """Validate Telegram prompt parsing for explicit device tasks."""

    def test_parse_explicit_device_request(self) -> None:
        request = parse_explicit_device_request("di device absen-server, status host")

        self.assertEqual(request.device_ref, "absen-server")
        self.assertEqual(request.task_text, "status host")

    def test_parse_task_status_request(self) -> None:
        self.assertEqual(parse_task_status_request("hasil task dt-abcdef12"), "dt-abcdef12")

    def test_classify_supported_tasks(self) -> None:
        self.assertEqual(classify_device_task("status host"), ("host_status", {}))
        self.assertEqual(classify_device_task("schema database bisnis"), ("sqlite_schema", {}))
        self.assertEqual(
            classify_device_task("schema database bisnis", active_repo="/srv/absen"),
            ("sqlite_schema", {"cwd": "/srv/absen"}),
        )
        self.assertEqual(
            classify_device_task("select * from absensi"),
            ("sqlite_query", {"sql": "select * from absensi"}),
        )
        self.assertEqual(
            classify_device_task("berapa karyawan yang telat bulan ini dan siapa namanya", active_repo="/srv/payroll"),
            ("late_this_month", {"cwd": "/srv/payroll"}),
        )
        self.assertEqual(
            classify_device_task_for_dispatch("data gaji bulan ini", active_repo="/srv/hr"),
            ("repo_readonly_query", {"query": "data gaji bulan ini", "cwd": "/srv/hr"}),
        )
        self.assertEqual(
            classify_device_task_for_dispatch("data gaji bulan ini"),
            ("natural_query", {"query": "data gaji bulan ini", "cwd": ""}),
        )

    def test_parse_context_prompts(self) -> None:
        self.assertEqual(parse_use_device_request("pakai device absen-server"), "absen-server")
        self.assertTrue(parse_use_host_request("pakai host pusat"))
        self.assertTrue(is_active_device_query("device aktif apa"))
        self.assertEqual(
            parse_device_repo_request("di device absen-server, pakai repo /srv/absen"),
            ("absen-server", "/srv/absen"),
        )
        self.assertEqual(parse_device_repo_request("pakai repo /srv/absen"), (None, "/srv/absen"))
        self.assertEqual(parse_device_context_status_request("konteks device absen-server"), "absen-server")


class DeviceContextStoreTests(unittest.TestCase):
    """Validate persisted active device and per-device repo context."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.context_path = Path(self.tempdir.name) / "contexts.json"
        self.logger = SimpleNamespace(exception=lambda *args, **kwargs: None)
        self.store = DeviceContextStore(context_path=self.context_path, logger=self.logger)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_active_device_and_repo_are_persisted(self) -> None:
        self.store.set_active_device(1, "absen-server")
        self.store.set_active_repo(1, "absen-server", "/srv/absen")

        reloaded = DeviceContextStore(context_path=self.context_path, logger=self.logger)

        self.assertEqual(reloaded.get_active_device(1), "absen-server")
        self.assertEqual(reloaded.get_context(1, "absen-server").active_repo, "/srv/absen")
        self.assertEqual(reloaded.get_active_target(1).target_kind, "device")

    def test_host_target_is_persisted_without_losing_last_device(self) -> None:
        self.store.set_active_device(1, "absen-server")
        self.store.set_host_target(1)

        reloaded = DeviceContextStore(context_path=self.context_path, logger=self.logger)

        self.assertEqual(reloaded.get_active_target(1).target_kind, "host")
        self.assertEqual(reloaded.get_active_device(1), "absen-server")


class DeviceTaskQueueTests(unittest.TestCase):
    """Validate JSON-backed task queue lifecycle."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.queue_path = Path(self.tempdir.name) / "tasks.json"
        self.logger = SimpleNamespace(exception=lambda *args, **kwargs: None)
        self.queue = DeviceTaskQueue(queue_path=self.queue_path, logger=self.logger)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_enqueue_poll_complete(self) -> None:
        task = self.queue.enqueue(
            device_id="absen-server",
            requested_by=1,
            kind="host_status",
            payload={},
        )

        polled = self.queue.poll(
            device_id="absen-server",
            capabilities=("system_activity",),
        )
        self.assertEqual(polled.task_id, task.task_id)
        self.assertEqual(polled.status, "running")

        completed = self.queue.complete(
            device_id="absen-server",
            task_id=task.task_id,
            ok=True,
            result={"output": "ok"},
        )

        self.assertEqual(completed.status, "completed")
        payload = self.queue.render_task_payload(task.task_id, assistant_name="Codi")
        self.assertIn("ok", payload.text)

    def test_poll_requires_capability(self) -> None:
        self.queue.enqueue(
            device_id="absen-server",
            requested_by=1,
            kind="sqlite_schema",
            payload={},
        )

        self.assertIsNone(self.queue.poll(device_id="absen-server", capabilities=("system_activity",)))
        self.assertIsNotNone(self.queue.poll(device_id="absen-server", capabilities=("business_readonly",)))

    def test_natural_query_requires_explicit_capability(self) -> None:
        self.queue.enqueue(
            device_id="absen-server",
            requested_by=1,
            kind="natural_query",
            payload={"query": "cek database"},
        )

        self.assertEqual(required_capability_for_task("natural_query"), "natural_query")
        self.assertIsNone(self.queue.poll(device_id="absen-server", capabilities=("system_activity",)))
        self.assertIsNotNone(self.queue.poll(device_id="absen-server", capabilities=("natural_query",)))

    def test_repo_readonly_query_requires_repo_readonly_capability(self) -> None:
        self.queue.enqueue(
            device_id="absen-server",
            requested_by=1,
            kind="repo_readonly_query",
            payload={"query": "data gaji", "cwd": "/srv/hr"},
        )

        self.assertEqual(required_capability_for_task("repo_readonly_query"), "repo_readonly")
        self.assertIsNone(self.queue.poll(device_id="absen-server", capabilities=("natural_query",)))
        self.assertIsNotNone(self.queue.poll(device_id="absen-server", capabilities=("repo_readonly",)))


if __name__ == "__main__":
    unittest.main()
