"""Safety policy, approvals, modes, and audit logging for host actions."""

from __future__ import annotations

import json
import re
import shlex
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from models.result import MessagePayload

SAFETY_MODES = ("aman", "ops", "admin")
_MODE_RANK = {mode: index for index, mode in enumerate(SAFETY_MODES)}
_PENDING_CONTROL_RE = re.compile(
    r"^(lanjutkan|batal)\s+aksi(?:\s+([A-Za-z0-9-]+))?$",
    re.IGNORECASE,
)
_MODE_CONTROL_RE = re.compile(
    r"^(?:mode|set\s+mode)\s+(aman|ops|admin)$",
    re.IGNORECASE,
)
_MODE_STATUS_RE = re.compile(
    r"^(?:mode\s+saya\s+apa|mode\s+apa|cek\s+mode|status\s+mode)$",
    re.IGNORECASE,
)
_SHELL_ALLOWED_TOP_LEVEL: dict[str, str] = {
    "pwd": "observe",
    "ls": "observe",
    "cat": "observe",
    "sed": "observe",
    "tail": "observe",
    "head": "observe",
    "rg": "observe",
    "find": "observe",
    "ps": "observe",
    "df": "observe",
    "free": "observe",
    "ss": "observe",
    "journalctl": "service",
    "systemctl": "service",
    "git": "repo",
    "npm": "node",
    "pnpm": "node",
    "yarn": "node",
    "bun": "node",
    "python": "python",
    "python3": "python",
    "pytest": "python",
    "uv": "python",
    "poetry": "python",
    "pip": "python",
    "alembic": "python",
    "make": "build",
    "docker": "container",
    "curl": "network",
    "wget": "network",
    "tar": "archive",
}
_SHELL_FORBIDDEN_SNIPPETS = (
    "$(",
    "`",
    "rm -rf /",
    "mkfs",
    "shutdown",
    "reboot",
    "poweroff",
    ":(){",
)


@dataclass(frozen=True, slots=True)
class SafetyPolicy:
    """Permission requirements for an action that touches the host."""

    category: str
    required_mode: str
    requires_confirmation: bool
    summary: str
    preview: str


@dataclass(slots=True)
class PendingSafetyApproval:
    """A host action waiting for explicit confirmation."""

    approval_id: str
    user_id: int
    summary: str
    preview: str
    category: str
    required_mode: str
    kind: str
    payload: Any
    created_at: float
    expires_at: float


@dataclass(frozen=True, slots=True)
class SafetyGateResult:
    """Result of passing an action through the safety layer."""

    allowed: bool
    payload: MessagePayload | None = None


@dataclass(frozen=True, slots=True)
class SafetyControlResult:
    """Result of a safety control message such as mode or approval handling."""

    handled: bool
    payload: MessagePayload | None = None
    pending: PendingSafetyApproval | None = None
    approved: bool = False


class SafetyManager:
    """Track user safety modes, pending approvals, and audit events."""

    def __init__(
        self,
        *,
        assistant_name: str,
        allowed_user_ids: tuple[int, ...],
        default_mode: str = "ops",
        admin_user_ids: tuple[int, ...] | None = None,
        ops_user_ids: tuple[int, ...] | None = None,
        approval_ttl_seconds: int = 180,
        audit_log_path: Path,
        logger,
    ) -> None:
        self._assistant_name = assistant_name
        self._allowed_user_ids = set(allowed_user_ids)
        self._default_mode = _normalize_mode(default_mode)
        self._admin_user_ids = set(admin_user_ids or allowed_user_ids)
        self._ops_user_ids = set(ops_user_ids or allowed_user_ids)
        self._approval_ttl_seconds = approval_ttl_seconds
        self._audit_log_path = audit_log_path.resolve()
        self._logger = logger
        self._user_modes: dict[int, str] = {}
        self._pending_by_user: dict[int, PendingSafetyApproval] = {}

    def get_current_mode(self, user_id: int) -> str:
        """Return the current active safety mode for a user."""

        mode = self._user_modes.get(user_id, self._default_mode)
        max_mode = self.get_max_mode(user_id)
        if _mode_rank(mode) > _mode_rank(max_mode):
            return max_mode
        return mode

    def get_max_mode(self, user_id: int) -> str:
        """Return the highest safety mode a user may activate."""

        if user_id in self._admin_user_ids:
            return "admin"
        if user_id in self._ops_user_ids:
            return "ops"
        if user_id in self._allowed_user_ids:
            return "aman"
        return "aman"

    def get_pending_summary(self, user_id: int) -> str | None:
        """Return a short summary of the user's pending host approval."""

        pending = self._get_pending(user_id)
        if pending is None:
            return None
        return pending.summary

    def has_pending(self, user_id: int) -> bool:
        """Return whether the user still has a pending host approval."""

        return self._get_pending(user_id) is not None

    def reset_user(self, user_id: int) -> None:
        """Clear transient safety state for a user."""

        self._pending_by_user.pop(user_id, None)
        self._user_modes.pop(user_id, None)

    def clear_pending(self, user_id: int) -> None:
        """Drop a pending dangerous action without changing the selected mode."""

        self._pending_by_user.pop(user_id, None)

    def try_handle_control_message(self, user_id: int, text: str) -> SafetyControlResult:
        """Handle mode switches or dangerous-action approval replies."""

        mode_result = self._try_handle_mode_message(user_id, text)
        if mode_result.handled:
            return mode_result

        control_match = _PENDING_CONTROL_RE.match(" ".join(text.strip().split()))
        if control_match is None:
            return SafetyControlResult(handled=False)

        pending = self._get_pending(user_id)
        if pending is None:
            return SafetyControlResult(
                handled=True,
                payload=MessagePayload(
                    text=(
                        f"<b>{self._assistant_name}</b>\n\n"
                        "Tidak ada aksi berbahaya yang sedang menunggu konfirmasi."
                    ),
                    parse_mode="HTML",
                ),
            )

        requested_id = (control_match.group(2) or "").strip()
        if requested_id and requested_id != pending.approval_id:
            return SafetyControlResult(
                handled=True,
                payload=MessagePayload(
                    text=(
                        f"<b>{self._assistant_name}</b>\n\n"
                        "ID approval-nya tidak cocok dengan aksi yang sedang menunggu."
                    ),
                    parse_mode="HTML",
                ),
            )

        action = control_match.group(1).lower()
        self._pending_by_user.pop(user_id, None)
        if action == "batal":
            self.record_audit_event(
                user_id=user_id,
                event="rejected",
                category=pending.category,
                mode=self.get_current_mode(user_id),
                required_mode=pending.required_mode,
                summary=pending.summary,
                preview=pending.preview,
                outcome="rejected",
            )
            return SafetyControlResult(
                handled=True,
                payload=MessagePayload(
                    text=(
                        f"<b>{self._assistant_name}</b>\n\n"
                        "Aksi berbahaya tadi saya batalkan."
                    ),
                    parse_mode="HTML",
                ),
            )

        self.record_audit_event(
            user_id=user_id,
            event="approved",
            category=pending.category,
            mode=self.get_current_mode(user_id),
            required_mode=pending.required_mode,
            summary=pending.summary,
            preview=pending.preview,
            outcome="approved",
        )
        return SafetyControlResult(
            handled=True,
            pending=pending,
            approved=True,
        )

    def evaluate_action(
        self,
        *,
        user_id: int,
        kind: str,
        payload: Any,
        policy: SafetyPolicy,
    ) -> SafetyGateResult:
        """Check mode and confirmation requirements before an action executes."""

        self._clear_if_expired(user_id)
        current_mode = self.get_current_mode(user_id)
        max_mode = self.get_max_mode(user_id)
        if _mode_rank(current_mode) < _mode_rank(policy.required_mode):
            self.record_audit_event(
                user_id=user_id,
                event="blocked",
                category=policy.category,
                mode=current_mode,
                required_mode=policy.required_mode,
                summary=policy.summary,
                preview=policy.preview,
                outcome="blocked",
            )
            return SafetyGateResult(
                allowed=False,
                payload=MessagePayload(
                    text=(
                        f"<b>{self._assistant_name}</b>\n\n"
                        f"Aksi ini butuh mode <code>{policy.required_mode}</code>, "
                        f"sedangkan mode kamu sekarang <code>{current_mode}</code>.\n"
                        f"Mode maksimum untuk akun ini: <code>{max_mode}</code>.\n\n"
                        "Kalau perlu, kirim `mode ops` atau `mode admin` dulu."
                    ),
                    parse_mode="HTML",
                ),
            )

        existing_pending = self._get_pending(user_id)
        if existing_pending is not None:
            return SafetyGateResult(
                allowed=False,
                payload=MessagePayload(
                    text=(
                        f"<b>{self._assistant_name}</b>\n\n"
                        "Masih ada satu aksi berbahaya yang menunggu konfirmasi.\n"
                        f"Pending: {existing_pending.summary}\n"
                        f"Approval ID: <code>{existing_pending.approval_id}</code>\n\n"
                        "Balas <code>lanjutkan aksi</code> atau <code>batal aksi</code> dulu."
                    ),
                    parse_mode="HTML",
                ),
            )

        if not policy.requires_confirmation:
            self.record_audit_event(
                user_id=user_id,
                event="authorized",
                category=policy.category,
                mode=current_mode,
                required_mode=policy.required_mode,
                summary=policy.summary,
                preview=policy.preview,
                outcome="authorized",
            )
            return SafetyGateResult(allowed=True)

        pending = PendingSafetyApproval(
            approval_id=_new_approval_id(),
            user_id=user_id,
            summary=policy.summary,
            preview=policy.preview,
            category=policy.category,
            required_mode=policy.required_mode,
            kind=kind,
            payload=payload,
            created_at=time.time(),
            expires_at=time.time() + self._approval_ttl_seconds,
        )
        self._pending_by_user[user_id] = pending
        self.record_audit_event(
            user_id=user_id,
            event="pending",
            category=policy.category,
            mode=current_mode,
            required_mode=policy.required_mode,
            summary=policy.summary,
            preview=policy.preview,
            outcome="pending",
            approval_id=pending.approval_id,
        )
        return SafetyGateResult(
            allowed=False,
            payload=MessagePayload(
                text=(
                    f"<b>{self._assistant_name}</b>\n\n"
                    "Aksi ini saya tahan dulu karena termasuk operasi yang sensitif.\n\n"
                    f"Ringkasan: {policy.summary}\n"
                    f"Kategori: <code>{policy.category}</code>\n"
                    f"Mode yang dibutuhkan: <code>{policy.required_mode}</code>\n"
                    f"Approval ID: <code>{pending.approval_id}</code>\n"
                    f"Preview: <code>{policy.preview}</code>\n\n"
                    "Balas <code>lanjutkan aksi</code> untuk menjalankan, "
                    "atau <code>batal aksi</code> untuk membatalkan."
                ),
                parse_mode="HTML",
            ),
        )

    def record_audit_event(
        self,
        *,
        user_id: int,
        event: str,
        category: str,
        mode: str,
        required_mode: str,
        summary: str,
        preview: str,
        outcome: str,
        approval_id: str | None = None,
        exit_code: int | None = None,
    ) -> None:
        """Append a structured audit event to the local audit log."""

        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "event": event,
            "category": category,
            "mode": mode,
            "required_mode": required_mode,
            "summary": summary,
            "preview": preview,
            "outcome": outcome,
        }
        if approval_id is not None:
            record["approval_id"] = approval_id
        if exit_code is not None:
            record["exit_code"] = exit_code

        try:
            self._audit_log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._audit_log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=True) + "\n")
        except Exception:
            self._logger.exception("action=audit_log_failed | path=%s", str(self._audit_log_path))

    def get_audit_log_path(self) -> Path:
        """Return the path of the current audit log file."""

        return self._audit_log_path

    def _try_handle_mode_message(self, user_id: int, text: str) -> SafetyControlResult:
        normalized = " ".join(text.strip().split())
        if not normalized:
            return SafetyControlResult(handled=False)

        if _MODE_STATUS_RE.match(normalized):
            current = self.get_current_mode(user_id)
            max_mode = self.get_max_mode(user_id)
            return SafetyControlResult(
                handled=True,
                payload=MessagePayload(
                    text=(
                        f"<b>{self._assistant_name}</b>\n\n"
                        f"Mode keamanan sekarang: <code>{current}</code>\n"
                        f"Mode maksimum akun ini: <code>{max_mode}</code>"
                    ),
                    parse_mode="HTML",
                ),
            )

        mode_match = _MODE_CONTROL_RE.match(normalized)
        if mode_match is None:
            return SafetyControlResult(handled=False)

        requested_mode = _normalize_mode(mode_match.group(1))
        max_mode = self.get_max_mode(user_id)
        if _mode_rank(requested_mode) > _mode_rank(max_mode):
            return SafetyControlResult(
                handled=True,
                payload=MessagePayload(
                    text=(
                        f"<b>{self._assistant_name}</b>\n\n"
                        f"Kamu tidak bisa pindah ke mode <code>{requested_mode}</code>.\n"
                        f"Mode maksimum akun ini: <code>{max_mode}</code>."
                    ),
                    parse_mode="HTML",
                ),
            )

        self._user_modes[user_id] = requested_mode
        self.record_audit_event(
            user_id=user_id,
            event="mode_changed",
            category="safety_mode",
            mode=requested_mode,
            required_mode=requested_mode,
            summary=f"Ganti mode ke {requested_mode}",
            preview=requested_mode,
            outcome="changed",
        )
        return SafetyControlResult(
            handled=True,
            payload=MessagePayload(
                text=(
                    f"<b>{self._assistant_name}</b>\n\n"
                    f"Mode keamanan sekarang saya ubah ke <code>{requested_mode}</code>."
                ),
                parse_mode="HTML",
            ),
        )

    def _get_pending(self, user_id: int) -> PendingSafetyApproval | None:
        self._clear_if_expired(user_id)
        return self._pending_by_user.get(user_id)

    def _clear_if_expired(self, user_id: int) -> None:
        pending = self._pending_by_user.get(user_id)
        if pending is None:
            return
        if pending.expires_at >= time.time():
            return
        self._pending_by_user.pop(user_id, None)


def classify_shell_policy(command: str) -> SafetyPolicy:
    """Classify a direct shell command into a safety category and required mode."""

    raw_command = command.strip()
    lowered = raw_command.lower()
    if not raw_command:
        raise ValueError("Command kosong.")
    for snippet in _SHELL_FORBIDDEN_SNIPPETS:
        if snippet in lowered:
            raise ValueError("Perintah shell ini mengandung pola yang terlalu berisiko.")
    if ";" in raw_command or "\n" in raw_command:
        raise ValueError("Separator command tambahan belum diizinkan lewat shell langsung Codi.")
    if "&" in raw_command.replace("&&", ""):
        raise ValueError("Background command belum diizinkan lewat shell langsung Codi.")
    if any(token in raw_command for token in (">", "<")):
        raise ValueError("Redirect file belum diizinkan lewat shell langsung Codi.")

    categories: list[str] = []
    for segment in re.split(r"\s*(?:&&|\|\||\|)\s*", raw_command):
        parts = shlex.split(segment)
        if not parts:
            continue
        top_level = parts[0]
        category = _SHELL_ALLOWED_TOP_LEVEL.get(top_level)
        if category is None:
            raise ValueError(f"Perintah `{top_level}` belum masuk allowlist shell Codi.")
        categories.append(category)

    if not categories:
        raise ValueError("Perintah shell ini belum bisa dipahami dengan aman.")

    return SafetyPolicy(
        category=categories[0],
        required_mode="admin",
        requires_confirmation=True,
        summary="Menjalankan shell command langsung di host",
        preview=raw_command,
    )


def classify_repo_shortcut_policy(action: str, preview: str) -> SafetyPolicy:
    """Return safety requirements for a repo shortcut action."""

    if action in {"git_status", "git_branch_current", "git_branch_list"}:
        return SafetyPolicy("repo_read", "aman", False, "Aksi repo read-only", preview)
    if action in {"git_fetch", "node_test", "node_lint", "backend_test"}:
        return SafetyPolicy("repo_ops", "ops", False, "Aksi repo operasional", preview)
    if action in {"git_pull", "git_branch_create", "git_branch_switch", "node_build", "node_install", "backend_build", "backend_install"}:
        return SafetyPolicy("repo_mutation", "ops", True, "Aksi repo yang mengubah workspace", preview)
    if action in {"service_start", "service_stop", "service_restart"}:
        return SafetyPolicy("service_control", "ops", True, "Kontrol service host", preview)
    if action in {"node_deploy", "node_publish", "backend_deploy", "backend_publish", "git_push", "git_commit", "git_cherry_pick", "git_branch_delete", "git_branch_merge", "git_branch_rebase", "git_rollback_last_commit", "git_rollback_to_tag", "git_tag_create"}:
        return SafetyPolicy("admin_repo", "admin", True, "Aksi repo berisiko tinggi", preview)
    return SafetyPolicy("repo_ops", "ops", True, "Aksi repo host", preview)


def classify_service_shortcut_policy(action: str, preview: str) -> SafetyPolicy:
    """Return safety requirements for a service shortcut action."""

    if action in {"service_status", "service_logs", "service_health", "service_health_all"}:
        return SafetyPolicy("service_observe", "aman", False, "Observasi service host", preview)
    if action in {"service_start", "service_stop", "service_restart"}:
        return SafetyPolicy("service_control", "ops", True, "Kontrol service host", preview)
    return SafetyPolicy("service_control", "ops", True, "Aksi service host", preview)


def classify_env_config_policy(key: str, preview: str) -> SafetyPolicy:
    """Return safety requirements for an `.env` config update."""

    return SafetyPolicy(
        category="config_update",
        required_mode="ops",
        requires_confirmation=True,
        summary=f"Mengubah konfigurasi lokal {key}",
        preview=preview,
    )


def classify_restart_policy() -> SafetyPolicy:
    """Return safety requirements for restarting Codi itself."""

    return SafetyPolicy(
        category="system_control",
        required_mode="ops",
        requires_confirmation=True,
        summary="Restart proses Codi",
        preview="restart codi",
    )


def _new_approval_id() -> str:
    return uuid.uuid4().hex[:8]


def _normalize_mode(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized not in _MODE_RANK:
        return "ops"
    return normalized


def _mode_rank(mode: str) -> int:
    return _MODE_RANK[_normalize_mode(mode)]
