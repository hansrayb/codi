"""Helpers for verifying and restarting Codi after self-updates."""

from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SelfCheckResult:
    """Verification summary after applying changes to the Codi repo."""

    compile_ok: bool
    tests_ok: bool
    compile_output: str
    test_output: str

    @property
    def ready_for_restart(self) -> bool:
        """Return whether the updated bot passed local verification."""

        return self.compile_ok and self.tests_ok


class SelfMaintenanceManager:
    """Run self-update checks and restart the bot process in place."""

    def __init__(
        self,
        *,
        project_root: Path,
        python_bin: str,
        entrypoint: Path,
        logger,
        compile_timeout: int = 90,
        test_timeout: int = 240,
        restart_delay_seconds: float = 1.2,
    ) -> None:
        self._project_root = project_root.resolve()
        self._python_bin = python_bin
        self._entrypoint = entrypoint.resolve()
        self._logger = logger
        self._compile_timeout = compile_timeout
        self._test_timeout = test_timeout
        self._restart_delay_seconds = restart_delay_seconds
        self._restart_scheduled = False
        self._restart_task: asyncio.Task[None] | None = None

    def is_self_repo(self, repo_root: Path) -> bool:
        """Return whether a repo path points at the running Codi project."""

        return repo_root.resolve() == self._project_root

    async def verify_self_update(self) -> SelfCheckResult:
        """Run lightweight verification after applying Codi changes."""

        return await asyncio.to_thread(self._run_checks)

    def schedule_restart(self) -> bool:
        """Schedule an in-place process restart once the current reply is sent."""

        if self._restart_scheduled:
            return False
        self._restart_scheduled = True
        self._restart_task = asyncio.create_task(self._delayed_restart())
        return True

    def cancel_restart(self) -> None:
        """Cancel a scheduled restart, mainly for shutdown paths."""

        if self._restart_task is not None:
            self._restart_task.cancel()
        self._restart_task = None
        self._restart_scheduled = False

    def _run_checks(self) -> SelfCheckResult:
        compile_output, compile_ok = self._run_command(
            [
                self._python_bin,
                "-m",
                "compileall",
                "config.py",
                "main.py",
                "handlers",
                "core",
                "models",
                "utils",
                "tests",
            ],
            timeout=self._compile_timeout,
        )
        test_output, tests_ok = self._run_command(
            [
                self._python_bin,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-v",
            ],
            timeout=self._test_timeout,
        )
        return SelfCheckResult(
            compile_ok=compile_ok,
            tests_ok=tests_ok,
            compile_output=compile_output,
            test_output=test_output,
        )

    def _run_command(self, args: list[str], *, timeout: int) -> tuple[str, bool]:
        try:
            completed = subprocess.run(
                args,
                cwd=self._project_root,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            output = ((exc.stdout or "") + "\n" + (exc.stderr or "")).strip()
            return (output or f"Command timeout setelah {timeout} detik."), False

        output = "\n".join(
            part.strip()
            for part in (completed.stdout or "", completed.stderr or "")
            if part.strip()
        ).strip()
        return output, completed.returncode == 0

    async def _delayed_restart(self) -> None:
        try:
            await asyncio.sleep(self._restart_delay_seconds)
            self._logger.info("action=self_restart | project_root=%s", str(self._project_root))
            os.chdir(self._project_root)
            os.execv(self._python_bin, [self._python_bin, str(self._entrypoint)])
        except asyncio.CancelledError:
            raise
        except Exception:
            self._restart_scheduled = False
            self._logger.exception("action=self_restart_failed")
