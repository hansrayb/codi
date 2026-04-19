"""Tests for explicit multi-device task queue phase."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.device_tasks import (
    DeviceTaskQueue,
    classify_device_task,
    parse_explicit_device_request,
    parse_task_status_request,
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
            classify_device_task("select * from absensi"),
            ("sqlite_query", {"sql": "select * from absensi"}),
        )


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


if __name__ == "__main__":
    unittest.main()
