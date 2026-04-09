"""Tests for device registry persistence, queries, and API heartbeat ingress."""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib import error, request

from core.device_api import DeviceApiServer
from core.device_registry import (
    DeviceRegistryManager,
    DeviceRegistryStats,
    DeviceRegistration,
    parse_device_registration,
)


class DeviceRegistryManagerTests(unittest.TestCase):
    """Validate in-memory plus persisted device state behavior."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.registry_path = Path(self.tempdir.name) / "devices.json"
        self.logger = SimpleNamespace(info=lambda *args, **kwargs: None, exception=lambda *args, **kwargs: None)
        self.manager = DeviceRegistryManager(
            registry_path=self.registry_path,
            heartbeat_ttl_seconds=90,
            assistant_name="Codi",
            logger=self.logger,
        )
        self.registration = DeviceRegistration(
            device_id="laptop-kerja",
            label="Laptop Kerja",
            device_type="desktop",
            hostname="laptop",
            platform="Linux",
            capabilities=("shell", "screenshot"),
            agent_version="v1",
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_register_device_persists_registry_file(self) -> None:
        record = self.manager.register_device(self.registration, remote_addr="10.0.0.2")

        self.assertEqual(record.device_id, "laptop-kerja")
        self.assertTrue(self.registry_path.exists())
        payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["devices"][0]["device_id"], "laptop-kerja")
        self.assertEqual(payload["devices"][0]["last_ip"], "10.0.0.2")

    def test_get_stats_counts_online_devices(self) -> None:
        self.manager.register_device(self.registration)
        stats = self.manager.get_stats()

        self.assertEqual(
            stats,
            DeviceRegistryStats(registered_devices=1, online_devices=1),
        )

    def test_render_detail_payload_matches_device_label(self) -> None:
        self.manager.register_device(self.registration)
        payload = self.manager.render_detail_payload("Laptop Kerja")

        self.assertIn("Detail device Laptop Kerja", payload.text)
        self.assertIn("laptop-kerja", payload.text)

    def test_classify_device_queries(self) -> None:
        self.assertEqual(self.manager.classify_message("device yang online apa saja").action, "list")
        self.assertEqual(self.manager.classify_message("detail device laptop-kerja").action, "detail")
        self.assertIsNone(self.manager.classify_message("cek repo ini"))

    def test_parse_device_registration_normalizes_capabilities(self) -> None:
        registration = parse_device_registration(
            {
                "device_id": "Laptop Kerja",
                "label": "Laptop Kerja",
                "device_type": "Desktop",
                "hostname": "laptop",
                "platform": "Linux",
                "capabilities": "shell, screenshot, shell",
            }
        )

        self.assertEqual(registration.device_id, "laptop-kerja")
        self.assertEqual(registration.capabilities, ("shell", "screenshot"))


class DeviceApiServerTests(unittest.TestCase):
    """Validate authenticated register and heartbeat ingress over HTTP."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        registry_path = Path(self.tempdir.name) / "devices.json"
        logger = SimpleNamespace(info=lambda *args, **kwargs: None, exception=lambda *args, **kwargs: None)
        self.registry = DeviceRegistryManager(
            registry_path=registry_path,
            heartbeat_ttl_seconds=90,
            assistant_name="Codi",
            logger=logger,
        )
        self.server = DeviceApiServer(
            host="127.0.0.1",
            port=0,
            shared_token="secret-token",
            registry=self.registry,
            logger=logger,
        )
        self.server.start()
        time.sleep(0.05)

    def tearDown(self) -> None:
        self.server.stop()
        self.tempdir.cleanup()

    def test_register_endpoint_accepts_valid_token(self) -> None:
        response = self._post(
            "/api/device/register",
            {
                "device_id": "vps-hestia",
                "label": "VPS Hestia",
                "device_type": "server",
                "hostname": "vps-01",
                "platform": "Linux",
                "capabilities": ["shell", "repo", "systemd"],
            },
        )

        self.assertTrue(response["ok"])
        payload = self.registry.render_list_payload()
        self.assertIn("VPS Hestia", payload.text)

    def test_heartbeat_endpoint_rejects_missing_token(self) -> None:
        req = request.Request(
            self._url("/api/device/heartbeat"),
            data=json.dumps({"device_id": "x"}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        with self.assertRaises(error.HTTPError) as ctx:
            request.urlopen(req, timeout=5)

        self.assertEqual(ctx.exception.code, 401)
        ctx.exception.close()

    def _post(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        req = request.Request(
            self._url(path),
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer secret-token",
            },
        )
        with request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.server.bound_port}{path}"


if __name__ == "__main__":
    unittest.main()
