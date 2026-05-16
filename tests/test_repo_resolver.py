"""Repo resolver tests for name, path, and active-session targeting."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from config import Settings
from core.repo_resolver import RepoResolver, RepoResolverError
from models.case import Case
from models.session import Session


class RepoResolverTests(unittest.TestCase):
    """Validate repo resolution across common Telegram prompt patterns."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tempdir.name).resolve()
        self.repo_customerchant = self._make_repo("aplikasi-customerchant")
        self.repo_payroll_web = self._make_repo("web-dashboard-payroll")
        self.repo_payroll_mobile = self._make_repo("mobile-payroll")
        self.project_codi = self._make_project("AI-Agent-Telegram")
        self.settings = Settings(
            assistant_name="Codi",
            enable_desktop_actions=True,
            enable_local_shell=True,
            telegram_bot_token="token",
            allowed_user_ids=(1,),
            admin_user_ids=(),
            viewer_user_ids=(),
            business_user_ids=(),
            business_allowed_dirs=(),
            business_database_paths=(),
            business_database_urls=(),
            ai_backend="codex",
            codex_bin="codex",
            claude_timeout=180,
            codex_reasoning_effort="medium",
            codex_write_sandbox_mode="workspace-write",
            claude_work_dir=self.workspace,
            claude_bin="claude",
            claude_model="claude-sonnet-4-6",
            allowed_work_dirs=(self.workspace,),
            default_role="general",
            max_active_sessions=4,
            max_sessions_per_user=3,
            session_idle_ttl_minutes=60,
            max_queue_per_session=1,
            max_output_length=3000,
            local_shell_timeout=120,
            log_level="INFO",
            log_file=None,
            max_requests_per_minute=5,
            repo_watch_poll_seconds=30,
            service_watch_poll_seconds=30,
            max_watched_repos_per_user=5,
            important_services=("codi.service",),
            important_pm2_apps=(),
            alert_targets_path=self.workspace / "codi-alert-targets.json",
            enable_device_registry=False,
            device_registry_path=self.workspace / "codi-devices.json",
            device_api_host="127.0.0.1",
            device_api_port=8787,
            device_api_shared_token=None,
            device_heartbeat_ttl_seconds=90,
        )
        self.resolver = RepoResolver(self.settings, refresh_interval_seconds=0)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_exact_repo_hint_resolves(self) -> None:
        resolution = self.resolver.resolve("cek repo aplikasi-customerchant")

        self.assertEqual(resolution.root, self.repo_customerchant)
        self.assertEqual(resolution.label, "aplikasi-customerchant")
        self.assertTrue(resolution.explicit)

    def test_absolute_path_resolves_repo_root(self) -> None:
        nested_file = self.repo_customerchant / "backend" / "src" / "pricing.service.ts"
        nested_file.parent.mkdir(parents=True)
        nested_file.write_text("export {};\n", encoding="utf-8")

        resolution = self.resolver.resolve(f"review file {nested_file}")

        self.assertEqual(resolution.root, self.repo_customerchant)
        self.assertEqual(resolution.reason, "absolute_path_repo")

    def test_case_mismatched_absolute_path_resolves_existing_project(self) -> None:
        requested = self.project_codi.parent / "ai-agent-telegram"
        resolution = self.resolver.resolve(f"ada di {requested}")

        self.assertEqual(resolution.root, self.project_codi)
        self.assertEqual(resolution.reason, "absolute_path_repo")

    def test_non_git_project_name_resolves(self) -> None:
        resolution = self.resolver.resolve("cek repo AI-Agent-Telegram")

        self.assertEqual(resolution.root, self.project_codi)
        self.assertEqual(resolution.label, "AI-Agent-Telegram")

    def test_active_session_is_reused_when_prompt_has_no_explicit_repo(self) -> None:
        active_session = Session(
            session_id="s-01",
            owner_user_id=1,
            role="builder",
            cwd=str(self.repo_payroll_web),
            summary="- perbaiki login payroll",
        )

        resolution = self.resolver.resolve("lanjutkan perbaiki bug login", active_session)

        self.assertEqual(resolution.root, self.repo_payroll_web)
        self.assertTrue(resolution.used_active_session)

    def test_active_business_case_is_reused_outside_allowed_work_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as business_tempdir:
            business_root = Path(business_tempdir).resolve()
            business_repo = business_root / "sales-dashboard"
            (business_repo / ".git").mkdir(parents=True)
            settings = Settings(
                assistant_name="Codi",
                enable_desktop_actions=True,
                enable_local_shell=True,
                telegram_bot_token="token",
                allowed_user_ids=(1,),
                admin_user_ids=(),
                viewer_user_ids=(),
                business_user_ids=(1,),
                business_allowed_dirs=(business_root,),
                business_database_paths=(),
                business_database_urls=(),
                ai_backend="codex",
                codex_bin="codex",
                claude_timeout=180,
                codex_reasoning_effort="medium",
                codex_write_sandbox_mode="workspace-write",
                claude_work_dir=self.workspace,
                claude_bin="claude",
                claude_model="claude-sonnet-4-6",
                allowed_work_dirs=(self.workspace,),
                default_role="general",
                max_active_sessions=4,
                max_sessions_per_user=3,
                session_idle_ttl_minutes=60,
                max_queue_per_session=1,
                max_output_length=3000,
                local_shell_timeout=120,
                log_level="INFO",
                log_file=None,
                max_requests_per_minute=5,
                repo_watch_poll_seconds=30,
                service_watch_poll_seconds=30,
                max_watched_repos_per_user=5,
                important_services=("codi.service",),
                important_pm2_apps=(),
                alert_targets_path=self.workspace / "codi-alert-targets.json",
                enable_device_registry=False,
                device_registry_path=self.workspace / "codi-devices.json",
                device_api_host="127.0.0.1",
                device_api_port=8787,
                device_api_shared_token=None,
                device_heartbeat_ttl_seconds=90,
            )
            resolver = RepoResolver(settings, refresh_interval_seconds=0)
            active_case = Case(
                case_id="c-01",
                owner_user_id=1,
                repo_root=str(business_repo),
                title="pakai repo sales-dashboard",
            )

            resolution = resolver.resolve("schema database bisnis", active_case=active_case)

            self.assertEqual(resolution.root, business_repo)
            self.assertTrue(resolution.used_active_case)

    def test_contextual_repo_hint_reuses_active_session(self) -> None:
        active_session = Session(
            session_id="s-02",
            owner_user_id=1,
            role="builder",
            cwd=str(self.project_codi),
            summary="- cek repo AI-Agent-Telegram",
        )

        for prompt in (
            "edit README.md di repo ini",
            "edit README.md di project ini",
            "edit README.md di repo project",
        ):
            resolution = self.resolver.resolve(prompt, active_session)
            self.assertEqual(resolution.root, self.project_codi)
            self.assertTrue(resolution.used_active_session)

    def test_ambiguous_repo_hint_raises(self) -> None:
        with self.assertRaises(RepoResolverError) as captured:
            self.resolver.resolve("cek repo payroll")

        self.assertIn("beberapa repo yang mirip", str(captured.exception))

    def test_unknown_repo_hint_raises(self) -> None:
        with self.assertRaises(RepoResolverError) as captured:
            self.resolver.resolve("cek repo totally-unknown-service")

        self.assertIn("belum menemukan repo", str(captured.exception))

    def test_unique_fuzzy_hint_resolves_single_repo(self) -> None:
        other_tempdir = tempfile.TemporaryDirectory()
        try:
            other_workspace = Path(other_tempdir.name).resolve()
            unique_repo = other_workspace / "backend-observability"
            (unique_repo / ".git").mkdir(parents=True)
            unique_settings = Settings(
                assistant_name="Codi",
                enable_desktop_actions=True,
                enable_local_shell=True,
                telegram_bot_token="token",
                allowed_user_ids=(1,),
                admin_user_ids=(),
                viewer_user_ids=(),
                business_user_ids=(),
                business_allowed_dirs=(),
                business_database_paths=(),
                business_database_urls=(),
                ai_backend="codex",
                codex_bin="codex",
                claude_timeout=180,
                codex_reasoning_effort="medium",
                codex_write_sandbox_mode="workspace-write",
                claude_work_dir=other_workspace,
                claude_bin="claude",
                claude_model="claude-sonnet-4-6",
                allowed_work_dirs=(other_workspace,),
                default_role="general",
                max_active_sessions=4,
                max_sessions_per_user=3,
                session_idle_ttl_minutes=60,
                max_queue_per_session=1,
                max_output_length=3000,
                local_shell_timeout=120,
                log_level="INFO",
                log_file=None,
                max_requests_per_minute=5,
                repo_watch_poll_seconds=30,
                service_watch_poll_seconds=30,
                max_watched_repos_per_user=5,
                important_services=("codi.service",),
                important_pm2_apps=(),
                alert_targets_path=other_workspace / "codi-alert-targets.json",
                enable_device_registry=False,
                device_registry_path=other_workspace / "codi-devices.json",
                device_api_host="127.0.0.1",
                device_api_port=8787,
                device_api_shared_token=None,
                device_heartbeat_ttl_seconds=90,
            )
            resolver = RepoResolver(unique_settings, refresh_interval_seconds=0)

            resolution = resolver.resolve("review repo observability")

            self.assertEqual(resolution.root, unique_repo)
        finally:
            other_tempdir.cleanup()

    def _make_repo(self, name: str) -> Path:
        repo_root = self.workspace / name
        (repo_root / ".git").mkdir(parents=True)
        return repo_root

    def _make_project(self, name: str) -> Path:
        project_root = self.workspace / name
        project_root.mkdir(parents=True)
        (project_root / "requirements.txt").write_text("python-telegram-bot\n", encoding="utf-8")
        (project_root / "main.py").write_text("print('hello')\n", encoding="utf-8")
        return project_root


if __name__ == "__main__":
    unittest.main()
