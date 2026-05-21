"""Device registry, heartbeat tracking, and Telegram-facing device summaries."""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import asdict, dataclass
from html import escape
from pathlib import Path

from models.result import MessagePayload

_DEVICE_LIST_PATTERNS = (
    re.compile(r"^(?:device|devices?)\s+(?:yang\s+)?online(?:\s+apa\s+saja)?$", re.IGNORECASE),
    re.compile(r"^(?:daftar|list)\s+device(?:s)?$", re.IGNORECASE),
    re.compile(r"^status\s+semua\s+device(?:s)?$", re.IGNORECASE),
)
_DEVICE_DETAIL_PATTERN = re.compile(
    r"^(?:detail|status|lihat)\s+device\s+(.+)$",
    re.IGNORECASE,
)


class DeviceRegistryError(RuntimeError):
    """Raised when a device registry operation cannot proceed."""


@dataclass(frozen=True)
class DeviceRegistration:
    """A validated device registration or heartbeat payload."""

    device_id: str
    label: str
    device_type: str
    hostname: str
    platform: str
    capabilities: tuple[str, ...]
    agent_version: str | None = None


@dataclass(frozen=True)
class DeviceQuery:
    """A structured device-related Telegram query."""

    action: str
    device_ref: str | None = None


@dataclass(frozen=True)
class DeviceRecord:
    """The persisted state of a registered device."""

    device_id: str
    label: str
    device_type: str
    hostname: str
    platform: str
    capabilities: tuple[str, ...]
    agent_version: str | None
    first_seen_at: float
    last_seen_at: float
    last_ip: str | None = None


@dataclass(frozen=True)
class DeviceRegistryStats:
    """A compact online/offline summary of registered devices."""

    registered_devices: int
    online_devices: int


class DeviceRegistryManager:
    """Persist device registrations and determine online status from heartbeats."""

    def __init__(
        self,
        *,
        registry_path: Path,
        heartbeat_ttl_seconds: int,
        assistant_name: str,
        logger,
    ) -> None:
        self._registry_path = registry_path.expanduser().resolve()
        self._heartbeat_ttl_seconds = heartbeat_ttl_seconds
        self._assistant_name = assistant_name
        self._logger = logger
        self._lock = threading.RLock()
        self._devices: dict[str, DeviceRecord] = {}
        self._load()

    @staticmethod
    def classify_message(text: str) -> DeviceQuery | None:
        """Classify natural-language Telegram prompts about registered devices."""

        normalized = " ".join(text.strip().split())
        if not normalized:
            return None
        for pattern in _DEVICE_LIST_PATTERNS:
            if pattern.match(normalized):
                return DeviceQuery(action="list")
        detail_match = _DEVICE_DETAIL_PATTERN.match(normalized)
        if detail_match is not None:
            return DeviceQuery(action="detail", device_ref=detail_match.group(1).strip())
        return None

    def register_device(
        self,
        registration: DeviceRegistration,
        *,
        remote_addr: str | None = None,
    ) -> DeviceRecord:
        """Register a device and mark it immediately online."""

        return self._upsert_device(
            registration,
            remote_addr=remote_addr,
            now=time.time(),
        )

    def record_heartbeat(
        self,
        registration: DeviceRegistration,
        *,
        remote_addr: str | None = None,
    ) -> DeviceRecord:
        """Refresh the last-seen time of a previously known device."""

        return self._upsert_device(
            registration,
            remote_addr=remote_addr,
            now=time.time(),
        )

    def get_stats(self) -> DeviceRegistryStats:
        """Return the total and currently online device counts."""

        with self._lock:
            online = sum(1 for record in self._devices.values() if self._is_online(record))
            return DeviceRegistryStats(
                registered_devices=len(self._devices),
                online_devices=online,
            )

    def render_list_payload(self) -> MessagePayload:
        """Render a Telegram payload listing known devices and their status."""

        devices = self.list_records()
        if not devices:
            return MessagePayload(
                text=(
                    f"<b>{escape(self._assistant_name)}</b>\n\n"
                    "Belum ada device yang pernah register ke bot pusat ini."
                ),
                parse_mode="HTML",
            )

        lines = [f"<b>{escape(self._assistant_name)} melihat device ini:</b>", ""]
        for record in devices:
            state = "online" if self._is_online(record) else "offline"
            capabilities = ", ".join(record.capabilities[:5]) if record.capabilities else "-"
            lines.append(
                (
                    f"- <b>{escape(record.label)}</b> "
                    f"(<code>{escape(record.device_id)}</code>)\n"
                    f"  Status: {escape(state)} | Tipe: {escape(record.device_type)}\n"
                    f"  Host: <code>{escape(record.hostname)}</code> | "
                    f"Platform: <code>{escape(record.platform)}</code>\n"
                    f"  Capability: <code>{escape(capabilities)}</code>\n"
                    f"  Last seen: {escape(_humanize_last_seen(record.last_seen_at))}"
                )
            )
        return MessagePayload(text="\n".join(lines), parse_mode="HTML")

    def list_records(self) -> tuple[DeviceRecord, ...]:
        """Return all known devices sorted by online status and label."""

        with self._lock:
            devices = tuple(sorted(
                self._devices.values(),
                key=lambda item: (not self._is_online(item), item.label.lower(), item.device_id),
            ))
        return devices

    def render_detail_payload(self, device_ref: str) -> MessagePayload:
        """Render a Telegram payload with the full detail of one device."""

        record = self._resolve_device(device_ref)
        if record is None:
            return MessagePayload(
                text=(
                    f"<b>{escape(self._assistant_name)}</b>\n\n"
                    f"Saya belum menemukan device yang cocok untuk '{escape(device_ref)}'."
                ),
                parse_mode="HTML",
            )

        capabilities = ", ".join(record.capabilities) if record.capabilities else "-"
        status = "online" if self._is_online(record) else "offline"
        lines = [
            f"<b>Detail device {escape(record.label)}</b>",
            "",
            f"ID: <code>{escape(record.device_id)}</code>",
            f"Status: {escape(status)}",
            f"Tipe: <code>{escape(record.device_type)}</code>",
            f"Hostname: <code>{escape(record.hostname)}</code>",
            f"Platform: <code>{escape(record.platform)}</code>",
            f"Capability: <code>{escape(capabilities)}</code>",
            f"Pertama terlihat: {escape(_format_timestamp(record.first_seen_at))}",
            f"Terakhir heartbeat: {escape(_format_timestamp(record.last_seen_at))}",
        ]
        if record.agent_version:
            lines.append(f"Versi agent: <code>{escape(record.agent_version)}</code>")
        if record.last_ip:
            lines.append(f"IP terakhir: <code>{escape(record.last_ip)}</code>")
        return MessagePayload(text="\n".join(lines), parse_mode="HTML")

    def resolve_device(self, device_ref: str) -> DeviceRecord | None:
        """Return a matching device record by ID or label."""

        return self._resolve_device(device_ref)

    def get_all_device_ids(self) -> list[str]:
        """Return a list of all registered device IDs."""

        with self._lock:
            return list(self._devices.keys())

    def is_online_record(self, record: DeviceRecord) -> bool:
        """Return whether a device record is currently online."""

        return self._is_online(record)

    def _upsert_device(
        self,
        registration: DeviceRegistration,
        *,
        remote_addr: str | None,
        now: float,
    ) -> DeviceRecord:
        with self._lock:
            existing = self._devices.get(registration.device_id)
            first_seen_at = existing.first_seen_at if existing is not None else now
            record = DeviceRecord(
                device_id=registration.device_id,
                label=registration.label,
                device_type=registration.device_type,
                hostname=registration.hostname,
                platform=registration.platform,
                capabilities=registration.capabilities,
                agent_version=registration.agent_version,
                first_seen_at=first_seen_at,
                last_seen_at=now,
                last_ip=remote_addr or (existing.last_ip if existing is not None else None),
            )
            self._devices[record.device_id] = record
            self._save_locked()
            return record

    def _resolve_device(self, device_ref: str) -> DeviceRecord | None:
        normalized_ref = _normalize_key(device_ref)
        with self._lock:
            if device_ref in self._devices:
                return self._devices[device_ref]
            for record in self._devices.values():
                if _normalize_key(record.device_id) == normalized_ref:
                    return record
                if _normalize_key(record.label) == normalized_ref:
                    return record
        return None

    def _is_online(self, record: DeviceRecord) -> bool:
        return (time.time() - record.last_seen_at) <= self._heartbeat_ttl_seconds

    def _load(self) -> None:
        with self._lock:
            if not self._registry_path.exists():
                self._devices = {}
                return
            try:
                payload = json.loads(self._registry_path.read_text(encoding="utf-8"))
            except Exception:
                self._logger.exception(
                    "action=device_registry_load_failed | path=%s",
                    str(self._registry_path),
                )
                self._devices = {}
                return

            raw_devices = payload.get("devices", [])
            devices: dict[str, DeviceRecord] = {}
            for raw in raw_devices:
                try:
                    record = DeviceRecord(
                        device_id=str(raw["device_id"]),
                        label=str(raw["label"]),
                        device_type=str(raw["device_type"]),
                        hostname=str(raw["hostname"]),
                        platform=str(raw["platform"]),
                        capabilities=tuple(str(item) for item in raw.get("capabilities", [])),
                        agent_version=(
                            str(raw["agent_version"])
                            if raw.get("agent_version") is not None
                            else None
                        ),
                        first_seen_at=float(raw["first_seen_at"]),
                        last_seen_at=float(raw["last_seen_at"]),
                        last_ip=(
                            str(raw["last_ip"])
                            if raw.get("last_ip") is not None
                            else None
                        ),
                    )
                except Exception:
                    self._logger.exception(
                        "action=device_registry_record_invalid | path=%s",
                        str(self._registry_path),
                    )
                    continue
                devices[record.device_id] = record
            self._devices = devices

    def _save_locked(self) -> None:
        payload = {
            "version": 1,
            "devices": [asdict(record) for record in sorted(self._devices.values(), key=lambda item: item.device_id)],
        }
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        self._registry_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )


def parse_device_registration(payload: dict[str, object]) -> DeviceRegistration:
    """Validate and normalize a device registration or heartbeat payload."""

    device_id = _require_non_empty_string(payload.get("device_id"), "device_id")
    label = _require_non_empty_string(payload.get("label"), "label")
    device_type = _require_non_empty_string(payload.get("device_type"), "device_type")
    hostname = _require_non_empty_string(payload.get("hostname"), "hostname")
    platform = _require_non_empty_string(payload.get("platform"), "platform")
    capabilities = _parse_capabilities(payload.get("capabilities"))
    agent_version_raw = payload.get("agent_version")
    agent_version = str(agent_version_raw).strip() if agent_version_raw else None
    return DeviceRegistration(
        device_id=_normalize_device_id(device_id),
        label=label,
        device_type=device_type.strip().lower(),
        hostname=hostname,
        platform=platform,
        capabilities=capabilities,
        agent_version=agent_version or None,
    )


def _require_non_empty_string(value: object, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise DeviceRegistryError(f"Field `{field_name}` wajib diisi.")
    return text


def _parse_capabilities(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        parts = [item.strip().lower() for item in value.split(",") if item.strip()]
        return tuple(dict.fromkeys(parts))
    if isinstance(value, list):
        parts = [str(item).strip().lower() for item in value if str(item).strip()]
        return tuple(dict.fromkeys(parts))
    raise DeviceRegistryError("Field `capabilities` harus berupa string CSV atau array.")


def _normalize_device_id(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9._:-]+", "-", value.strip().lower()).strip("-")
    if not normalized:
        raise DeviceRegistryError("device_id tidak valid.")
    return normalized


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.strip().lower())


def _format_timestamp(value: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(value))


def _humanize_last_seen(last_seen_at: float) -> str:
    delta = max(0, int(time.time() - last_seen_at))
    if delta < 10:
        return "baru saja"
    if delta < 60:
        return f"{delta} detik lalu"
    minutes, seconds = divmod(delta, 60)
    if minutes < 60:
        return f"{minutes} menit lalu"
    hours, rem_minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours} jam {rem_minutes} menit lalu"
    days, rem_hours = divmod(hours, 24)
    return f"{days} hari {rem_hours} jam lalu"
