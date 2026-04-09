"""Integration-leaning tests for safety-gated direct queries."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.orchestrator import Orchestrator
from core.safety import SafetyManager


class _DeviceRegistryStub:
    @staticmethod
    def classify_message(text: str):
        return None

    @staticmethod
    def get_stats():
        return SimpleNamespace(registered_devices=0, online_devices=0)


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


class OrchestratorSafetyTests(unittest.IsolatedAsyncioTestCase):
    """Validate safety approval flows through orchestrator entry points."""

    async def asyncSetUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.workdir = Path(self.tempdir.name)
        (self.workdir / ".env").write_text("CODEX_TIMEOUT=180\n", encoding="utf-8")
        self.logger = SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            exception=lambda *args, **kwargs: None,
        )
        self.safety_manager = SafetyManager(
            assistant_name="Codi",
            allowed_user_ids=(1,),
            default_mode="ops",
            admin_user_ids=(1,),
            ops_user_ids=(1,),
            approval_ttl_seconds=180,
            audit_log_path=self.workdir / "codi-audit.log",
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
        )
        self.orchestrator = Orchestrator(
            settings,
            router=SimpleNamespace(),
            case_manager=_AsyncNoop(),
            session_manager=_AsyncNoop(),
            repo_resolver=_RepoResolverStub(),
            repo_watch_manager=SimpleNamespace(),
            device_registry_manager=_DeviceRegistryStub(),
            self_maintenance_manager=SimpleNamespace(),
            desktop_action_manager=SimpleNamespace(),
            desktop_screenshot_service=SimpleNamespace(),
            local_shell_service=SimpleNamespace(),
            edit_approval_manager=_EditApprovalStub(),
            safety_manager=self.safety_manager,
            system_activity_inspector=SimpleNamespace(),
            logger=self.logger,
        )

    async def asyncTearDown(self) -> None:
        self.tempdir.cleanup()

    async def test_restart_requires_approval_then_schedules_restart(self) -> None:
        pending = await self.orchestrator.try_handle_direct_query(1, "restart codi")
        approved = await self.orchestrator.try_handle_control_message(1, "lanjutkan aksi")

        self.assertIn("aksi ini saya tahan dulu", pending.text.lower())
        self.assertEqual(approved.post_send_action, "restart_self")
        self.assertIn("mulai ulang", approved.text.lower())

    async def test_mode_aman_blocks_restart_until_mode_is_raised(self) -> None:
        await self.orchestrator.try_handle_control_message(1, "mode aman")

        payload = await self.orchestrator.try_handle_direct_query(1, "restart codi")

        self.assertIn("butuh mode", payload.text.lower())
        self.assertIn("ops", payload.text.lower())

    async def test_env_update_is_applied_after_confirmation(self) -> None:
        pending = await self.orchestrator.try_handle_direct_query(
            1,
            "ubah codex timeout jadi 600",
        )
        approved = await self.orchestrator.try_handle_control_message(1, "lanjutkan aksi")

        self.assertIn("aksi ini saya tahan dulu", pending.text.lower())
        self.assertIn("CODEX_TIMEOUT", approved.text)
        self.assertIn("<code>600</code>", approved.text)
        self.assertEqual(approved.post_send_action, "restart_self")
        self.assertIn("CODEX_TIMEOUT=600", (self.workdir / ".env").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
