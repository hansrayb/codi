"""Tests for host safety modes, approvals, and shell allowlists."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.safety import (
    SafetyManager,
    classify_restart_policy,
    classify_shell_policy,
)


class SafetyManagerTests(unittest.TestCase):
    """Verify mode handling, approvals, and audit logging."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.audit_log_path = Path(self.tempdir.name) / "codi-audit.log"
        logger = SimpleNamespace(exception=lambda *args, **kwargs: None)
        self.manager = SafetyManager(
            assistant_name="Codi",
            allowed_user_ids=(1, 2, 3),
            default_mode="ops",
            admin_user_ids=(1,),
            ops_user_ids=(1, 2),
            approval_ttl_seconds=180,
            audit_log_path=self.audit_log_path,
            logger=logger,
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_current_mode_is_clamped_by_user_max_mode(self) -> None:
        self.assertEqual(self.manager.get_current_mode(3), "aman")
        result = self.manager.try_handle_control_message(3, "mode admin")

        self.assertTrue(result.handled)
        self.assertIn("tidak bisa pindah", result.payload.text.lower())
        self.assertEqual(self.manager.get_current_mode(3), "aman")

    def test_mode_switch_to_ops_is_allowed_for_ops_user(self) -> None:
        result = self.manager.try_handle_control_message(2, "mode ops")

        self.assertTrue(result.handled)
        self.assertIn("mode keamanan sekarang saya ubah", result.payload.text.lower())
        self.assertEqual(self.manager.get_current_mode(2), "ops")

    def test_sensitive_action_requires_pending_then_can_be_approved(self) -> None:
        policy = classify_restart_policy()
        gate = self.manager.evaluate_action(
            user_id=1,
            kind="restart_self",
            payload=None,
            policy=policy,
        )

        self.assertFalse(gate.allowed)
        self.assertIsNotNone(gate.payload)
        self.assertTrue(self.manager.has_pending(1))

        approve = self.manager.try_handle_control_message(1, "lanjutkan aksi")

        self.assertTrue(approve.handled)
        self.assertTrue(approve.approved)
        self.assertIsNotNone(approve.pending)
        self.assertFalse(self.manager.has_pending(1))

        records = self._read_audit_records()
        self.assertEqual(records[0]["event"], "pending")
        self.assertEqual(records[1]["event"], "approved")

    def test_second_sensitive_action_is_blocked_while_pending_exists(self) -> None:
        policy = classify_restart_policy()
        first_gate = self.manager.evaluate_action(
            user_id=1,
            kind="restart_self",
            payload=None,
            policy=policy,
        )
        second_gate = self.manager.evaluate_action(
            user_id=1,
            kind="restart_self",
            payload=None,
            policy=policy,
        )

        self.assertFalse(first_gate.allowed)
        self.assertFalse(second_gate.allowed)
        self.assertIn("menunggu konfirmasi", second_gate.payload.text.lower())

    def test_cancel_pending_action_clears_it(self) -> None:
        policy = classify_restart_policy()
        self.manager.evaluate_action(
            user_id=1,
            kind="restart_self",
            payload=None,
            policy=policy,
        )

        cancel = self.manager.try_handle_control_message(1, "batal aksi")

        self.assertTrue(cancel.handled)
        self.assertIn("batalkan", cancel.payload.text.lower())
        self.assertFalse(self.manager.has_pending(1))

    def test_shell_policy_allows_unknown_command_with_admin_approval(self) -> None:
        policy = classify_shell_policy("whoami")

        self.assertEqual(policy.required_mode, "admin")
        self.assertTrue(policy.requires_confirmation)
        self.assertEqual(policy.category, "host_shell")

    def test_shell_policy_allows_redirects_and_separators(self) -> None:
        policy = classify_shell_policy("git status; whoami > /tmp/codi-test.txt")

        self.assertEqual(policy.required_mode, "admin")
        self.assertTrue(policy.requires_confirmation)
        self.assertEqual(policy.category, "repo")

    def test_shell_policy_still_blocks_known_high_risk_snippets(self) -> None:
        with self.assertRaisesRegex(ValueError, "terlalu berisiko"):
            classify_shell_policy("shutdown now")

    def test_shell_policy_marks_direct_host_shell_as_admin(self) -> None:
        policy = classify_shell_policy("git status --short")

        self.assertEqual(policy.required_mode, "admin")
        self.assertTrue(policy.requires_confirmation)
        self.assertEqual(policy.category, "repo")

    def _read_audit_records(self) -> list[dict[str, object]]:
        content = self.audit_log_path.read_text(encoding="utf-8")
        return [json.loads(line) for line in content.splitlines() if line.strip()]


if __name__ == "__main__":
    unittest.main()
