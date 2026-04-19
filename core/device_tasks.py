"""Persistent task queue for explicit central-to-device execution."""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import asdict, dataclass
from html import escape
from pathlib import Path
from uuid import uuid4

from models.result import MessagePayload

TERMINAL_STATES = {"completed", "failed", "expired"}
TASK_TTL_SECONDS = 300

_DEVICE_TARGET_PATTERN = re.compile(
    r"^\s*(?:di|ke|pada)\s+device\s+(?P<device>[a-zA-Z0-9._:-]+)\s*,?\s+(?P<task>.+)$",
    re.IGNORECASE,
)
_TASK_STATUS_PATTERN = re.compile(
    r"^\s*(?:hasil|status)\s+(?:task\s+)?(?P<task_id>dt-[a-f0-9]{8})\s*$",
    re.IGNORECASE,
)
_ACTIVE_DEVICE_PATTERN = re.compile(
    r"^\s*(?:device\s+aktif|device\s+saya|device\s+aktif\s+saya)(?:\s+(?:apa|sekarang))?\s*$",
    re.IGNORECASE,
)
_USE_DEVICE_PATTERN = re.compile(
    r"^\s*(?:pakai|gunakan|set|ganti\s+ke)\s+device\s+(?P<device>[a-zA-Z0-9._:-]+)\s*$",
    re.IGNORECASE,
)
_DEVICE_REPO_PATTERN = re.compile(
    r"^\s*(?:di\s+device\s+(?P<device>[a-zA-Z0-9._:-]+)\s*,?\s+)?(?:pakai|gunakan|set)\s+repo\s+(?P<repo>.+)$",
    re.IGNORECASE,
)
_DEVICE_CONTEXT_STATUS_PATTERN = re.compile(
    r"^\s*(?:konteks|context|repo)\s+device\s+(?P<device>[a-zA-Z0-9._:-]+)(?:\s+(?:apa|sekarang))?\s*$",
    re.IGNORECASE,
)


class DeviceTaskError(RuntimeError):
    """Raised when a task queue operation cannot proceed."""


@dataclass(frozen=True)
class DeviceTask:
    """A task assigned by the central bot to one device agent."""

    task_id: str
    device_id: str
    requested_by: int
    kind: str
    payload: dict[str, object]
    status: str
    created_at: float
    updated_at: float
    claimed_at: float | None = None
    completed_at: float | None = None
    result: dict[str, object] | None = None
    error: str | None = None


@dataclass(frozen=True)
class DeviceTaskRequest:
    """Parsed explicit-device user request."""

    device_ref: str
    task_text: str


@dataclass(frozen=True)
class DeviceContext:
    """Persisted context for one user on one device."""

    user_id: int
    device_id: str
    active_repo: str | None
    updated_at: float


class DeviceContextStore:
    """JSON-backed active device and per-device repo context."""

    def __init__(self, *, context_path: Path, logger) -> None:
        self._context_path = context_path.expanduser().resolve()
        self._logger = logger
        self._lock = threading.RLock()
        self._active_devices: dict[int, str] = {}
        self._contexts: dict[tuple[int, str], DeviceContext] = {}
        self._load()

    def set_active_device(self, user_id: int, device_id: str) -> None:
        with self._lock:
            self._active_devices[user_id] = device_id
            self._contexts.setdefault(
                (user_id, device_id),
                DeviceContext(user_id=user_id, device_id=device_id, active_repo=None, updated_at=time.time()),
            )
            self._save_locked()

    def get_active_device(self, user_id: int) -> str | None:
        with self._lock:
            return self._active_devices.get(user_id)

    def set_active_repo(self, user_id: int, device_id: str, repo_path: str) -> DeviceContext:
        context = DeviceContext(
            user_id=user_id,
            device_id=device_id,
            active_repo=repo_path,
            updated_at=time.time(),
        )
        with self._lock:
            self._active_devices[user_id] = device_id
            self._contexts[(user_id, device_id)] = context
            self._save_locked()
        return context

    def get_context(self, user_id: int, device_id: str) -> DeviceContext:
        with self._lock:
            return self._contexts.get(
                (user_id, device_id),
                DeviceContext(user_id=user_id, device_id=device_id, active_repo=None, updated_at=0.0),
            )

    def _load(self) -> None:
        with self._lock:
            if not self._context_path.exists():
                return
            try:
                payload = json.loads(self._context_path.read_text(encoding="utf-8"))
            except Exception:
                self._logger.exception("action=device_context_load_failed | path=%s", self._context_path)
                return
            self._active_devices = {
                int(user_id): str(device_id)
                for user_id, device_id in dict(payload.get("active_devices", {})).items()
            }
            contexts: dict[tuple[int, str], DeviceContext] = {}
            for raw in payload.get("contexts", []):
                try:
                    context = DeviceContext(
                        user_id=int(raw["user_id"]),
                        device_id=str(raw["device_id"]),
                        active_repo=str(raw["active_repo"]) if raw.get("active_repo") else None,
                        updated_at=float(raw.get("updated_at", 0.0)),
                    )
                except Exception:
                    self._logger.exception("action=device_context_record_invalid | path=%s", self._context_path)
                    continue
                contexts[(context.user_id, context.device_id)] = context
            self._contexts = contexts

    def _save_locked(self) -> None:
        payload = {
            "version": 1,
            "active_devices": {str(user_id): device_id for user_id, device_id in sorted(self._active_devices.items())},
            "contexts": [
                asdict(context)
                for context in sorted(self._contexts.values(), key=lambda item: (item.user_id, item.device_id))
            ],
        }
        self._context_path.parent.mkdir(parents=True, exist_ok=True)
        self._context_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


class DeviceTaskQueue:
    """Small JSON-backed queue used by central bot and polling agents."""

    def __init__(self, *, queue_path: Path, logger) -> None:
        self._queue_path = queue_path.expanduser().resolve()
        self._logger = logger
        self._lock = threading.RLock()
        self._tasks: dict[str, DeviceTask] = {}
        self._load()

    def enqueue(
        self,
        *,
        device_id: str,
        requested_by: int,
        kind: str,
        payload: dict[str, object],
    ) -> DeviceTask:
        now = time.time()
        task = DeviceTask(
            task_id=f"dt-{uuid4().hex[:8]}",
            device_id=device_id,
            requested_by=requested_by,
            kind=kind,
            payload=payload,
            status="queued",
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._tasks[task.task_id] = task
            self._save_locked()
        return task

    def poll(self, *, device_id: str, capabilities: tuple[str, ...]) -> DeviceTask | None:
        now = time.time()
        capability_set = set(capabilities)
        with self._lock:
            self._expire_old_locked(now)
            queued = sorted(
                (
                    task
                    for task in self._tasks.values()
                    if task.device_id == device_id
                    and task.status == "queued"
                    and _required_capability(task.kind) in capability_set
                ),
                key=lambda item: item.created_at,
            )
            if not queued:
                self._save_locked()
                return None
            task = queued[0]
            claimed = _replace_task(
                task,
                status="running",
                claimed_at=now,
                updated_at=now,
            )
            self._tasks[claimed.task_id] = claimed
            self._save_locked()
            return claimed

    def complete(
        self,
        *,
        device_id: str,
        task_id: str,
        ok: bool,
        result: dict[str, object] | None = None,
        error: str | None = None,
    ) -> DeviceTask:
        now = time.time()
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise DeviceTaskError("task_not_found")
            if task.device_id != device_id:
                raise DeviceTaskError("wrong_device")
            completed = _replace_task(
                task,
                status="completed" if ok else "failed",
                result=result or {},
                error=error,
                completed_at=now,
                updated_at=now,
            )
            self._tasks[task_id] = completed
            self._save_locked()
            return completed

    def get(self, task_id: str) -> DeviceTask | None:
        with self._lock:
            self._expire_old_locked(time.time())
            task = self._tasks.get(task_id)
            self._save_locked()
            return task

    def render_task_payload(self, task_id: str, *, assistant_name: str) -> MessagePayload:
        task = self.get(task_id)
        if task is None:
            return MessagePayload(
                text=f"<b>{escape(assistant_name)}</b>\n\nTask <code>{escape(task_id)}</code> tidak ditemukan.",
                parse_mode="HTML",
            )
        lines = [
            f"<b>{escape(assistant_name)} melihat task device.</b>",
            "",
            f"Task: <code>{escape(task.task_id)}</code>",
            f"Device: <code>{escape(task.device_id)}</code>",
            f"Status: <b>{escape(task.status)}</b>",
            f"Jenis: <code>{escape(task.kind)}</code>",
        ]
        if task.error:
            lines.extend(["", f"Error: <code>{escape(task.error)}</code>"])
        if task.result:
            output = str(task.result.get("output") or "").strip()
            if output:
                lines.extend(["", escape(output[:3500])])
        is_terminal = task.status in TERMINAL_STATES
        if not is_terminal:
            lines.append("")
            lines.append(f"Cek lagi dengan <code>hasil task {escape(task.task_id)}</code>.")
        refresh_button: tuple[tuple[str, str], ...] | None = None
        if not is_terminal:
            refresh_button = (("🔄 Refresh Hasil", f"device:task:{task.task_id}"),)
        return MessagePayload(
            text="\n".join(lines),
            parse_mode="HTML",
            inline_buttons=refresh_button,
        )

    def _expire_old_locked(self, now: float) -> None:
        for task in tuple(self._tasks.values()):
            if task.status in {"queued", "running"} and now - task.created_at > TASK_TTL_SECONDS:
                self._tasks[task.task_id] = _replace_task(
                    task,
                    status="expired",
                    error="Task expired sebelum agent mengirim hasil.",
                    updated_at=now,
                )

    def _load(self) -> None:
        with self._lock:
            if not self._queue_path.exists():
                self._tasks = {}
                return
            try:
                payload = json.loads(self._queue_path.read_text(encoding="utf-8"))
            except Exception:
                self._logger.exception("action=device_task_queue_load_failed | path=%s", self._queue_path)
                self._tasks = {}
                return
            tasks: dict[str, DeviceTask] = {}
            for raw in payload.get("tasks", []):
                try:
                    task = DeviceTask(
                        task_id=str(raw["task_id"]),
                        device_id=str(raw["device_id"]),
                        requested_by=int(raw["requested_by"]),
                        kind=str(raw["kind"]),
                        payload=dict(raw.get("payload", {})),
                        status=str(raw["status"]),
                        created_at=float(raw["created_at"]),
                        updated_at=float(raw["updated_at"]),
                        claimed_at=_optional_float(raw.get("claimed_at")),
                        completed_at=_optional_float(raw.get("completed_at")),
                        result=dict(raw["result"]) if raw.get("result") is not None else None,
                        error=str(raw["error"]) if raw.get("error") is not None else None,
                    )
                except Exception:
                    self._logger.exception("action=device_task_record_invalid | path=%s", self._queue_path)
                    continue
                tasks[task.task_id] = task
            self._tasks = tasks

    def _save_locked(self) -> None:
        payload = {
            "version": 1,
            "tasks": [
                asdict(task)
                for task in sorted(self._tasks.values(), key=lambda item: item.created_at)
            ],
        }
        self._queue_path.parent.mkdir(parents=True, exist_ok=True)
        self._queue_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def parse_explicit_device_request(text: str) -> DeviceTaskRequest | None:
    """Parse prompts like `di device absen-server, status host`."""

    match = _DEVICE_TARGET_PATTERN.match(text.strip())
    if match is None:
        return None
    return DeviceTaskRequest(
        device_ref=match.group("device").strip(),
        task_text=match.group("task").strip(),
    )


def parse_task_status_request(text: str) -> str | None:
    """Parse prompts like `hasil task dt-1234abcd`."""

    match = _TASK_STATUS_PATTERN.match(text.strip())
    if match is None:
        return None
    return match.group("task_id").lower()


def is_active_device_query(text: str) -> bool:
    """Return whether a prompt asks for the active device."""

    return bool(_ACTIVE_DEVICE_PATTERN.match(text.strip()))


def parse_use_device_request(text: str) -> str | None:
    """Parse prompts like `pakai device absen-server`."""

    match = _USE_DEVICE_PATTERN.match(text.strip())
    if match is None:
        return None
    return match.group("device").strip()


def parse_device_repo_request(text: str) -> tuple[str | None, str] | None:
    """Parse prompts like `di device x, pakai repo /srv/app` or `pakai repo /srv/app`."""

    match = _DEVICE_REPO_PATTERN.match(text.strip())
    if match is None:
        return None
    return match.group("device"), match.group("repo").strip()


def parse_device_context_status_request(text: str) -> str | None:
    """Parse prompts like `konteks device absen-server`."""

    match = _DEVICE_CONTEXT_STATUS_PATTERN.match(text.strip())
    if match is None:
        return None
    return match.group("device").strip()


def classify_device_task(
    task_text: str,
    *,
    active_repo: str | None = None,
) -> tuple[str, dict[str, object]] | None:
    """Classify a small safe task for a remote agent."""

    normalized = " ".join(task_text.strip().lower().split())
    if normalized in {"status host", "cek status host", "host status", "status server"}:
        return "host_status", {}
    if (
        ("telat" in normalized or "terlambat" in normalized or "late" in normalized)
        and "bulan ini" in normalized
        and ("karyawan" in normalized or "pegawai" in normalized or "employee" in normalized)
    ):
        payload = {}
        if active_repo:
            payload["cwd"] = active_repo
        return "late_this_month", payload
    if "schema" in normalized and ("database" in normalized or "db" in normalized):
        payload: dict[str, object] = {}
        if active_repo:
            payload["cwd"] = active_repo
        return "sqlite_schema", payload
    sql = _extract_sql(task_text)
    if sql is not None:
        payload = {"sql": sql}
        if active_repo:
            payload["cwd"] = active_repo
        return "sqlite_query", payload
    return None


def _extract_sql(text: str) -> str | None:
    stripped = text.strip()
    lowered = stripped.lower()
    for prefix in ("sql:", "query:"):
        if lowered.startswith(prefix):
            return stripped[len(prefix):].strip()
    if re.match(r"^\s*(?:select|with)\b", stripped, re.IGNORECASE | re.DOTALL):
        return stripped
    return None


def _required_capability(kind: str) -> str:
    if kind in {"host_status", "self_update", "natural_query"}:
        return "system_activity"
    if kind in {"sqlite_schema", "sqlite_query", "late_this_month"}:
        return "business_readonly"
    return kind


def _replace_task(task: DeviceTask, **updates) -> DeviceTask:
    values = asdict(task)
    values.update(updates)
    return DeviceTask(**values)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
