"""Test auth + RBAC + CRUD accounts (Fase B)."""

from __future__ import annotations

import tempfile
import time
import unittest
from http import HTTPStatus
from pathlib import Path

from core.auth import AuthDb, AuthService, JwtHelper
from core.auth.models import AuthContext
from core.auth.service import AuthServiceError
from core.mobile_api import mobile_handle


JWT_SECRET = "test-secret-do-not-use-in-production"


def _make_service(tmp_dir: Path) -> AuthService:
    db = AuthDb.connect(tmp_dir / "auth.db")
    db.seed_default_roles()
    jwt = JwtHelper(secret=JWT_SECRET, access_ttl_minutes=60, refresh_ttl_days=7)
    return AuthService(db, jwt)


def _seed_superadmin(service: AuthService) -> str:
    """Return superadmin id."""
    acc = service.create_account(
        email="hans@emasberlian.com",
        password="Sup3rPa55!",
        name="Hans",
        title="Super Admin",
        role_slug="superadmin",
    )
    return acc.id


class AuthServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.service = _make_service(self.tmp_path)
        self.super_id = _seed_superadmin(self.service)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # ── Login ─────────────────────────────────────────────
    def test_login_email_ok(self) -> None:
        result = self.service.login_email("hans@emasberlian.com", "Sup3rPa55!")
        self.assertEqual(result.account.email, "hans@emasberlian.com")
        self.assertTrue(result.access_token)
        self.assertTrue(result.refresh_token)
        self.assertIn("accounts:read", result.scopes)
        self.assertIn("dashboard:read", result.scopes)

    def test_login_email_case_insensitive(self) -> None:
        result = self.service.login_email("HANS@emasberlian.com", "Sup3rPa55!")
        self.assertEqual(result.account.email, "hans@emasberlian.com")

    def test_login_wrong_password(self) -> None:
        with self.assertRaises(AuthServiceError) as ctx:
            self.service.login_email("hans@emasberlian.com", "wrong")
        self.assertEqual(ctx.exception.code, "invalid_credentials")
        self.assertEqual(ctx.exception.http_status, 401)

    def test_login_unknown_email(self) -> None:
        with self.assertRaises(AuthServiceError):
            self.service.login_email("ghost@x.com", "anything")

    def test_rate_limit_after_5_failures(self) -> None:
        for _ in range(5):
            with self.assertRaises(AuthServiceError):
                self.service.login_email("hans@emasberlian.com", "wrong")
        with self.assertRaises(AuthServiceError) as ctx:
            self.service.login_email("hans@emasberlian.com", "wrong")
        self.assertEqual(ctx.exception.code, "too_many_attempts")
        self.assertEqual(ctx.exception.http_status, 429)

    # ── JWT verify ───────────────────────────────────────
    def test_access_token_verify_returns_context(self) -> None:
        result = self.service.login_email("hans@emasberlian.com", "Sup3rPa55!")
        ctx = self.service.verify_access_token(result.access_token)
        self.assertEqual(ctx.account_id, self.super_id)
        self.assertEqual(ctx.role_slug, "superadmin")
        self.assertFalse(ctx.is_bootstrap)
        self.assertIn("accounts:delete", ctx.scopes)

    def test_verify_rejects_invalid_token(self) -> None:
        with self.assertRaises(AuthServiceError):
            self.service.verify_access_token("not-a-jwt")

    def test_verify_rejects_suspended_account(self) -> None:
        result = self.service.login_email("hans@emasberlian.com", "Sup3rPa55!")
        # superadmin tak bisa di-suspend lewat update_account_status (guard).
        # buat akun viewer lalu suspend.
        viewer = self.service.create_account(
            email="viewer@x.com",
            password="Viewer123!",
            name="Vee",
            title="",
            role_slug="viewer",
        )
        login = self.service.login_email("viewer@x.com", "Viewer123!")
        self.service.update_account_status(viewer.id, "suspended", actor_id=self.super_id)
        with self.assertRaises(AuthServiceError):
            self.service.verify_access_token(login.access_token)

    def test_refresh_rotates_tokens(self) -> None:
        login = self.service.login_email("hans@emasberlian.com", "Sup3rPa55!")
        refreshed = self.service.refresh(login.refresh_token)
        self.assertTrue(refreshed.access_token)

    # ── Biometric enroll + login ─────────────────────────
    def test_enroll_and_login_biometric(self) -> None:
        login = self.service.login_email("hans@emasberlian.com", "Sup3rPa55!")
        binding = self.service.enroll_device(
            account_id=login.account.id,
            device_id="pixel-9-hans",
            fingerprint="sha256:abc123",
            platform="android",
        )
        self.assertTrue(binding.id.startswith("dvc_"))

        biometric = self.service.login_biometric(
            device_id="pixel-9-hans", fingerprint="sha256:abc123"
        )
        self.assertEqual(biometric.account.id, login.account.id)

    def test_biometric_rejects_unknown_device(self) -> None:
        with self.assertRaises(AuthServiceError) as ctx:
            self.service.login_biometric(device_id="ghost", fingerprint="x")
        self.assertEqual(ctx.exception.code, "device_not_enrolled")

    def test_biometric_rejects_wrong_fingerprint(self) -> None:
        login = self.service.login_email("hans@emasberlian.com", "Sup3rPa55!")
        self.service.enroll_device(
            account_id=login.account.id,
            device_id="pixel-9",
            fingerprint="sha256:correct",
            platform="android",
        )
        with self.assertRaises(AuthServiceError):
            self.service.login_biometric(device_id="pixel-9", fingerprint="sha256:wrong")

    def test_revoked_device_rejected(self) -> None:
        login = self.service.login_email("hans@emasberlian.com", "Sup3rPa55!")
        binding = self.service.enroll_device(
            account_id=login.account.id,
            device_id="dev-1",
            fingerprint="fp1",
            platform="ios",
        )
        self.service.revoke_device(binding.id)
        with self.assertRaises(AuthServiceError):
            self.service.login_biometric(device_id="dev-1", fingerprint="fp1")

    # ── CRUD accounts ────────────────────────────────────
    def test_create_account_director(self) -> None:
        acc = self.service.create_account(
            email="leo@lumbungemas.co.id",
            password="LeoStrong1!",
            name="Leo",
            title="Direktur Utama",
            role_slug="director",
        )
        self.assertEqual(acc.role_slug, "director")
        self.assertEqual(acc.status, "active")

    def test_create_duplicate_email_rejected(self) -> None:
        self.service.create_account(
            email="dup@x.com",
            password="Strong123!",
            name="Dup",
            title="",
            role_slug="viewer",
        )
        with self.assertRaises(AuthServiceError) as ctx:
            self.service.create_account(
                email="dup@x.com",
                password="Strong123!",
                name="Dup2",
                title="",
                role_slug="viewer",
            )
        self.assertEqual(ctx.exception.code, "email_exists")

    def test_create_invalid_role_rejected(self) -> None:
        with self.assertRaises(AuthServiceError):
            self.service.create_account(
                email="x@x.com",
                password="Strong123!",
                name="X",
                title="",
                role_slug="cosmonaut",
            )

    def test_update_role(self) -> None:
        acc = self.service.create_account(
            email="vee@x.com",
            password="Strong123!",
            name="Vee",
            title="",
            role_slug="viewer",
        )
        updated = self.service.update_account_role(
            acc.id, "director", actor_id=self.super_id
        )
        self.assertEqual(updated.role_slug, "director")

    def test_cannot_change_other_superadmin(self) -> None:
        # buat superadmin kedua (dummy untuk test)
        other = self.service.create_account(
            email="other@x.com",
            password="Strong123!",
            name="Other",
            title="",
            role_slug="superadmin",
        )
        with self.assertRaises(AuthServiceError) as ctx:
            self.service.update_account_role(other.id, "viewer", actor_id=self.super_id)
        self.assertEqual(ctx.exception.code, "forbidden")

    def test_cannot_delete_superadmin(self) -> None:
        with self.assertRaises(AuthServiceError):
            self.service.delete_account(self.super_id, actor_id=self.super_id)

    def test_delete_account(self) -> None:
        acc = self.service.create_account(
            email="trash@x.com",
            password="Strong123!",
            name="T",
            title="",
            role_slug="viewer",
        )
        self.service.delete_account(acc.id, actor_id=self.super_id)
        self.assertIsNone(self.service._db.get_account_by_id(acc.id))  # noqa: SLF001


class MobileApiAuthTests(unittest.TestCase):
    """End-to-end mobile_handle test dengan auth_ctx + auth_service."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.service = _make_service(Path(self._tmp.name))
        self.super_id = _seed_superadmin(self.service)
        # Login superadmin sekali untuk dapat token + ctx.
        self.super_login = self.service.login_email("hans@emasberlian.com", "Sup3rPa55!")
        self.super_ctx = self.service.verify_access_token(self.super_login.access_token)
        # Viewer untuk negative tests.
        viewer = self.service.create_account(
            email="vee@x.com",
            password="Strong123!",
            name="Vee",
            title="",
            role_slug="viewer",
        )
        self.viewer_login = self.service.login_email("vee@x.com", "Strong123!")
        self.viewer_ctx = self.service.verify_access_token(self.viewer_login.access_token)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _call(self, method, path, *, ctx=None, body=None, query=None):
        return mobile_handle(
            method,
            path,
            query or {},
            body,
            auth_ctx=ctx,
            auth_service=self.service,
        )

    # ── Login endpoint ───────────────────────────────────
    def test_login_endpoint_ok(self) -> None:
        status, payload = self._call(
            "POST", "/auth/login",
            body={"email": "hans@emasberlian.com", "password": "Sup3rPa55!"},
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertIn("access_token", payload)
        self.assertEqual(payload["user"]["email"], "hans@emasberlian.com")
        self.assertIn("accounts:read", payload["scopes"])

    def test_login_endpoint_wrong_pw(self) -> None:
        status, payload = self._call(
            "POST", "/auth/login",
            body={"email": "hans@emasberlian.com", "password": "wrong"},
        )
        self.assertEqual(status, HTTPStatus.UNAUTHORIZED)
        self.assertEqual(payload["error"]["code"], "invalid_credentials")

    # ── Authed access requires token ─────────────────────
    def test_no_token_returns_401(self) -> None:
        status, payload = self._call("GET", "/me", ctx=None)
        self.assertEqual(status, HTTPStatus.UNAUTHORIZED)

    def test_me_with_ctx(self) -> None:
        status, payload = self._call("GET", "/me", ctx=self.super_ctx)
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(payload["email"], "hans@emasberlian.com")
        self.assertEqual(payload["role"], "superadmin")

    # ── RBAC: viewer cannot access accounts ──────────────
    def test_viewer_blocked_from_accounts_list(self) -> None:
        status, payload = self._call("GET", "/accounts", ctx=self.viewer_ctx)
        self.assertEqual(status, HTTPStatus.FORBIDDEN)
        self.assertEqual(payload["error"]["code"], "forbidden")

    def test_viewer_blocked_from_create_account(self) -> None:
        status, payload = self._call(
            "POST", "/accounts",
            ctx=self.viewer_ctx,
            body={
                "email": "x@x.com",
                "password": "Strong123!",
                "name": "X",
                "title": "",
                "role": "viewer",
            },
        )
        self.assertEqual(status, HTTPStatus.FORBIDDEN)

    def test_viewer_can_read_dashboard(self) -> None:
        status, payload = self._call(
            "GET", "/dashboard/summary",
            ctx=self.viewer_ctx,
            query={"period": "month"},
        )
        self.assertEqual(status, HTTPStatus.OK)

    def test_viewer_blocked_from_chat(self) -> None:
        status, payload = self._call(
            "POST", "/chat/messages",
            ctx=self.viewer_ctx,
            body={"message": "halo"},
        )
        self.assertEqual(status, HTTPStatus.FORBIDDEN)

    # ── Superadmin CRUD via API ──────────────────────────
    def test_superadmin_can_list_accounts(self) -> None:
        status, payload = self._call("GET", "/accounts", ctx=self.super_ctx)
        self.assertEqual(status, HTTPStatus.OK)
        emails = {a["email"] for a in payload["accounts"]}
        self.assertIn("hans@emasberlian.com", emails)
        self.assertIn("vee@x.com", emails)

    def test_superadmin_can_create_account(self) -> None:
        status, payload = self._call(
            "POST", "/accounts",
            ctx=self.super_ctx,
            body={
                "email": "newdir@lumbungemas.co.id",
                "password": "Strong123!",
                "name": "New Direksi",
                "title": "Direktur Keuangan",
                "role": "director",
            },
        )
        self.assertEqual(status, HTTPStatus.CREATED)
        self.assertEqual(payload["email"], "newdir@lumbungemas.co.id")
        self.assertEqual(payload["role"], "director")

    def test_superadmin_can_update_role(self) -> None:
        viewer_id = self.viewer_ctx.account_id
        status, payload = self._call(
            "PATCH", f"/accounts/{viewer_id}/role",
            ctx=self.super_ctx,
            body={"role": "director"},
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(payload["role"], "director")

    def test_superadmin_can_delete(self) -> None:
        # buat dummy
        st, payload = self._call(
            "POST", "/accounts",
            ctx=self.super_ctx,
            body={
                "email": "trash@x.com",
                "password": "Strong123!",
                "name": "T",
                "title": "",
                "role": "viewer",
            },
        )
        self.assertEqual(st, HTTPStatus.CREATED)
        new_id = payload["id"]
        st, _ = self._call("DELETE", f"/accounts/{new_id}", ctx=self.super_ctx)
        self.assertEqual(st, HTTPStatus.NO_CONTENT)

    def test_roles_endpoint(self) -> None:
        status, payload = self._call("GET", "/accounts/roles", ctx=self.super_ctx)
        self.assertEqual(status, HTTPStatus.OK)
        slugs = {r["slug"] for r in payload["roles"]}
        self.assertEqual(slugs, {"superadmin", "admin", "director", "viewer"})

    # ── Bootstrap context (legacy fallback) ──────────────
    def test_bootstrap_ctx_can_read_dashboard(self) -> None:
        boot = AuthContext(
            account_id="bootstrap",
            email="bootstrap@codi",
            role_slug="bootstrap",
            scopes=("dashboard:read", "insight:read", "chat:use"),
            is_bootstrap=True,
        )
        status, payload = self._call("GET", "/dashboard/summary", ctx=boot)
        self.assertEqual(status, HTTPStatus.OK)

    def test_bootstrap_ctx_blocked_from_accounts(self) -> None:
        boot = AuthContext(
            account_id="bootstrap",
            email="bootstrap@codi",
            role_slug="bootstrap",
            scopes=("dashboard:read", "insight:read"),
            is_bootstrap=True,
        )
        status, _ = self._call("GET", "/accounts", ctx=boot)
        self.assertEqual(status, HTTPStatus.FORBIDDEN)

    def test_bootstrap_ctx_cannot_enroll_device(self) -> None:
        boot = AuthContext(
            account_id="bootstrap",
            email="bootstrap@codi",
            role_slug="bootstrap",
            scopes=("dashboard:read",),
            is_bootstrap=True,
        )
        status, payload = self._call(
            "POST", "/auth/enroll-biometric",
            ctx=boot,
            body={"device_id": "x", "fingerprint": "y", "platform": "android"},
        )
        self.assertEqual(status, HTTPStatus.FORBIDDEN)


if __name__ == "__main__":
    unittest.main()
