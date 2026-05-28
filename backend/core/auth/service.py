"""Service layer auth — orchestrate db + bcrypt + jwt."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Iterable

import bcrypt

from .db import AuthDb
from .jwt_helper import JwtError, JwtHelper
from .models import Account, AuthContext, DeviceBinding, Role


class AuthServiceError(Exception):
    """Error bisnis-level (login gagal, email duplikat, role tidak ada, dsb)."""

    def __init__(self, code: str, message: str, *, http_status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


@dataclass
class LoginResult:
    account: Account
    access_token: str
    refresh_token: str
    expires_in: int
    scopes: tuple[str, ...]


# Rate-limit failed login per email (in-memory). 5 attempts / 5 menit.
_MAX_FAILED_ATTEMPTS = 5
_LOCK_WINDOW_SECONDS = 5 * 60


class AuthService:
    """Operasi auth — login, enroll device, CRUD account."""

    def __init__(self, db: AuthDb, jwt_helper: JwtHelper) -> None:
        self._db = db
        self._jwt = jwt_helper
        self._failed_attempts: dict[str, list[float]] = {}

    # ── Token verification ─────────────────────────────────────
    def verify_access_token(self, token: str) -> AuthContext:
        try:
            payload = self._jwt.verify(token, expected_typ="access")
        except JwtError as exc:
            raise AuthServiceError("unauthorized", str(exc), http_status=401) from exc
        account_id = payload.get("sub")
        email = payload.get("email", "")
        role_slug = payload.get("role", "")
        scopes_payload = payload.get("scopes", []) or []
        if not account_id or not isinstance(scopes_payload, list):
            raise AuthServiceError("unauthorized", "Token tidak lengkap.", http_status=401)
        # Cross-check account masih aktif.
        account = self._db.get_account_by_id(str(account_id))
        if account is None or account.status != "active":
            raise AuthServiceError("unauthorized", "Akun tidak aktif.", http_status=401)
        return AuthContext(
            account_id=account.id,
            email=email,
            role_slug=role_slug,
            scopes=tuple(str(s) for s in scopes_payload),
            is_bootstrap=False,
        )

    def refresh(self, refresh_token: str) -> LoginResult:
        try:
            payload = self._jwt.verify(refresh_token, expected_typ="refresh")
        except JwtError as exc:
            raise AuthServiceError("unauthorized", str(exc), http_status=401) from exc
        account_id = str(payload.get("sub") or "")
        account = self._db.get_account_by_id(account_id)
        if account is None or account.status != "active":
            raise AuthServiceError("unauthorized", "Akun tidak aktif.", http_status=401)
        return self._issue_tokens(account)

    # ── Login (email + password) ───────────────────────────────
    def login_email(self, email: str, password: str) -> LoginResult:
        email = email.lower().strip()
        if not email or not password:
            raise AuthServiceError("invalid_credentials", "Email dan password wajib diisi.")
        self._check_rate_limit(email)
        record = self._db.get_account_by_email(email)
        if record is None:
            self._register_failure(email)
            raise AuthServiceError(
                "invalid_credentials", "Email atau password salah.", http_status=401
            )
        account, password_hash = record
        if account.status != "active":
            raise AuthServiceError(
                "account_suspended",
                "Akun ditangguhkan. Hubungi superadmin.",
                http_status=403,
            )
        if not _verify_password(password, password_hash):
            self._register_failure(email)
            raise AuthServiceError(
                "invalid_credentials", "Email atau password salah.", http_status=401
            )
        self._reset_failures(email)
        self._db.touch_last_login(account.id)
        return self._issue_tokens(account)

    # ── Biometric flow ─────────────────────────────────────────
    def enroll_device(
        self,
        *,
        account_id: str,
        device_id: str,
        fingerprint: str,
        platform: str,
    ) -> DeviceBinding:
        if not device_id or not fingerprint:
            raise AuthServiceError("invalid_payload", "device_id dan fingerprint wajib.")
        account = self._db.get_account_by_id(account_id)
        if account is None:
            raise AuthServiceError("not_found", "Akun tidak ditemukan.", http_status=404)
        binding_id = f"dvc_{secrets.token_hex(8)}"
        return self._db.upsert_device_binding(
            binding_id=binding_id,
            account_id=account_id,
            device_id=device_id.strip(),
            fingerprint=fingerprint.strip(),
            platform=platform.strip() or "unknown",
        )

    def login_biometric(
        self, *, device_id: str, fingerprint: str
    ) -> LoginResult:
        if not device_id or not fingerprint:
            raise AuthServiceError(
                "invalid_payload", "device_id dan fingerprint wajib."
            )
        binding = self._db.find_active_binding(device_id.strip(), fingerprint.strip())
        if binding is None:
            raise AuthServiceError(
                "device_not_enrolled",
                "Device belum di-enroll. Login dengan email + password dulu.",
                http_status=401,
            )
        account = self._db.get_account_by_id(binding.account_id)
        if account is None or account.status != "active":
            raise AuthServiceError(
                "account_suspended", "Akun tidak aktif.", http_status=403
            )
        self._db.touch_last_login(account.id)
        return self._issue_tokens(account)

    # ── Account CRUD ───────────────────────────────────────────
    def create_account(
        self,
        *,
        email: str,
        password: str,
        name: str,
        title: str,
        role_slug: str,
    ) -> Account:
        email = email.lower().strip()
        if not email or "@" not in email:
            raise AuthServiceError("invalid_payload", "Email tidak valid.")
        if not password or len(password) < 8:
            raise AuthServiceError(
                "invalid_payload", "Password minimal 8 karakter."
            )
        if not name:
            raise AuthServiceError("invalid_payload", "Nama wajib diisi.")
        role = self._db.get_role(role_slug)
        if role is None:
            raise AuthServiceError("invalid_payload", f"Role '{role_slug}' tidak dikenal.")
        if self._db.get_account_by_email(email) is not None:
            raise AuthServiceError(
                "email_exists", "Email sudah terdaftar.", http_status=409
            )
        account_id = f"acc_{secrets.token_hex(8)}"
        return self._db.insert_account(
            account_id=account_id,
            email=email,
            password_hash=_hash_password(password),
            name=name.strip(),
            title=title.strip(),
            role_slug=role_slug,
        )

    def update_account_role(
        self, account_id: str, role_slug: str, *, actor_id: str
    ) -> Account:
        target = self._db.get_account_by_id(account_id)
        if target is None:
            raise AuthServiceError("not_found", "Akun tidak ditemukan.", http_status=404)
        if target.role_slug == "superadmin" and target.id != actor_id:
            raise AuthServiceError(
                "forbidden",
                "Role superadmin lain tak bisa diubah.",
                http_status=403,
            )
        if self._db.get_role(role_slug) is None:
            raise AuthServiceError("invalid_payload", f"Role '{role_slug}' tidak dikenal.")
        self._db.update_account_role(account_id, role_slug)
        updated = self._db.get_account_by_id(account_id)
        assert updated is not None
        return updated

    def update_account_status(
        self, account_id: str, status: str, *, actor_id: str
    ) -> Account:
        if status not in {"active", "suspended"}:
            raise AuthServiceError("invalid_payload", "Status harus active/suspended.")
        target = self._db.get_account_by_id(account_id)
        if target is None:
            raise AuthServiceError("not_found", "Akun tidak ditemukan.", http_status=404)
        if target.role_slug == "superadmin" and target.id != actor_id:
            raise AuthServiceError(
                "forbidden", "Superadmin lain tak bisa di-suspend.", http_status=403
            )
        self._db.update_account_status(account_id, status)
        updated = self._db.get_account_by_id(account_id)
        assert updated is not None
        return updated

    def delete_account(self, account_id: str, *, actor_id: str) -> None:
        target = self._db.get_account_by_id(account_id)
        if target is None:
            raise AuthServiceError("not_found", "Akun tidak ditemukan.", http_status=404)
        if target.role_slug == "superadmin":
            raise AuthServiceError(
                "forbidden", "Superadmin tak bisa dihapus.", http_status=403
            )
        if target.id == actor_id:
            raise AuthServiceError(
                "forbidden", "Tak bisa menghapus akun sendiri.", http_status=403
            )
        self._db.delete_account(account_id)

    def reset_password(
        self, account_id: str, new_password: str
    ) -> None:
        if not new_password or len(new_password) < 8:
            raise AuthServiceError(
                "invalid_payload", "Password minimal 8 karakter."
            )
        target = self._db.get_account_by_id(account_id)
        if target is None:
            raise AuthServiceError("not_found", "Akun tidak ditemukan.", http_status=404)
        self._db.update_account_password(account_id, _hash_password(new_password))

    def list_accounts(self) -> list[Account]:
        return self._db.list_accounts()

    def list_roles(self) -> list[Role]:
        return self._db.list_roles()

    def list_devices(self, account_id: str) -> list[DeviceBinding]:
        return self._db.list_bindings_for_account(account_id)

    def revoke_device(self, binding_id: str) -> None:
        self._db.revoke_binding(binding_id)

    # ── Helpers ────────────────────────────────────────────────
    def _issue_tokens(self, account: Account) -> LoginResult:
        role = self._db.get_role(account.role_slug)
        scopes: tuple[str, ...] = role.scopes if role else tuple()
        access, expires_in = self._jwt.sign_access(
            account_id=account.id,
            email=account.email,
            role_slug=account.role_slug,
            scopes=scopes,
        )
        refresh = self._jwt.sign_refresh(
            account_id=account.id,
            email=account.email,
            role_slug=account.role_slug,
        )
        return LoginResult(
            account=account,
            access_token=access,
            refresh_token=refresh,
            expires_in=expires_in,
            scopes=scopes,
        )

    def _check_rate_limit(self, email: str) -> None:
        now = time.time()
        attempts = [
            ts for ts in self._failed_attempts.get(email, [])
            if now - ts < _LOCK_WINDOW_SECONDS
        ]
        self._failed_attempts[email] = attempts
        if len(attempts) >= _MAX_FAILED_ATTEMPTS:
            raise AuthServiceError(
                "too_many_attempts",
                "Terlalu banyak percobaan gagal. Coba lagi dalam 5 menit.",
                http_status=429,
            )

    def _register_failure(self, email: str) -> None:
        self._failed_attempts.setdefault(email, []).append(time.time())

    def _reset_failures(self, email: str) -> None:
        self._failed_attempts.pop(email, None)


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False
