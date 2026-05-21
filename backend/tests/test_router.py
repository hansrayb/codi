"""Router tests for prompt classification and session reuse hints."""

from __future__ import annotations

import unittest

from core.router import IntentRouter
from models.session import Session


class IntentRouterTests(unittest.TestCase):
    """Validate rule-based routing behavior."""

    def setUp(self) -> None:
        self.router = IntentRouter(default_role="general")

    def test_explicit_override_wins(self) -> None:
        decision = self.router.route("pakai reviewer untuk cek auth middleware")
        self.assertEqual(decision.role, "reviewer")
        self.assertTrue(decision.override_applied)

    def test_keyword_routing_prefers_builder(self) -> None:
        decision = self.router.route("buat endpoint login FastAPI dengan test")
        self.assertEqual(decision.role, "builder")
        self.assertGreaterEqual(decision.confidence, 0.5)

    def test_repo_check_routes_to_reviewer(self) -> None:
        decision = self.router.route("cek repo aplikasi-customerchant")
        self.assertEqual(decision.role, "reviewer")
        self.assertGreaterEqual(decision.confidence, 0.5)

    def test_running_apps_query_routes_to_ops(self) -> None:
        decision = self.router.route("Codi laptop ku sedang menjalankan aplikasi apa")
        self.assertEqual(decision.role, "ops")
        self.assertGreaterEqual(decision.confidence, 0.5)

    def test_commit_message_task_routes_to_builder(self) -> None:
        decision = self.router.route("tolong buat commit message untuk perubahan repo ini")
        self.assertEqual(decision.role, "builder")
        self.assertGreaterEqual(decision.confidence, 0.5)

    def test_pr_review_routes_to_reviewer(self) -> None:
        decision = self.router.route("review PR ini dan cek diff yang berubah")
        self.assertEqual(decision.role, "reviewer")
        self.assertGreaterEqual(decision.confidence, 0.5)

    def test_continuation_reuses_active_role(self) -> None:
        active_session = Session(
            session_id="s-01",
            owner_user_id=1,
            role="debugger",
            cwd="/tmp",
            summary="- debug service systemd",
        )
        decision = self.router.route("lanjutkan yang tadi dan cek traceback", active_session)
        self.assertEqual(decision.role, "debugger")
        self.assertTrue(decision.continuation_hint)

    def test_should_reuse_with_topic_overlap(self) -> None:
        active_session = Session(
            session_id="s-02",
            owner_user_id=1,
            role="reviewer",
            cwd="/tmp",
            summary="- review auth middleware password hashing",
        )
        decision = self.router.route("review password hashing middleware auth flow")
        self.assertTrue(self.router.should_reuse("review password hashing middleware auth flow", decision, active_session))


if __name__ == "__main__":
    unittest.main()
