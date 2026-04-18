"""Local shell execution helpers for trusted Telegram commands."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path

LOCAL_SHELL_PREFIXES: tuple[tuple[str, str], ...] = (
    ("powershell:", "powershell"),
    ("pwsh:", "pwsh"),
    ("bash:", "bash"),
    ("zsh:", "zsh"),
    ("sh:", "sh"),
    ("shell:", "default"),
)
RESTART_SELF_HINTS = {
    "restart codi",
    "restart bot",
    "restart bot ini",
    "restart dirimu",
    "restart diri",
    "reload codi",
    "mulai ulang codi",
    "mulai ulang bot",
}
REPO_CONTEXT_PHRASES = (
    "repo ini",
    "project ini",
    "proyek ini",
    "folder ini",
    "workspace ini",
)
SHORTCUT_SCOPE_HINTS = (
    "repo",
    "project",
    "proyek",
    "workspace",
    "folder",
    "frontend",
    "front end",
    "web",
    "dashboard",
    "mobile",
    "backend",
    "api",
    "node",
    "npm",
    "pnpm",
    "yarn",
)
BUILD_LIKE_ACTIONS = {
    "node_build",
    "node_publish",
    "node_test",
    "node_lint",
    "node_install",
    "node_deploy",
    "backend_build",
    "backend_publish",
    "backend_test",
    "backend_install",
    "backend_deploy",
}
SAFE_GIT_REF_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}")
SAFE_GIT_COMMIT_PATTERN = re.compile(r"[A-Fa-f0-9]{7,40}")
SAFE_SYSTEMD_UNIT_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9@._-]{0,127}")
SYSTEMD_UNIT_SUFFIXES = (
    ".service",
    ".socket",
    ".timer",
    ".target",
    ".path",
    ".mount",
    ".automount",
    ".scope",
    ".slice",
)


class LocalShellError(RuntimeError):
    """Raised when a local shell command cannot be executed safely."""


@dataclass(frozen=True)
class LocalShellRequest:
    """A structured local-shell request parsed from a Telegram message."""

    shell: str
    command: str


@dataclass(frozen=True)
class RepoShellShortcutRequest:
    """A structured repo-scoped shortcut that maps to a local shell command."""

    action: str
    repo_hint: str
    original_prompt: str
    branch_name: str | None = None
    source_branch: str | None = None
    target_branch: str | None = None
    commit_message: str | None = None
    commit_sha: str | None = None
    tag_name: str | None = None
    force: bool = False
    stage_all: bool = False


@dataclass(frozen=True)
class ServiceShellShortcutRequest:
    """A structured systemd service shortcut mapped to local shell commands."""

    action: str
    original_prompt: str
    unit_name: str | None = None
    unit_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class LocalShellResult:
    """Normalized result from a local shell invocation."""

    shell: str
    shell_path: str
    command: str
    cwd: Path
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


class LocalShellService:
    """Run explicit local shell commands outside the Codex sandbox."""

    def __init__(
        self,
        *,
        enabled: bool,
        default_cwd: Path,
        timeout: int = 120,
    ) -> None:
        self._enabled = enabled
        self._default_cwd = default_cwd.resolve()
        self._timeout = timeout

    async def run(
        self,
        request: LocalShellRequest,
        *,
        cwd: Path | None = None,
    ) -> LocalShellResult:
        """Execute a local shell command and capture its output."""

        if not self._enabled:
            raise LocalShellError(
                "Eksekusi shell lokal belum diaktifkan di konfigurasi Codi."
            )
        command = request.command.strip()
        if not command:
            raise LocalShellError("Perintah shell kosong. Tulis setelah prefix seperti `shell:`.")

        resolved_cwd = (cwd or self._default_cwd).expanduser().resolve()
        if not resolved_cwd.exists() or not resolved_cwd.is_dir():
            raise LocalShellError(f"Folder kerja shell tidak valid: {resolved_cwd}")

        shell_path, args = _build_shell_invocation(request.shell, command)
        process = await asyncio.create_subprocess_exec(
            shell_path,
            *args,
            cwd=str(resolved_cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        timed_out = False
        try:
            stdout_raw, stderr_raw = await asyncio.wait_for(
                process.communicate(),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            timed_out = True
            process.kill()
            stdout_raw, stderr_raw = await process.communicate()

        return LocalShellResult(
            shell=request.shell,
            shell_path=shell_path,
            command=command,
            cwd=resolved_cwd,
            exit_code=124 if timed_out else (process.returncode or 0),
            stdout=_decode_output(stdout_raw),
            stderr=_decode_output(stderr_raw),
            timed_out=timed_out,
        )


def match_local_shell_query(prompt: str) -> LocalShellRequest | None:
    """Return a shell request when the user explicitly asks for local shell access."""

    stripped = prompt.lstrip()
    lowered = stripped.lower()
    for prefix, shell in LOCAL_SHELL_PREFIXES:
        if lowered.startswith(prefix):
            return LocalShellRequest(
                shell=shell,
                command=stripped[len(prefix):].strip(),
            )
    return None


def match_restart_self_query(prompt: str) -> bool:
    """Return whether the prompt explicitly asks Codi to restart itself."""

    normalized = " ".join(prompt.strip().lower().split())
    return normalized in RESTART_SELF_HINTS


def match_repo_shell_shortcut(prompt: str) -> RepoShellShortcutRequest | None:
    """Parse natural repo-operation shortcuts like pull/build/status without `shell:`."""

    normalized = " ".join(prompt.strip().lower().split())
    condensed_prompt = " ".join(prompt.strip().split())
    if not normalized or normalized.startswith("pull request"):
        return None

    structured_shortcut = _match_structured_git_shortcut(condensed_prompt)
    if structured_shortcut is not None:
        return structured_shortcut

    action, target = _match_shortcut_action(normalized)
    if action is None or target is None:
        return None
    if action.startswith("backend_") and "backend" not in target and "api" not in target:
        target = f"backend {target}".strip()

    if not _looks_like_repo_target(target, action):
        return None

    repo_hint = _canonicalize_repo_hint(target)
    if not repo_hint:
        return None

    return RepoShellShortcutRequest(
        action=action,
        repo_hint=repo_hint,
        original_prompt=condensed_prompt,
    )


def build_shell_request_for_repo_shortcut(
    shortcut: RepoShellShortcutRequest,
    repo_root: Path,
) -> LocalShellRequest:
    """Translate a repo shortcut into a concrete local shell command."""

    repo_path = repo_root.resolve()
    if shortcut.action == "git_pull":
        return LocalShellRequest(shell="bash", command="git pull")
    if shortcut.action == "git_push":
        return LocalShellRequest(shell="bash", command="git push")
    if shortcut.action == "git_fetch":
        return LocalShellRequest(shell="bash", command="git fetch --all --prune")
    if shortcut.action == "git_status":
        return LocalShellRequest(shell="bash", command="git status --short --branch")
    if shortcut.action == "git_branch_current":
        return LocalShellRequest(shell="bash", command="git branch --show-current")
    if shortcut.action == "git_branch_list":
        return LocalShellRequest(shell="bash", command="git branch --all --verbose --no-abbrev")
    if shortcut.action == "git_branch_create":
        branch_name = _quote_git_ref(shortcut.branch_name)
        return LocalShellRequest(shell="bash", command=f"git switch -c {branch_name}")
    if shortcut.action == "git_branch_switch":
        branch_name = _quote_git_ref(shortcut.branch_name)
        return LocalShellRequest(shell="bash", command=f"git switch {branch_name}")
    if shortcut.action == "git_branch_merge":
        source_branch = _quote_git_ref(shortcut.source_branch)
        target_branch = _quote_git_ref(shortcut.target_branch)
        return LocalShellRequest(
            shell="bash",
            command=f"git switch {target_branch} && git merge {source_branch}",
        )
    if shortcut.action == "git_branch_delete":
        branch_name = _quote_git_ref(shortcut.branch_name)
        delete_flag = "-D" if shortcut.force else "-d"
        return LocalShellRequest(shell="bash", command=f"git branch {delete_flag} {branch_name}")
    if shortcut.action == "git_branch_rebase":
        source_branch = _quote_git_ref(shortcut.source_branch)
        target_branch = _quote_git_ref(shortcut.target_branch)
        return LocalShellRequest(
            shell="bash",
            command=f"git switch {source_branch} && git rebase {target_branch}",
        )
    if shortcut.action == "git_commit":
        message = _quote_commit_message(shortcut.commit_message)
        if shortcut.stage_all:
            return LocalShellRequest(
                shell="bash",
                command=f"git add -A && git commit -m {message}",
            )
        return LocalShellRequest(shell="bash", command=f"git commit -m {message}")
    if shortcut.action == "git_cherry_pick":
        commit_sha = _quote_git_commit(shortcut.commit_sha)
        return LocalShellRequest(shell="bash", command=f"git cherry-pick {commit_sha}")
    if shortcut.action == "git_rollback_last_commit":
        return LocalShellRequest(shell="bash", command="git revert --no-edit HEAD")
    if shortcut.action == "git_rollback_to_tag":
        tag_name = _quote_git_ref(shortcut.tag_name)
        rollback_message = _quote_commit_message(f"Rollback ke tag {shortcut.tag_name}")
        return LocalShellRequest(
            shell="bash",
            command=(
                f"git revert --no-commit {tag_name}..HEAD "
                f"&& git commit -m {rollback_message}"
            ),
        )
    if shortcut.action == "git_tag_create":
        tag_name = _quote_git_ref(shortcut.tag_name)
        return LocalShellRequest(shell="bash", command=f"git tag {tag_name}")
    if shortcut.action.startswith("backend_"):
        return _build_backend_shell_request(shortcut, repo_path)

    package_json = repo_path / "package.json"
    if not package_json.exists():
        raise LocalShellError(
            f"{repo_path.name} belum terlihat seperti project Node/frontend karena `package.json` tidak ditemukan."
        )

    if shortcut.action == "node_install":
        return LocalShellRequest(
            shell="bash",
            command=_build_package_manager_install_command(repo_path),
        )

    script_name = {
        "node_build": "build",
        "node_publish": "publish",
        "node_deploy": "deploy",
        "node_test": "test",
        "node_lint": "lint",
    }.get(shortcut.action)
    if script_name is None:
        raise LocalShellError("Shortcut repo ini belum punya command shell yang cocok.")
    if not _package_script_exists(package_json, script_name):
        raise LocalShellError(
            f"{repo_path.name} tidak punya script `{script_name}` di package.json."
        )
    return LocalShellRequest(
        shell="bash",
        command=_build_package_manager_run_command(repo_path, script_name),
    )


def match_system_service_shortcut(prompt: str) -> ServiceShellShortcutRequest | None:
    """Parse natural service shortcuts like status/restart/log without `shell:`."""

    condensed_prompt = " ".join(prompt.strip().split())
    if not condensed_prompt:
        return None

    patterns: tuple[tuple[str, str], ...] = (
        ("service_health_all", r"^(?:cek\s+)?health\s+semua\s+serv(?:ice|is)\s+penting$"),
        ("service_health_all", r"^(?:cek\s+)?kesehatan\s+semua\s+serv(?:ice|is)\s+penting$"),
        ("service_health", r"^(?:cek\s+)?health\s+serv(?:ice|is)\s+(.+)$"),
        ("service_health", r"^(?:cek\s+)?kesehatan\s+serv(?:ice|is)\s+(.+)$"),
        ("service_status", r"^(?:cek\s+|lihat\s+|tampilkan\s+)?status\s+serv(?:ice|is)\s+(.+)$"),
        ("service_restart", r"^(?:restart|mulai\s+ulang|reload)\s+serv(?:ice|is)\s+(.+)$"),
        ("service_start", r"^(?:start|jalankan|nyalakan)\s+serv(?:ice|is)\s+(.+)$"),
        ("service_stop", r"^(?:stop|hentikan|matikan)\s+serv(?:ice|is)\s+(.+)$"),
        ("service_logs", r"^(?:(?:lihat|tampilkan|cek)\s+)?log\s+serv(?:ice|is)\s+(.+)$"),
    )
    for action, pattern in patterns:
        match = re.match(pattern, condensed_prompt, re.IGNORECASE)
        if match:
            if action == "service_health_all":
                return ServiceShellShortcutRequest(
                    action=action,
                    original_prompt=condensed_prompt,
                )
            return ServiceShellShortcutRequest(
                action=action,
                original_prompt=condensed_prompt,
                unit_name=_normalize_systemd_unit_name(match.group(1)),
            )
    return None


def build_shell_request_for_service_shortcut(
    shortcut: ServiceShellShortcutRequest,
    *,
    important_services: tuple[str, ...] = (),
) -> LocalShellRequest:
    """Translate a service shortcut into a concrete `systemctl` or `journalctl` call."""

    if shortcut.action == "service_health_all":
        raw_units = important_services or ("codex-agent.service",)
        units = tuple(_quote_systemd_unit(unit) for unit in raw_units)
        units_expr = " ".join(units)
        return LocalShellRequest(
            shell="bash",
            command=(
                "overall=0; "
                f"for unit in {units_expr}; do "
                "printf '==> %s\\n' \"$unit\"; "
                "systemctl --user is-active \"$unit\" || overall=1; "
                "systemctl --user is-enabled \"$unit\" 2>/dev/null || true; "
                "systemctl --user status \"$unit\" --no-pager --full || overall=1; "
                "printf '\\n'; "
                "done; "
                "exit \"$overall\""
            ),
        )

    unit_name = _quote_systemd_unit(shortcut.unit_name)
    if shortcut.action == "service_health":
        return LocalShellRequest(
            shell="bash",
            command=(
                f"systemctl --user is-active {unit_name}; "
                f"systemctl --user is-enabled {unit_name} 2>/dev/null || true; "
                f"systemctl --user status {unit_name} --no-pager --full"
            ),
        )
    if shortcut.action == "service_status":
        return LocalShellRequest(
            shell="bash",
            command=f"systemctl --user status {unit_name} --no-pager --full",
        )
    if shortcut.action == "service_restart":
        return LocalShellRequest(
            shell="bash",
            command=(
                f"systemctl --user restart {unit_name} "
                f"&& systemctl --user status {unit_name} --no-pager --full"
            ),
        )
    if shortcut.action == "service_start":
        return LocalShellRequest(
            shell="bash",
            command=(
                f"systemctl --user start {unit_name} "
                f"&& systemctl --user status {unit_name} --no-pager --full"
            ),
        )
    if shortcut.action == "service_stop":
        return LocalShellRequest(
            shell="bash",
            command=(
                f"systemctl --user stop {unit_name} "
                f"&& systemctl --user status {unit_name} --no-pager --full"
            ),
        )
    if shortcut.action == "service_logs":
        return LocalShellRequest(
            shell="bash",
            command=f"journalctl --user -u {unit_name} -n 100 --no-pager",
        )
    raise LocalShellError("Shortcut service ini belum punya command shell yang cocok.")


def _build_shell_invocation(shell_name: str, command: str) -> tuple[str, list[str]]:
    shell_path = _resolve_shell_binary(shell_name)
    if shell_name in {"pwsh", "powershell"}:
        return (
            shell_path,
            ["-NoLogo", "-NoProfile", "-Command", command],
        )
    return (
        shell_path,
        ["-lc", command],
    )


def _resolve_shell_binary(shell_name: str) -> str:
    candidates = _shell_candidates(shell_name)
    for candidate in candidates:
        if not candidate:
            continue
        if os.path.isabs(candidate) and Path(candidate).exists():
            return candidate
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    if shell_name in {"pwsh", "powershell"}:
        raise LocalShellError(
            "PowerShell belum tersedia di laptop ini. Pastikan `pwsh` atau `powershell` terpasang."
        )
    raise LocalShellError(f"Shell `{shell_name}` tidak tersedia di laptop ini.")


def _shell_candidates(shell_name: str) -> tuple[str, ...]:
    if shell_name == "default":
        env_shell = (os.environ.get("SHELL") or "").strip()
        env_shell_name = Path(env_shell).name if env_shell else ""
        return (env_shell, env_shell_name, "bash", "sh")
    if shell_name == "bash":
        return ("bash", "/bin/bash")
    if shell_name == "sh":
        return ("sh", "/bin/sh")
    if shell_name == "zsh":
        return ("zsh", "/bin/zsh")
    if shell_name in {"pwsh", "powershell"}:
        return ("pwsh", "powershell", "powershell.exe")
    return (shell_name,)


def _decode_output(raw: bytes | None) -> str:
    if not raw:
        return ""
    return raw.decode("utf-8", errors="replace")


def _match_shortcut_action(normalized_prompt: str) -> tuple[str | None, str | None]:
    patterns: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("git_pull", ("pull ",)),
        ("git_push", ("push ",)),
        ("git_fetch", ("fetch ",)),
        ("git_branch_list", ("list branch ", "daftar branch ", "lihat semua branch ", "tampilkan semua branch ")),
        ("git_branch_current", ("cek branch ", "lihat branch ", "tampilkan branch ", "branch ")),
        ("git_status", ("cek status ", "lihat status ", "tampilkan status ", "status ")),
        ("backend_build", ("build backend ", "build api ")),
        ("backend_publish", ("publish backend ", "publish api ")),
        ("backend_deploy", ("deploy backend ", "deploy api ")),
        ("backend_test", ("test backend ", "test api ")),
        ("backend_install", ("install backend ", "install api ")),
        ("node_build", ("build ", "build frontend ", "build web ", "build dashboard ")),
        ("node_publish", ("publish build ", "publish ",)),
        ("node_deploy", ("deploy ", "deploy frontend ", "deploy web ", "deploy dashboard ")),
        ("node_test", ("test ", "test frontend ", "test web ", "test dashboard ")),
        ("node_lint", ("lint ", "lint frontend ", "lint web ", "lint dashboard ")),
        ("node_install", ("install ", "install frontend ", "install web ", "install dashboard ")),
    )
    for action, prefixes in patterns:
        for prefix in prefixes:
            if normalized_prompt.startswith(prefix):
                return action, normalized_prompt[len(prefix):].strip()
    return None, None


def _match_structured_git_shortcut(
    prompt: str,
) -> RepoShellShortcutRequest | None:
    create_match = re.match(
        r"^(?:buat(?:kan)?|create)\s+branch\s+([A-Za-z0-9._/-]+)\s+(?:di|untuk)\s+(.+)$",
        prompt,
        re.IGNORECASE,
    )
    if create_match:
        return RepoShellShortcutRequest(
            action="git_branch_create",
            repo_hint=_canonicalize_repo_hint(create_match.group(2)),
            original_prompt=prompt,
            branch_name=create_match.group(1),
        )

    switch_match = re.match(
        r"^(?:switch|pindah|ganti|checkout)\s+(?:ke\s+)?branch\s+([A-Za-z0-9._/-]+)\s+(?:di|untuk)\s+(.+)$",
        prompt,
        re.IGNORECASE,
    )
    if switch_match:
        return RepoShellShortcutRequest(
            action="git_branch_switch",
            repo_hint=_canonicalize_repo_hint(switch_match.group(2)),
            original_prompt=prompt,
            branch_name=switch_match.group(1),
        )

    merge_match = re.match(
        r"^merge\s+(?:branch\s+)?([A-Za-z0-9._/-]+)\s+ke\s+(?:branch\s+)?([A-Za-z0-9._/-]+)\s+(?:di|untuk)\s+(.+)$",
        prompt,
        re.IGNORECASE,
    )
    if merge_match:
        return RepoShellShortcutRequest(
            action="git_branch_merge",
            repo_hint=_canonicalize_repo_hint(merge_match.group(3)),
            original_prompt=prompt,
            source_branch=merge_match.group(1),
            target_branch=merge_match.group(2),
        )

    delete_match = re.match(
        r"^(hapus|delete)\s+(paksa\s+)?branch\s+([A-Za-z0-9._/-]+)\s+(?:di|untuk)\s+(.+)$",
        prompt,
        re.IGNORECASE,
    )
    if delete_match:
        return RepoShellShortcutRequest(
            action="git_branch_delete",
            repo_hint=_canonicalize_repo_hint(delete_match.group(4)),
            original_prompt=prompt,
            branch_name=delete_match.group(3),
            force=bool(delete_match.group(2)),
        )

    rebase_match = re.match(
        r"^rebase\s+(?:branch\s+)?([A-Za-z0-9._/-]+)\s+ke\s+(?:branch\s+)?([A-Za-z0-9._/-]+)\s+(?:di|untuk)\s+(.+)$",
        prompt,
        re.IGNORECASE,
    )
    if rebase_match:
        return RepoShellShortcutRequest(
            action="git_branch_rebase",
            repo_hint=_canonicalize_repo_hint(rebase_match.group(3)),
            original_prompt=prompt,
            source_branch=rebase_match.group(1),
            target_branch=rebase_match.group(2),
        )

    commit_match = re.match(
        r'^(?:buat(?:kan)?\s+)?commit\s+(?:(?:di|untuk)\s+)?(.+?)\s+dengan\s+pesan\s+["\'](.+?)["\']$',
        prompt,
        re.IGNORECASE,
    )
    commit_all_match = re.match(
        r'^(?:buat(?:kan)?\s+)?commit\s+semua\s+perubahan\s+(?:(?:di|untuk)\s+)?(.+?)\s+dengan\s+pesan\s+["\'](.+?)["\']$',
        prompt,
        re.IGNORECASE,
    )
    if commit_all_match:
        return RepoShellShortcutRequest(
            action="git_commit",
            repo_hint=_canonicalize_repo_hint(commit_all_match.group(1)),
            original_prompt=prompt,
            commit_message=commit_all_match.group(2),
            stage_all=True,
        )
    if commit_match:
        return RepoShellShortcutRequest(
            action="git_commit",
            repo_hint=_canonicalize_repo_hint(commit_match.group(1)),
            original_prompt=prompt,
            commit_message=commit_match.group(2),
        )

    cherry_pick_match = re.match(
        r"^cherry-pick\s+commit\s+([A-Fa-f0-9]{7,40})\s+(?:di|untuk)\s+(.+)$",
        prompt,
        re.IGNORECASE,
    )
    if cherry_pick_match:
        return RepoShellShortcutRequest(
            action="git_cherry_pick",
            repo_hint=_canonicalize_repo_hint(cherry_pick_match.group(2)),
            original_prompt=prompt,
            commit_sha=cherry_pick_match.group(1),
        )

    rollback_match = re.match(
        r"^rollback\s+commit\s+terakhir\s+(?:di|untuk)\s+(.+)$",
        prompt,
        re.IGNORECASE,
    )
    if rollback_match:
        return RepoShellShortcutRequest(
            action="git_rollback_last_commit",
            repo_hint=_canonicalize_repo_hint(rollback_match.group(1)),
            original_prompt=prompt,
        )

    rollback_tag_match = re.match(
        r"^rollback\s+(?:ke\s+)?(?:tag|versi)\s+([A-Za-z0-9._/-]+)\s+(?:di|untuk)\s+(.+)$",
        prompt,
        re.IGNORECASE,
    )
    if rollback_tag_match:
        return RepoShellShortcutRequest(
            action="git_rollback_to_tag",
            repo_hint=_canonicalize_repo_hint(rollback_tag_match.group(2)),
            original_prompt=prompt,
            tag_name=rollback_tag_match.group(1),
        )

    tag_match = re.match(
        r"^(?:buat(?:kan)?\s+)?tag\s+([A-Za-z0-9._/-]+)\s+(?:di|untuk)\s+(.+)$",
        prompt,
        re.IGNORECASE,
    )
    if tag_match:
        return RepoShellShortcutRequest(
            action="git_tag_create",
            repo_hint=_canonicalize_repo_hint(tag_match.group(2)),
            original_prompt=prompt,
            tag_name=tag_match.group(1),
        )

    return None


def _looks_like_repo_target(target: str, action: str) -> bool:
    if not target:
        return False
    if any(phrase in target for phrase in REPO_CONTEXT_PHRASES):
        return True
    if any(hint in target for hint in SHORTCUT_SCOPE_HINTS):
        return True
    if re.search(r"[a-z0-9]+[-_/][a-z0-9]+", target):
        return True
    if action not in BUILD_LIKE_ACTIONS and target.startswith("repo "):
        return True
    return False


def _canonicalize_repo_hint(target: str) -> str:
    normalized = " ".join(target.strip().lower().split())
    if not normalized:
        return ""
    if any(phrase == normalized for phrase in REPO_CONTEXT_PHRASES):
        return normalized

    hint = normalized
    replacements = (
        (r"\bfront\s+end\b", "web dashboard"),
        (r"\bfrontend\b", "web dashboard"),
        (r"\bdashboard\b", "dashboard"),
        (r"\bwebsite\b", "web"),
        (r"\bweb app\b", "web"),
    )
    for pattern, replacement in replacements:
        hint = re.sub(pattern, replacement, hint)
    hint = re.sub(r"\b(aplikasi|app)\b", " ", hint)
    hint = re.sub(r"\s+", " ", hint).strip()
    return hint


def _build_package_manager_install_command(repo_root: Path) -> str:
    manager = _detect_package_manager(repo_root)
    if manager == "pnpm":
        return "pnpm install"
    if manager == "yarn":
        return "yarn install"
    if manager == "bun":
        return "bun install"
    return "npm install"


def _build_package_manager_run_command(repo_root: Path, script_name: str) -> str:
    manager = _detect_package_manager(repo_root)
    if manager == "pnpm":
        return f"pnpm run {script_name}"
    if manager == "yarn":
        return f"yarn run {script_name}"
    if manager == "bun":
        return f"bun run {script_name}"
    return f"npm run {script_name}"


def _build_backend_shell_request(
    shortcut: RepoShellShortcutRequest,
    repo_root: Path,
) -> LocalShellRequest:
    action_to_script = {
        "backend_build": "build",
        "backend_publish": "publish",
        "backend_deploy": "deploy",
        "backend_test": "test",
        "backend_install": "install",
    }
    script_name = action_to_script.get(shortcut.action)
    if script_name is None:
        raise LocalShellError("Shortcut backend ini belum punya command shell yang cocok.")

    package_json = repo_root / "package.json"
    if package_json.exists() and _package_script_exists(package_json, script_name):
        return LocalShellRequest(
            shell="bash",
            command=_build_package_manager_run_command(repo_root, script_name),
        )

    makefile = _resolve_makefile(repo_root)
    if makefile is not None and _make_target_exists(makefile, script_name):
        return LocalShellRequest(shell="bash", command=f"make {script_name}")

    command = _build_python_backend_command(repo_root, shortcut.action)
    return LocalShellRequest(shell="bash", command=command)


def _build_python_backend_command(repo_root: Path, action: str) -> str:
    if not _looks_like_python_backend(repo_root):
        raise LocalShellError(
            f"{repo_root.name} belum punya jalur backend yang dikenali untuk shortcut ini."
        )

    if action == "backend_install":
        if (repo_root / "uv.lock").exists():
            return "uv sync"
        if (repo_root / "poetry.lock").exists():
            return "poetry install"
        if (repo_root / "requirements.txt").exists():
            return "pip install -r requirements.txt"
        return "pip install -e ."

    if action == "backend_test":
        if (repo_root / "uv.lock").exists():
            return "uv run pytest"
        if (repo_root / "poetry.lock").exists():
            return "poetry run pytest"
        return "pytest"

    if action == "backend_build":
        if (repo_root / "poetry.lock").exists():
            return "poetry build"
        return "python -m build"

    if action == "backend_publish":
        if (repo_root / "poetry.lock").exists():
            return "poetry publish --build"
        raise LocalShellError(
            f"{repo_root.name} tidak punya shortcut publish backend yang dikenali. "
            "Tambahkan script `publish`, target `make publish`, atau tooling Poetry."
        )

    if action == "backend_deploy":
        raise LocalShellError(
            f"{repo_root.name} tidak punya shortcut deploy backend yang dikenali. "
            "Tambahkan script `deploy` atau target `make deploy` di repo ini."
        )

    raise LocalShellError("Shortcut backend ini belum punya command shell yang cocok.")


def _resolve_makefile(repo_root: Path) -> Path | None:
    for filename in ("Makefile", "makefile"):
        candidate = repo_root / filename
        if candidate.exists():
            return candidate
    return None


def _make_target_exists(makefile_path: Path, target_name: str) -> bool:
    pattern = re.compile(rf"^{re.escape(target_name)}\s*:", re.MULTILINE)
    try:
        content = makefile_path.read_text(encoding="utf-8")
    except OSError:
        return False
    return bool(pattern.search(content))


def _looks_like_python_backend(repo_root: Path) -> bool:
    markers = (
        "pyproject.toml",
        "requirements.txt",
        "setup.py",
        "manage.py",
    )
    return any((repo_root / marker).exists() for marker in markers)


def _detect_package_manager(repo_root: Path) -> str:
    if (repo_root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (repo_root / "yarn.lock").exists():
        return "yarn"
    if (repo_root / "bun.lockb").exists() or (repo_root / "bun.lock").exists():
        return "bun"
    return "npm"


def _package_script_exists(package_json: Path, script_name: str) -> bool:
    try:
        payload = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    scripts = payload.get("scripts")
    return isinstance(scripts, dict) and isinstance(scripts.get(script_name), str)


def _quote_git_ref(ref_name: str | None) -> str:
    if ref_name is None:
        raise LocalShellError("Nama branch belum terbaca dari prompt.")
    candidate = ref_name.strip()
    if not candidate or not SAFE_GIT_REF_PATTERN.fullmatch(candidate):
        raise LocalShellError(
            f"Nama branch `{ref_name}` tidak aman atau belum didukung untuk shortcut ini."
        )
    if candidate.startswith((".", "-", "/")) or candidate.endswith(("/", ".")):
        raise LocalShellError(
            f"Nama branch `{ref_name}` tidak aman atau belum didukung untuk shortcut ini."
        )
    if ".." in candidate or "//" in candidate:
        raise LocalShellError(
            f"Nama branch `{ref_name}` tidak aman atau belum didukung untuk shortcut ini."
        )
    return shlex.quote(candidate)


def _quote_commit_message(message: str | None) -> str:
    if message is None:
        raise LocalShellError("Pesan commit belum terbaca dari prompt.")
    candidate = " ".join(message.strip().split())
    if not candidate:
        raise LocalShellError("Pesan commit tidak boleh kosong.")
    if len(candidate) > 300:
        raise LocalShellError("Pesan commit terlalu panjang untuk shortcut natural ini.")
    return shlex.quote(candidate)


def _quote_git_commit(commit_sha: str | None) -> str:
    if commit_sha is None:
        raise LocalShellError("Hash commit belum terbaca dari prompt.")
    candidate = commit_sha.strip()
    if not SAFE_GIT_COMMIT_PATTERN.fullmatch(candidate):
        raise LocalShellError(
            f"Hash commit `{commit_sha}` tidak aman atau belum didukung untuk shortcut ini."
        )
    return shlex.quote(candidate)


def _normalize_systemd_unit_name(raw_target: str) -> str:
    candidate = "-".join(raw_target.strip().split())
    if not candidate:
        raise LocalShellError("Nama service belum terbaca dari prompt.")
    if not any(candidate.endswith(suffix) for suffix in SYSTEMD_UNIT_SUFFIXES):
        candidate = f"{candidate}.service"
    return candidate


def _quote_systemd_unit(unit_name: str | None) -> str:
    if unit_name is None:
        raise LocalShellError("Nama service belum terbaca dari prompt.")
    candidate = unit_name.strip()
    if not candidate or not SAFE_SYSTEMD_UNIT_PATTERN.fullmatch(candidate):
        raise LocalShellError(
            f"Nama service `{unit_name}` tidak aman atau belum didukung untuk shortcut ini."
        )
    if candidate.startswith((".", "-", "@")) or ".." in candidate or "//" in candidate:
        raise LocalShellError(
            f"Nama service `{unit_name}` tidak aman atau belum didukung untuk shortcut ini."
        )
    return shlex.quote(candidate)
