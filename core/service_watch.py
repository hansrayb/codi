"""Background monitoring for important systemd units and PM2 apps."""

from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape

from config import Settings
from core.alert_targets import AlertTargetRegistry
from models.result import MessagePayload


@dataclass(frozen=True)
class ServiceWatchAlert:
    """An outbound Telegram alert produced by the service-watch loop."""

    user_id: int
    chat_id: int
    payload: MessagePayload


@dataclass(frozen=True)
class MonitorSnapshot:
    """A compact point-in-time state for a monitored runtime target."""

    kind: str
    name: str
    scope: str
    healthy: bool
    status: str
    detail: str
    observed_at: datetime

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.name}"

    @property
    def fingerprint(self) -> str:
        return "|".join((self.scope, self.status, self.detail))


@dataclass(frozen=True)
class ServiceWatchStats:
    """Lightweight health summary for the status screen."""

    monitored_services: int
    unhealthy_services: int
    monitored_pm2_apps: int
    unhealthy_pm2_apps: int


class ServiceWatchManager:
    """Monitor configured systemd units and PM2 apps and emit alerts on changes."""

    def __init__(
        self,
        settings: Settings,
        *,
        alert_targets: AlertTargetRegistry,
        systemd_reader=None,
        pm2_reader=None,
    ) -> None:
        self._settings = settings
        self._alert_targets = alert_targets
        self._systemd_reader = systemd_reader or _read_systemd_unit
        self._pm2_reader = pm2_reader or _read_pm2_apps
        self._previous: dict[str, MonitorSnapshot] = {}
        self._latest: dict[str, MonitorSnapshot] = {}
        self._lock = asyncio.Lock()

    async def scan_once(self, *, assistant_name: str) -> tuple[ServiceWatchAlert, ...]:
        """Poll configured units once and return outbound alert payloads."""

        targets = await self._alert_targets.list_targets()
        snapshots = await asyncio.to_thread(self._collect_snapshots)
        async with self._lock:
            previous = dict(self._previous)
            self._previous = {snapshot.key: snapshot for snapshot in snapshots}
            self._latest = dict(self._previous)

        if not targets:
            return ()

        changed: list[MonitorSnapshot] = []
        for snapshot in snapshots:
            prior = previous.get(snapshot.key)
            if prior is None:
                if not snapshot.healthy:
                    changed.append(snapshot)
                continue
            if prior.fingerprint != snapshot.fingerprint:
                changed.append(snapshot)

        alerts: list[ServiceWatchAlert] = []
        for snapshot in changed:
            prior = previous.get(snapshot.key)
            payload = _build_service_watch_alert(
                assistant_name=assistant_name,
                current=snapshot,
                previous=prior,
            )
            if payload is None:
                continue
            for target in targets:
                alerts.append(
                    ServiceWatchAlert(
                        user_id=target.user_id,
                        chat_id=target.chat_id,
                        payload=payload,
                    )
                )
        return tuple(alerts)

    async def get_stats(self) -> ServiceWatchStats:
        """Return the latest monitor-health summary."""

        async with self._lock:
            snapshots = tuple(self._latest.values())
        return ServiceWatchStats(
            monitored_services=sum(1 for item in snapshots if item.kind == 'systemd'),
            unhealthy_services=sum(
                1 for item in snapshots if item.kind == 'systemd' and not item.healthy
            ),
            monitored_pm2_apps=sum(1 for item in snapshots if item.kind == 'pm2'),
            unhealthy_pm2_apps=sum(
                1 for item in snapshots if item.kind == 'pm2' and not item.healthy
            ),
        )

    def _collect_snapshots(self) -> tuple[MonitorSnapshot, ...]:
        snapshots: list[MonitorSnapshot] = []
        for unit_name in self._settings.important_services:
            snapshots.append(self._systemd_reader(unit_name))

        pm2_snapshots_by_name = {
            snapshot.name: snapshot
            for snapshot in self._pm2_reader(self._settings.important_pm2_apps)
        }
        for app_name in self._settings.important_pm2_apps:
            snapshots.append(
                pm2_snapshots_by_name.get(
                    app_name,
                    MonitorSnapshot(
                        kind='pm2',
                        name=app_name,
                        scope='pm2',
                        healthy=False,
                        status='missing',
                        detail='App tidak ditemukan di PM2.',
                        observed_at=_utcnow(),
                    ),
                )
            )

        return tuple(snapshots)


def _build_service_watch_alert(
    *,
    assistant_name: str,
    current: MonitorSnapshot,
    previous: MonitorSnapshot | None,
) -> MessagePayload | None:
    label = 'service' if current.kind == 'systemd' else 'PM2'
    header = (
        f"<b>{escape(assistant_name)} mendeteksi {label} down.</b>"
        if not current.healthy
        else f"<b>{escape(assistant_name)} mendeteksi {label} pulih.</b>"
    )
    lines = [
        header,
        '',
        f"Target: <code>{escape(current.name)}</code>",
        f"Sumber: <code>{escape(current.scope)}</code>",
        f"Status: <code>{escape(current.status)}</code>",
        f"Detail: {escape(current.detail)}",
    ]
    if previous is not None and previous.status != current.status:
        lines.append(f"Sebelumnya: <code>{escape(previous.status)}</code>")
    return MessagePayload(text='\n'.join(lines), parse_mode='HTML')


def _read_systemd_unit(unit_name: str) -> MonitorSnapshot:
    attempts = (
        ('user', ['systemctl', '--user', 'show', unit_name, '--property=LoadState,ActiveState,SubState,Result,ExecMainStatus']),
        ('system', ['systemctl', 'show', unit_name, '--property=LoadState,ActiveState,SubState,Result,ExecMainStatus']),
    )
    stderr_messages: list[str] = []
    for scope, command in attempts:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        stdout = result.stdout.strip()
        if result.returncode == 0 and stdout:
            fields = _parse_systemctl_show(stdout)
            load_state = fields.get('LoadState', 'unknown')
            active_state = fields.get('ActiveState', 'unknown')
            sub_state = fields.get('SubState', 'unknown')
            result_state = fields.get('Result', 'unknown')
            exec_main_status = fields.get('ExecMainStatus', 'unknown')
            healthy = active_state == 'active'
            detail = (
                f"load={load_state}, sub={sub_state}, result={result_state}, "
                f"exit={exec_main_status}"
            )
            return MonitorSnapshot(
                kind='systemd',
                name=unit_name,
                scope=scope,
                healthy=healthy,
                status=f"{active_state}/{sub_state}",
                detail=detail,
                observed_at=_utcnow(),
            )
        stderr = (result.stderr or stdout or '').strip()
        if stderr:
            stderr_messages.append(f"{scope}: {stderr}")

    return MonitorSnapshot(
        kind='systemd',
        name=unit_name,
        scope='unknown',
        healthy=False,
        status='unavailable',
        detail='; '.join(stderr_messages) or 'systemctl tidak mengembalikan status.',
        observed_at=_utcnow(),
    )


def _read_pm2_apps(app_names: tuple[str, ...]) -> tuple[MonitorSnapshot, ...]:
    if not app_names:
        return ()
    result = subprocess.run(
        ['pm2', 'jlist'],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or '').strip() or 'pm2 jlist gagal.'
        return tuple(
            MonitorSnapshot(
                kind='pm2',
                name=app_name,
                scope='pm2',
                healthy=False,
                status='unavailable',
                detail=detail,
                observed_at=_utcnow(),
            )
            for app_name in app_names
        )

    try:
        payload = json.loads(result.stdout or '[]')
    except json.JSONDecodeError:
        detail = 'Output PM2 tidak bisa dibaca.'
        return tuple(
            MonitorSnapshot(
                kind='pm2',
                name=app_name,
                scope='pm2',
                healthy=False,
                status='invalid-json',
                detail=detail,
                observed_at=_utcnow(),
            )
            for app_name in app_names
        )

    snapshots: list[MonitorSnapshot] = []
    by_name = {str(item.get('name') or ''): item for item in payload if item.get('name')}
    for app_name in app_names:
        item = by_name.get(app_name)
        if item is None:
            continue
        env = item.get('pm2_env') or {}
        status = str(env.get('status') or 'unknown')
        restarts = env.get('restart_time', 0)
        exit_code = env.get('exit_code', 0)
        healthy = status == 'online'
        detail = f"restart={restarts}, exit_code={exit_code}"
        snapshots.append(
            MonitorSnapshot(
                kind='pm2',
                name=app_name,
                scope='pm2',
                healthy=healthy,
                status=status,
                detail=detail,
                observed_at=_utcnow(),
            )
        )
    return tuple(snapshots)


def _parse_systemctl_show(stdout: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in stdout.splitlines():
        if '=' not in line:
            continue
        key, _, value = line.partition('=')
        fields[key.strip()] = value.strip()
    return fields


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
