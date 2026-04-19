"""Tests for systemd and PM2 background monitoring."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from config import Settings
from core.alert_targets import AlertTargetRegistry
from core.service_watch import MonitorSnapshot, ServiceWatchManager


def _snapshot(kind: str, name: str, *, healthy: bool, status: str, detail: str, scope: str) -> MonitorSnapshot:
    from datetime import datetime, timezone

    return MonitorSnapshot(
        kind=kind,
        name=name,
        scope=scope,
        healthy=healthy,
        status=status,
        detail=detail,
        observed_at=datetime.now(timezone.utc),
    )


class ServiceWatchManagerTests(unittest.IsolatedAsyncioTestCase):
    """Validate alert emission for monitored services and PM2 apps."""

    async def asyncSetUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        workspace = Path(self.tempdir.name).resolve()
        self.settings = Settings(
            assistant_name='Codi',
            enable_desktop_actions=True,
            enable_local_shell=True,
            telegram_bot_token='token',
            allowed_user_ids=(1,),
            admin_user_ids=(),
            viewer_user_ids=(),
            business_user_ids=(),
            business_allowed_dirs=(),
            business_database_paths=(),
            business_database_urls=(),
            ai_backend='codex',
            codex_bin='codex',
            codex_timeout=180,
            codex_reasoning_effort='medium',
            codex_write_sandbox_mode='workspace-write',
            codex_work_dir=workspace,
            claude_bin='claude',
            claude_model='claude-sonnet-4-6',
            allowed_work_dirs=(workspace,),
            default_role='general',
            max_active_sessions=4,
            max_sessions_per_user=3,
            session_idle_ttl_minutes=60,
            max_queue_per_session=1,
            max_output_length=3000,
            local_shell_timeout=120,
            log_level='INFO',
            log_file=None,
            max_requests_per_minute=5,
            repo_watch_poll_seconds=30,
            service_watch_poll_seconds=30,
            max_watched_repos_per_user=5,
            important_services=('codi.service',),
            important_pm2_apps=('api',),
            alert_targets_path=workspace / 'codi-alert-targets.json',
            enable_device_registry=False,
            device_registry_path=workspace / 'codi-devices.json',
            device_api_host='127.0.0.1',
            device_api_port=8787,
            device_api_shared_token=None,
            device_heartbeat_ttl_seconds=90,
        )
        self.alert_targets = AlertTargetRegistry(self.settings.alert_targets_path)
        await self.alert_targets.register_chat(user_id=1, chat_id=99)
        self.systemd_state = _snapshot(
            'systemd', 'codi.service', healthy=True, status='active/running', detail='ok', scope='user'
        )
        self.pm2_state = _snapshot(
            'pm2', 'api', healthy=True, status='online', detail='restart=0, exit_code=0', scope='pm2'
        )
        self.manager = ServiceWatchManager(
            self.settings,
            alert_targets=self.alert_targets,
            systemd_reader=lambda name: self.systemd_state,
            pm2_reader=lambda names: (self.pm2_state,),
        )

    async def asyncTearDown(self) -> None:
        self.tempdir.cleanup()

    async def test_healthy_first_scan_emits_no_alert(self) -> None:
        alerts = await self.manager.scan_once(assistant_name='Codi')
        self.assertEqual(alerts, ())

    async def test_down_transition_emits_alert(self) -> None:
        await self.manager.scan_once(assistant_name='Codi')
        self.systemd_state = _snapshot(
            'systemd', 'codi.service', healthy=False, status='failed/failed', detail='exit=1', scope='user'
        )

        alerts = await self.manager.scan_once(assistant_name='Codi')

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].chat_id, 99)
        self.assertIn('mendeteksi service down', alerts[0].payload.text)
        self.assertIn('codi.service', alerts[0].payload.text)

    async def test_recovery_transition_emits_alert(self) -> None:
        self.systemd_state = _snapshot(
            'systemd', 'codi.service', healthy=False, status='failed/failed', detail='exit=1', scope='user'
        )
        await self.manager.scan_once(assistant_name='Codi')
        self.systemd_state = _snapshot(
            'systemd', 'codi.service', healthy=True, status='active/running', detail='ok', scope='user'
        )

        alerts = await self.manager.scan_once(assistant_name='Codi')

        self.assertEqual(len(alerts), 1)
        self.assertIn('mendeteksi service pulih', alerts[0].payload.text)

    async def test_stats_reflect_latest_scan(self) -> None:
        self.pm2_state = _snapshot(
            'pm2', 'api', healthy=False, status='errored', detail='restart=3, exit_code=1', scope='pm2'
        )
        await self.manager.scan_once(assistant_name='Codi')

        stats = await self.manager.get_stats()

        self.assertEqual(stats.monitored_services, 1)
        self.assertEqual(stats.monitored_pm2_apps, 1)
        self.assertEqual(stats.unhealthy_services, 0)
        self.assertEqual(stats.unhealthy_pm2_apps, 1)


if __name__ == '__main__':
    unittest.main()
