"""Tests for explicit host/device target selection in the orchestrator."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.device_tasks import DeviceContextStore, DeviceTaskQueue
from core.orchestrator import Orchestrator


class _AsyncNoop:
    async def get_active_case(self, user_id: int):
        return None

    async def get_active_session(self, user_id: int):
        return None

    async def reset_user(self, user_id: int):
        return 0

    def classify_control_message(self, text: str):
        return None

    async def has_pending(self, user_id: int):
        return False


class _RepoResolverStub:
    def resolve(self, prompt, active_session, active_case):
        raise AssertionError("Repo resolver should not be used in this test")


class _EditApprovalStub:
    def classify_control_message(self, text: str):
        return None

    async def has_pending(self, user_id: int):
        return False

    async def reset_user(self, user_id: int):
        return None


class _DeviceRegistryStub:
    def __init__(self) -> None:
        self.record = SimpleNamespace(
            device_id="absen-server",
            label="Absen Server",
            device_type="server",
            hostname="absen-host",
            platform="Linux",
            capabilities=("system_activity", "business_readonly", "natural_query"),
        )

    @staticmethod
    def classify_message(text: str):
        return None

    @staticmethod
    def get_stats():
        return SimpleNamespace(registered_devices=1, online_devices=1)

    def resolve_device(self, device_ref: str):
        if device_ref in {"absen-server", "Absen Server"}:
            return self.record
        return None

    @staticmethod
    def is_online_record(record) -> bool:
        return True

    def list_records(self):
        return (self.record,)


class OrchestratorDeviceTargetTests(unittest.IsolatedAsyncioTestCase):
    """Validate explicit host-vs-device selection behavior."""

    async def asyncSetUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.workdir = Path(self.tempdir.name)
        self.logger = SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            exception=lambda *args, **kwargs: None,
        )
        self.device_registry = _DeviceRegistryStub()
        self.device_context_store = DeviceContextStore(
            context_path=self.workdir / "contexts.json",
            logger=self.logger,
        )
        self.device_task_queue = DeviceTaskQueue(
            queue_path=self.workdir / "tasks.json",
            logger=self.logger,
        )
        settings = SimpleNamespace(
            assistant_name="Codi",
            codex_work_dir=self.workdir,
            max_output_length=1200,
            important_services=("codex-agent.service",),
            enable_desktop_actions=True,
            codex_timeout=600,
            codex_bin="codex",
            codex_reasoning_effort="medium",
            ai_backend="codex",
        )
        self.orchestrator = Orchestrator(
            settings,
            router=SimpleNamespace(),
            case_manager=_AsyncNoop(),
            session_manager=_AsyncNoop(),
            repo_resolver=_RepoResolverStub(),
            repo_watch_manager=SimpleNamespace(),
            device_registry_manager=self.device_registry,
            self_maintenance_manager=SimpleNamespace(),
            desktop_action_manager=SimpleNamespace(),
            desktop_screenshot_service=SimpleNamespace(),
            local_shell_service=SimpleNamespace(),
            edit_approval_manager=_EditApprovalStub(),
            safety_manager=SimpleNamespace(
                try_handle_control_message=lambda user_id, text: SimpleNamespace(handled=False),
            ),
            system_activity_inspector=SimpleNamespace(),
            logger=self.logger,
            device_task_queue=self.device_task_queue,
            device_context_store=self.device_context_store,
        )

    async def asyncTearDown(self) -> None:
        self.tempdir.cleanup()

    async def test_host_target_does_not_auto_route_prompt_to_device(self) -> None:
        self.device_context_store.set_active_device(1, "absen-server")
        self.device_context_store.set_active_repo(1, "absen-server", "/srv/absen")
        self.device_context_store.set_host_target(1)

        payload = await self.orchestrator.try_handle_device_message(1, "status host")

        self.assertIsNone(payload)

    async def test_device_target_routes_prompt_to_selected_device(self) -> None:
        self.device_context_store.set_active_device(1, "absen-server")
        self.device_context_store.set_active_repo(1, "absen-server", "/srv/absen")

        payload = await self.orchestrator.try_handle_device_message(1, "status host")

        self.assertIsNotNone(payload)
        self.assertIn("mengirim task ke device", payload.text.lower())
        queued = self.device_task_queue.poll(device_id="absen-server", capabilities=("system_activity",))
        self.assertIsNotNone(queued)
        self.assertEqual(queued.kind, "host_status")

    async def test_devices_panel_shows_host_as_default_target(self) -> None:
        payload = self.orchestrator.render_devices_panel(1)

        self.assertIn("Target aktif: Host pusat", payload.text)
        self.assertIsNotNone(payload.inline_buttons)
        self.assertTrue(any(button[1] == "device:target:host" for button in payload.inline_buttons or ()))


if __name__ == "__main__":
    unittest.main()
