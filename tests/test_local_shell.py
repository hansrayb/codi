"""Tests for direct local-shell execution helpers."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.local_shell import (
    LocalShellRequest,
    LocalShellService,
    LocalShellError,
    RepoShellShortcutRequest,
    build_shell_request_for_repo_shortcut,
    match_local_shell_query,
    match_repo_shell_shortcut,
    match_restart_self_query,
)


class LocalShellQueryTests(unittest.TestCase):
    """Validate explicit shell-prefix parsing."""

    def test_bash_prefix_is_detected(self) -> None:
        request = match_local_shell_query("bash: git status --short")
        self.assertEqual(
            request,
            LocalShellRequest(shell="bash", command="git status --short"),
        )

    def test_powershell_prefix_is_detected(self) -> None:
        request = match_local_shell_query("pwsh: Get-Process | Select-Object -First 5")
        self.assertEqual(
            request,
            LocalShellRequest(
                shell="pwsh",
                command="Get-Process | Select-Object -First 5",
            ),
        )

    def test_restart_self_query_is_detected(self) -> None:
        self.assertTrue(match_restart_self_query("restart codi"))
        self.assertTrue(match_restart_self_query("mulai ulang codi"))
        self.assertFalse(match_restart_self_query("restart service postgres"))

    def test_repo_shortcut_git_is_detected(self) -> None:
        request = match_repo_shell_shortcut("pull repo ini")
        self.assertEqual(
            request,
            RepoShellShortcutRequest(
                action="git_pull",
                repo_hint="repo ini",
                original_prompt="pull repo ini",
            ),
        )

    def test_repo_shortcut_frontend_build_is_detected(self) -> None:
        request = match_repo_shell_shortcut("build frontend payroll")
        self.assertEqual(
            request,
            RepoShellShortcutRequest(
                action="node_build",
                repo_hint="web dashboard payroll",
                original_prompt="build frontend payroll",
            ),
        )

    def test_repo_shortcut_branch_create_is_detected(self) -> None:
        request = match_repo_shell_shortcut("buat branch fitur/login di repo ini")
        self.assertEqual(
            request,
            RepoShellShortcutRequest(
                action="git_branch_create",
                repo_hint="repo ini",
                original_prompt="buat branch fitur/login di repo ini",
                branch_name="fitur/login",
            ),
        )

    def test_repo_shortcut_branch_switch_is_detected(self) -> None:
        request = match_repo_shell_shortcut("switch ke branch main di repo AI-Agent-Telegram")
        self.assertEqual(
            request,
            RepoShellShortcutRequest(
                action="git_branch_switch",
                repo_hint="repo ai-agent-telegram",
                original_prompt="switch ke branch main di repo AI-Agent-Telegram",
                branch_name="main",
            ),
        )

    def test_repo_shortcut_preserves_branch_case(self) -> None:
        request = match_repo_shell_shortcut("buat branch Release/QA di repo ini")
        self.assertEqual(
            request,
            RepoShellShortcutRequest(
                action="git_branch_create",
                repo_hint="repo ini",
                original_prompt="buat branch Release/QA di repo ini",
                branch_name="Release/QA",
            ),
        )

    def test_repo_shortcut_branch_merge_is_detected(self) -> None:
        request = match_repo_shell_shortcut("merge branch staging ke main di repo ini")
        self.assertEqual(
            request,
            RepoShellShortcutRequest(
                action="git_branch_merge",
                repo_hint="repo ini",
                original_prompt="merge branch staging ke main di repo ini",
                source_branch="staging",
                target_branch="main",
            ),
        )

    def test_repo_shortcut_branch_delete_is_detected(self) -> None:
        request = match_repo_shell_shortcut("hapus branch fitur/login di repo ini")
        self.assertEqual(
            request,
            RepoShellShortcutRequest(
                action="git_branch_delete",
                repo_hint="repo ini",
                original_prompt="hapus branch fitur/login di repo ini",
                branch_name="fitur/login",
            ),
        )

    def test_repo_shortcut_force_branch_delete_is_detected(self) -> None:
        request = match_repo_shell_shortcut("hapus paksa branch fitur/login di repo ini")
        self.assertEqual(
            request,
            RepoShellShortcutRequest(
                action="git_branch_delete",
                repo_hint="repo ini",
                original_prompt="hapus paksa branch fitur/login di repo ini",
                branch_name="fitur/login",
                force=True,
            ),
        )

    def test_repo_shortcut_branch_rebase_is_detected(self) -> None:
        request = match_repo_shell_shortcut("rebase branch fitur/login ke main di repo ini")
        self.assertEqual(
            request,
            RepoShellShortcutRequest(
                action="git_branch_rebase",
                repo_hint="repo ini",
                original_prompt="rebase branch fitur/login ke main di repo ini",
                source_branch="fitur/login",
                target_branch="main",
            ),
        )

    def test_repo_shortcut_commit_with_message_is_detected(self) -> None:
        request = match_repo_shell_shortcut('commit repo ini dengan pesan "Update payroll flow"')
        self.assertEqual(
            request,
            RepoShellShortcutRequest(
                action="git_commit",
                repo_hint="repo ini",
                original_prompt='commit repo ini dengan pesan "Update payroll flow"',
                commit_message="Update payroll flow",
            ),
        )

    def test_repo_shortcut_commit_all_with_message_is_detected(self) -> None:
        request = match_repo_shell_shortcut(
            'commit semua perubahan di repo ini dengan pesan "Update payroll flow"'
        )
        self.assertEqual(
            request,
            RepoShellShortcutRequest(
                action="git_commit",
                repo_hint="repo ini",
                original_prompt='commit semua perubahan di repo ini dengan pesan "Update payroll flow"',
                commit_message="Update payroll flow",
                stage_all=True,
            ),
        )

    def test_repo_shortcut_cherry_pick_is_detected(self) -> None:
        request = match_repo_shell_shortcut("cherry-pick commit a1b2c3d di repo ini")
        self.assertEqual(
            request,
            RepoShellShortcutRequest(
                action="git_cherry_pick",
                repo_hint="repo ini",
                original_prompt="cherry-pick commit a1b2c3d di repo ini",
                commit_sha="a1b2c3d",
            ),
        )

    def test_repo_shortcut_deploy_is_detected(self) -> None:
        request = match_repo_shell_shortcut("deploy frontend payroll")
        self.assertEqual(
            request,
            RepoShellShortcutRequest(
                action="node_deploy",
                repo_hint="web dashboard payroll",
                original_prompt="deploy frontend payroll",
            ),
        )

    def test_repo_shortcut_publish_build_is_detected(self) -> None:
        request = match_repo_shell_shortcut("publish build frontend payroll")
        self.assertEqual(
            request,
            RepoShellShortcutRequest(
                action="node_publish",
                repo_hint="web dashboard payroll",
                original_prompt="publish build frontend payroll",
            ),
        )

    def test_repo_shortcut_rollback_last_commit_is_detected(self) -> None:
        request = match_repo_shell_shortcut("rollback commit terakhir di repo ini")
        self.assertEqual(
            request,
            RepoShellShortcutRequest(
                action="git_rollback_last_commit",
                repo_hint="repo ini",
                original_prompt="rollback commit terakhir di repo ini",
            ),
        )

    def test_repo_shortcut_tag_create_is_detected(self) -> None:
        request = match_repo_shell_shortcut("buat tag v1.2.3 di repo ini")
        self.assertEqual(
            request,
            RepoShellShortcutRequest(
                action="git_tag_create",
                repo_hint="repo ini",
                original_prompt="buat tag v1.2.3 di repo ini",
                tag_name="v1.2.3",
            ),
        )

    def test_non_repo_build_prompt_is_not_treated_as_shell_shortcut(self) -> None:
        self.assertIsNone(match_repo_shell_shortcut("build fitur payroll baru"))


class LocalShellServiceTests(unittest.IsolatedAsyncioTestCase):
    """Validate local-shell process execution behavior."""

    async def test_service_uses_bash_with_lc(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = LocalShellService(
                enabled=True,
                default_cwd=Path(temp_dir),
                timeout=5,
            )
            seen = {}

            class FakeProcess:
                returncode = 0

                async def communicate(self):
                    return (b"ok\n", b"")

                def kill(self):
                    seen["killed"] = True

            async def fake_create_subprocess_exec(*args, **kwargs):
                seen["args"] = args
                seen["cwd"] = kwargs.get("cwd")
                return FakeProcess()

            with patch("core.local_shell.shutil.which", return_value="/usr/bin/bash"):
                with patch(
                    "core.local_shell.asyncio.create_subprocess_exec",
                    side_effect=fake_create_subprocess_exec,
                ):
                    result = await service.run(
                        LocalShellRequest(shell="bash", command="git status --short")
                    )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.stdout, "ok\n")
        self.assertEqual(seen["args"], ("/usr/bin/bash", "-lc", "git status --short"))
        self.assertEqual(seen["cwd"], temp_dir)

    async def test_service_uses_pwsh_command_flag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = LocalShellService(
                enabled=True,
                default_cwd=Path(temp_dir),
                timeout=5,
            )
            seen = {}

            class FakeProcess:
                returncode = 0

                async def communicate(self):
                    return (b"Name\npython\n", b"")

                def kill(self):
                    seen["killed"] = True

            async def fake_create_subprocess_exec(*args, **kwargs):
                seen["args"] = args
                return FakeProcess()

            with patch("core.local_shell.shutil.which", side_effect=lambda name: "/usr/bin/pwsh" if name == "pwsh" else None):
                with patch(
                    "core.local_shell.asyncio.create_subprocess_exec",
                    side_effect=fake_create_subprocess_exec,
                ):
                    result = await service.run(
                        LocalShellRequest(
                            shell="pwsh",
                            command="Get-Process | Select-Object -First 1",
                        )
                    )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            seen["args"],
            (
                "/usr/bin/pwsh",
                "-NoLogo",
                "-NoProfile",
                "-Command",
                "Get-Process | Select-Object -First 1",
            ),
        )

    async def test_service_times_out_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = LocalShellService(
                enabled=True,
                default_cwd=Path(temp_dir),
                timeout=1,
            )
            seen = {"killed": False}

            class FakeProcess:
                returncode = None

                async def communicate(self):
                    return (b"", b"")

                def kill(self):
                    seen["killed"] = True

            async def fake_wait_for(awaitable, timeout):
                del timeout
                close = getattr(awaitable, "close", None)
                if callable(close):
                    close()
                raise asyncio.TimeoutError

            async def fake_create_subprocess_exec(*args, **kwargs):
                return FakeProcess()

            with patch("core.local_shell.shutil.which", return_value="/usr/bin/bash"):
                with patch(
                    "core.local_shell.asyncio.create_subprocess_exec",
                    side_effect=fake_create_subprocess_exec,
                ):
                    with patch("core.local_shell.asyncio.wait_for", side_effect=fake_wait_for):
                        result = await service.run(
                            LocalShellRequest(shell="bash", command="sleep 5")
                        )

        self.assertTrue(result.timed_out)
        self.assertEqual(result.exit_code, 124)
        self.assertTrue(seen["killed"])


class RepoShortcutCommandBuilderTests(unittest.TestCase):
    """Validate mapping from natural shortcuts to concrete commands."""

    def test_git_shortcut_maps_to_git_pull(self) -> None:
        request = build_shell_request_for_repo_shortcut(
            RepoShellShortcutRequest(
                action="git_pull",
                repo_hint="repo ini",
                original_prompt="pull repo ini",
            ),
            Path("/tmp/repo"),
        )

        self.assertEqual(request, LocalShellRequest(shell="bash", command="git pull"))

    def test_node_build_uses_npm_when_package_json_has_build_script(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            (repo_root / "package.json").write_text(
                '{"scripts":{"build":"vite build","test":"vitest"}}',
                encoding="utf-8",
            )

            request = build_shell_request_for_repo_shortcut(
                RepoShellShortcutRequest(
                    action="node_build",
                    repo_hint="web dashboard payroll",
                    original_prompt="build frontend payroll",
                ),
                repo_root,
            )

        self.assertEqual(request, LocalShellRequest(shell="bash", command="npm run build"))

    def test_git_branch_create_maps_to_switch_c(self) -> None:
        request = build_shell_request_for_repo_shortcut(
            RepoShellShortcutRequest(
                action="git_branch_create",
                repo_hint="repo ini",
                original_prompt="buat branch fitur/login di repo ini",
                branch_name="fitur/login",
            ),
            Path("/tmp/repo"),
        )

        self.assertEqual(
            request,
            LocalShellRequest(shell="bash", command="git switch -c fitur/login"),
        )

    def test_git_branch_switch_maps_to_git_switch(self) -> None:
        request = build_shell_request_for_repo_shortcut(
            RepoShellShortcutRequest(
                action="git_branch_switch",
                repo_hint="repo ini",
                original_prompt="switch ke branch main di repo ini",
                branch_name="main",
            ),
            Path("/tmp/repo"),
        )

        self.assertEqual(
            request,
            LocalShellRequest(shell="bash", command="git switch main"),
        )

    def test_git_branch_merge_maps_to_switch_and_merge(self) -> None:
        request = build_shell_request_for_repo_shortcut(
            RepoShellShortcutRequest(
                action="git_branch_merge",
                repo_hint="repo ini",
                original_prompt="merge branch staging ke main di repo ini",
                source_branch="staging",
                target_branch="main",
            ),
            Path("/tmp/repo"),
        )

        self.assertEqual(
            request,
            LocalShellRequest(shell="bash", command="git switch main && git merge staging"),
        )

    def test_git_branch_delete_maps_to_safe_delete(self) -> None:
        request = build_shell_request_for_repo_shortcut(
            RepoShellShortcutRequest(
                action="git_branch_delete",
                repo_hint="repo ini",
                original_prompt="hapus branch fitur/login di repo ini",
                branch_name="fitur/login",
            ),
            Path("/tmp/repo"),
        )

        self.assertEqual(
            request,
            LocalShellRequest(shell="bash", command="git branch -d fitur/login"),
        )

    def test_git_branch_delete_can_force_delete(self) -> None:
        request = build_shell_request_for_repo_shortcut(
            RepoShellShortcutRequest(
                action="git_branch_delete",
                repo_hint="repo ini",
                original_prompt="hapus paksa branch fitur/login di repo ini",
                branch_name="fitur/login",
                force=True,
            ),
            Path("/tmp/repo"),
        )

        self.assertEqual(
            request,
            LocalShellRequest(shell="bash", command="git branch -D fitur/login"),
        )

    def test_git_branch_rebase_maps_to_switch_and_rebase(self) -> None:
        request = build_shell_request_for_repo_shortcut(
            RepoShellShortcutRequest(
                action="git_branch_rebase",
                repo_hint="repo ini",
                original_prompt="rebase branch fitur/login ke main di repo ini",
                source_branch="fitur/login",
                target_branch="main",
            ),
            Path("/tmp/repo"),
        )

        self.assertEqual(
            request,
            LocalShellRequest(shell="bash", command="git switch fitur/login && git rebase main"),
        )

    def test_git_commit_maps_to_commit_message(self) -> None:
        request = build_shell_request_for_repo_shortcut(
            RepoShellShortcutRequest(
                action="git_commit",
                repo_hint="repo ini",
                original_prompt='commit repo ini dengan pesan "Update payroll flow"',
                commit_message="Update payroll flow",
            ),
            Path("/tmp/repo"),
        )

        self.assertEqual(
            request,
            LocalShellRequest(shell="bash", command="git commit -m 'Update payroll flow'"),
        )

    def test_git_commit_all_maps_to_add_and_commit(self) -> None:
        request = build_shell_request_for_repo_shortcut(
            RepoShellShortcutRequest(
                action="git_commit",
                repo_hint="repo ini",
                original_prompt='commit semua perubahan di repo ini dengan pesan "Update payroll flow"',
                commit_message="Update payroll flow",
                stage_all=True,
            ),
            Path("/tmp/repo"),
        )

        self.assertEqual(
            request,
            LocalShellRequest(
                shell="bash",
                command="git add -A && git commit -m 'Update payroll flow'",
            ),
        )

    def test_git_cherry_pick_maps_to_command(self) -> None:
        request = build_shell_request_for_repo_shortcut(
            RepoShellShortcutRequest(
                action="git_cherry_pick",
                repo_hint="repo ini",
                original_prompt="cherry-pick commit a1b2c3d di repo ini",
                commit_sha="a1b2c3d",
            ),
            Path("/tmp/repo"),
        )

        self.assertEqual(
            request,
            LocalShellRequest(shell="bash", command="git cherry-pick a1b2c3d"),
        )

    def test_git_rollback_last_commit_maps_to_revert(self) -> None:
        request = build_shell_request_for_repo_shortcut(
            RepoShellShortcutRequest(
                action="git_rollback_last_commit",
                repo_hint="repo ini",
                original_prompt="rollback commit terakhir di repo ini",
            ),
            Path("/tmp/repo"),
        )

        self.assertEqual(
            request,
            LocalShellRequest(shell="bash", command="git revert --no-edit HEAD"),
        )

    def test_git_tag_create_maps_to_git_tag(self) -> None:
        request = build_shell_request_for_repo_shortcut(
            RepoShellShortcutRequest(
                action="git_tag_create",
                repo_hint="repo ini",
                original_prompt="buat tag v1.2.3 di repo ini",
                tag_name="v1.2.3",
            ),
            Path("/tmp/repo"),
        )

        self.assertEqual(
            request,
            LocalShellRequest(shell="bash", command="git tag v1.2.3"),
        )

    def test_node_build_prefers_pnpm_when_lockfile_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            (repo_root / "package.json").write_text(
                '{"scripts":{"build":"vite build"}}',
                encoding="utf-8",
            )
            (repo_root / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")

            request = build_shell_request_for_repo_shortcut(
                RepoShellShortcutRequest(
                    action="node_build",
                    repo_hint="web dashboard payroll",
                    original_prompt="build frontend payroll",
                ),
                repo_root,
            )

        self.assertEqual(request, LocalShellRequest(shell="bash", command="pnpm run build"))

    def test_node_deploy_uses_deploy_script(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            (repo_root / "package.json").write_text(
                '{"scripts":{"deploy":"vite deploy"}}',
                encoding="utf-8",
            )

            request = build_shell_request_for_repo_shortcut(
                RepoShellShortcutRequest(
                    action="node_deploy",
                    repo_hint="web dashboard payroll",
                    original_prompt="deploy frontend payroll",
                ),
                repo_root,
            )

        self.assertEqual(request, LocalShellRequest(shell="bash", command="npm run deploy"))

    def test_node_publish_uses_publish_script(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            (repo_root / "package.json").write_text(
                '{"scripts":{"publish":"node scripts/publish.js"}}',
                encoding="utf-8",
            )

            request = build_shell_request_for_repo_shortcut(
                RepoShellShortcutRequest(
                    action="node_publish",
                    repo_hint="web dashboard payroll",
                    original_prompt="publish build frontend payroll",
                ),
                repo_root,
            )

        self.assertEqual(request, LocalShellRequest(shell="bash", command="npm run publish"))

    def test_node_build_requires_package_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(LocalShellError):
                build_shell_request_for_repo_shortcut(
                    RepoShellShortcutRequest(
                        action="node_build",
                        repo_hint="web dashboard payroll",
                        original_prompt="build frontend payroll",
                    ),
                    Path(temp_dir),
                )

    def test_git_branch_shortcuts_reject_unsafe_ref_names(self) -> None:
        with self.assertRaises(LocalShellError):
            build_shell_request_for_repo_shortcut(
                RepoShellShortcutRequest(
                    action="git_branch_create",
                    repo_hint="repo ini",
                    original_prompt="buat branch main;rm -rf / di repo ini",
                    branch_name="main;rm",
                ),
                Path("/tmp/repo"),
            )

    def test_git_commit_rejects_empty_message(self) -> None:
        with self.assertRaises(LocalShellError):
            build_shell_request_for_repo_shortcut(
                RepoShellShortcutRequest(
                    action="git_commit",
                    repo_hint="repo ini",
                    original_prompt='commit repo ini dengan pesan ""',
                    commit_message="   ",
                ),
                Path("/tmp/repo"),
            )

    def test_git_cherry_pick_rejects_unsafe_hash(self) -> None:
        with self.assertRaises(LocalShellError):
            build_shell_request_for_repo_shortcut(
                RepoShellShortcutRequest(
                    action="git_cherry_pick",
                    repo_hint="repo ini",
                    original_prompt="cherry-pick commit nope123; di repo ini",
                    commit_sha="nope123;",
                ),
                Path("/tmp/repo"),
            )

    def test_git_tag_rejects_unsafe_name(self) -> None:
        with self.assertRaises(LocalShellError):
            build_shell_request_for_repo_shortcut(
                RepoShellShortcutRequest(
                    action="git_tag_create",
                    repo_hint="repo ini",
                    original_prompt="buat tag v1.2.3;rm di repo ini",
                    tag_name="v1.2.3;rm",
                ),
                Path("/tmp/repo"),
            )


if __name__ == "__main__":
    unittest.main()
