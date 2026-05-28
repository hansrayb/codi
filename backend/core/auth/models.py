"""Tipe data domain auth (account, role, device, JWT context)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Sequence


@dataclass(frozen=True)
class Role:
    """Role dengan kumpulan scope (RBAC)."""

    slug: str
    name: str
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class Account:
    """Akun direksi/admin di sistem mobile."""

    id: str
    email: str
    name: str
    title: str
    role_slug: str
    status: str  # active | suspended | pending
    created_at: datetime
    last_login_at: datetime | None = None
    # password_hash sengaja tak dibawa keluar service.


@dataclass(frozen=True)
class DeviceBinding:
    """Binding device fisik ke account (untuk biometric login)."""

    id: str
    account_id: str
    device_id: str
    fingerprint: str
    platform: str
    enrolled_at: datetime
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class AuthContext:
    """Hasil verifikasi token JWT untuk satu request.

    Kalau `is_bootstrap=True`, request pakai shared-token legacy
    (fase A1) — diberi scope minimal dashboard:read agar app lama
    tak mati saat migrasi.
    """

    account_id: str
    email: str
    role_slug: str
    scopes: tuple[str, ...] = field(default_factory=tuple)
    is_bootstrap: bool = False
