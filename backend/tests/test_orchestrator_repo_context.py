"""Tests for direct-query active repo context flows."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.orchestrator import Orchestrator
from core.repo_resolver import RepoResolution
from models.case import Case
from models.session import Session


class _CaseManagerStub:
    def __init__(self) -> None:
        self.active_case: Case | None = None

    async def get_active_case(self, user_id: int):
        return self.active_case

    async def open_or_reuse_case(self, user_id: int, repo_root: Path, *, prompt: str, role: str):
        self.active_case = Case(
            case_id="c-01",
            owner_user_id=user_id,
            repo_root=str(repo_root),
            title=prompt,
            last_role=role,
            message_count=1,
        )
        return self.active_case, True

    def classify_control_message(self, text: str):
        return None


class _SessionManagerStub:
    def __init__(self) -> None:
        self.active_session: Session | None = None

    async def get_active_session(self, user_id: int):
        return self.active_session


class _RepoResolverStub:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.last_prompt: str | None = None

    def resolve(self, prompt, active_session, active_case):
        self.last_prompt = prompt
        return RepoResolution(
            root=self.root,
            label=self.root.name,
            confidence=1.0,
            reason="explicit",
            explicit=True,
        )


class _AsyncNoop:
    async def has_pending(self, user_id: int):
        return False


class _DeviceRegistryStub:
    @staticmethod
    def classify_message(text: str):
        return None

    @staticmethod
    def get_stats():
        return SimpleNamespace(registered_devices=0, online_devices=0)


class _EditApprovalStub(_AsyncNoop):
    def classify_control_message(self, text: str):
        return None

    async def reset_user(self, user_id: int):
        return None


class OrchestratorRepoContextTests(unittest.IsolatedAsyncioTestCase):
    """Validate explicit repo-context Telegram queries."""

    async def asyncSetUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.workdir = Path(self.tempdir.name)
        self.logger = SimpleNamespace(
            info=lambda *args, **kwargs: None,
            warning=lambda *args, **kwargs: None,
            exception=lambda *args, **kwargs: None,
        )
        self.case_manager = _CaseManagerStub()
        self.session_manager = _SessionManagerStub()
        self.repo_resolver = _RepoResolverStub(self.workdir / "AI-Agent-Telegram")
        settings = SimpleNamespace(
            assistant_name="Codi",
            claude_work_dir=self.workdir,
            max_output_length=1200,
            important_services=("codex-agent.service",),
            enable_desktop_actions=True,
            ai_backend="claude",
            claude_timeout=600,
            memory_db_path=self.workdir / "codi-memory.db",
        )
        self.orchestrator = Orchestrator(
            settings,
            router=SimpleNamespace(),
            case_manager=self.case_manager,
            session_manager=self.session_manager,
            repo_resolver=self.repo_resolver,
            repo_watch_manager=SimpleNamespace(),
            device_registry_manager=_DeviceRegistryStub(),
            self_maintenance_manager=SimpleNamespace(project_root=self.workdir, is_self_repo=lambda p: False),
            desktop_action_manager=SimpleNamespace(),
            desktop_screenshot_service=SimpleNamespace(),
            local_shell_service=SimpleNamespace(),
            edit_approval_manager=_EditApprovalStub(),
            safety_manager=SimpleNamespace(
                try_handle_control_message=lambda user_id, text: SimpleNamespace(handled=False),
            ),
            system_activity_inspector=SimpleNamespace(),
            logger=self.logger,
        )

    async def asyncTearDown(self) -> None:
        self.tempdir.cleanup()

    async def test_status_query_returns_active_repo_summary(self) -> None:
        repo_root = self.workdir / "AI-Agent-Telegram"
        self.case_manager.active_case = Case(
            case_id="c-01",
            owner_user_id=1,
            repo_root=str(repo_root),
            title="perbaiki help",
        )

        payload = await self.orchestrator.try_handle_direct_query(1, "repo aktif saat ini")

        self.assertIn("konteks aktif", payload.text.lower())
        self.assertIn(str(repo_root), payload.text)

    async def test_selection_query_switches_active_repo_context(self) -> None:
        payload = await self.orchestrator.try_handle_direct_query(
            1,
            "pakai repo AI-Agent-Telegram",
        )

        self.assertIn("sekarang pakai repo ini", payload.text.lower())
        self.assertEqual(self.repo_resolver.last_prompt, "repo AI-Agent-Telegram")
        self.assertIsNotNone(self.case_manager.active_case)


if __name__ == "__main__":
    unittest.main()
