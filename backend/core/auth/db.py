"""SQLite layer untuk auth (accounts, roles, device_bindings)."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .models import Account, DeviceBinding, Role


# Default scope per role. Bisa di-override per-row di tabel `roles`.
DEFAULT_ROLE_SCOPES: dict[str, tuple[str, ...]] = {
    "superadmin": (
        "accounts:read",
        "accounts:create",
        "accounts:update",
        "accounts:delete",
        "dashboard:read",
        "reports:read",
        "reports:write",
        "chat:use",
        "insight:read",
    ),
    "admin": (
        "accounts:read",
        "accounts:update_role",
        "dashboard:read",
        "reports:read",
        "reports:write",
        "chat:use",
        "insight:read",
    ),
    "director": (
        "dashboard:read",
        "reports:read",
        "chat:use",
        "insight:read",
    ),
    "viewer": (
        "dashboard:read",
        "insight:read",
    ),
}

DEFAULT_ROLE_NAMES: dict[str, str] = {
    "superadmin": "Super Admin",
    "admin": "Admin",
    "director": "Direksi",
    "viewer": "Viewer",
}


_SCHEMA = """
CREATE TABLE IF NOT EXISTS roles (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    scopes_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    role_slug TEXT NOT NULL REFERENCES roles(slug),
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    last_login_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_accounts_email ON accounts(email);

CREATE TABLE IF NOT EXISTS device_bindings (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    device_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    platform TEXT NOT NULL,
    enrolled_at TEXT NOT NULL,
    revoked_at TEXT,
    UNIQUE(account_id, device_id)
);

CREATE INDEX IF NOT EXISTS idx_device_bindings_account ON device_bindings(account_id);
CREATE INDEX IF NOT EXISTS idx_device_bindings_device ON device_bindings(device_id);
"""


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


class AuthDb:
    """Wrapper SQLite untuk auth schema."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._lock = threading.RLock()

    # ── Lifecycle ──────────────────────────────────────────────
    @classmethod
    def connect(cls, path: Path) -> "AuthDb":
        path = Path(path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(_SCHEMA)
        conn.commit()
        return cls(conn)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ── Roles ──────────────────────────────────────────────────
    def upsert_role(self, slug: str, name: str, scopes: Iterable[str]) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO roles(slug, name, scopes_json) VALUES(?,?,?) "
                "ON CONFLICT(slug) DO UPDATE SET name=excluded.name, scopes_json=excluded.scopes_json",
                (slug, name, json.dumps(list(scopes))),
            )
            self._conn.commit()

    def seed_default_roles(self) -> None:
        for slug, scopes in DEFAULT_ROLE_SCOPES.items():
            self.upsert_role(slug, DEFAULT_ROLE_NAMES[slug], scopes)

    def get_role(self, slug: str) -> Role | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT slug, name, scopes_json FROM roles WHERE slug = ?",
                (slug,),
            ).fetchone()
        if not row:
            return None
        return Role(
            slug=row["slug"],
            name=row["name"],
            scopes=tuple(json.loads(row["scopes_json"])),
        )

    def list_roles(self) -> list[Role]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT slug, name, scopes_json FROM roles ORDER BY slug"
            ).fetchall()
        return [
            Role(
                slug=row["slug"],
                name=row["name"],
                scopes=tuple(json.loads(row["scopes_json"])),
            )
            for row in rows
        ]

    # ── Accounts ───────────────────────────────────────────────
    def insert_account(
        self,
        *,
        account_id: str,
        email: str,
        password_hash: str,
        name: str,
        title: str,
        role_slug: str,
        status: str = "active",
    ) -> Account:
        created_at = _now_iso()
        with self._lock:
            self._conn.execute(
                "INSERT INTO accounts(id, email, password_hash, name, title, role_slug, status, created_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (account_id, email, password_hash, name, title, role_slug, status, created_at),
            )
            self._conn.commit()
        return Account(
            id=account_id,
            email=email,
            name=name,
            title=title,
            role_slug=role_slug,
            status=status,
            created_at=datetime.fromisoformat(created_at),
        )

    def update_account_role(self, account_id: str, role_slug: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE accounts SET role_slug = ? WHERE id = ?",
                (role_slug, account_id),
            )
            self._conn.commit()

    def update_account_status(self, account_id: str, status: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE accounts SET status = ? WHERE id = ?",
                (status, account_id),
            )
            self._conn.commit()

    def update_account_password(self, account_id: str, password_hash: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE accounts SET password_hash = ? WHERE id = ?",
                (password_hash, account_id),
            )
            self._conn.commit()

    def touch_last_login(self, account_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE accounts SET last_login_at = ? WHERE id = ?",
                (_now_iso(), account_id),
            )
            self._conn.commit()

    def delete_account(self, account_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
            self._conn.commit()

    def get_account_by_email(self, email: str) -> tuple[Account, str] | None:
        """Return `(account, password_hash)` atau None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM accounts WHERE email = ?", (email.lower().strip(),)
            ).fetchone()
        if not row:
            return None
        return self._row_to_account(row), row["password_hash"]

    def get_account_by_id(self, account_id: str) -> Account | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM accounts WHERE id = ?", (account_id,)
            ).fetchone()
        if not row:
            return None
        return self._row_to_account(row)

    def list_accounts(self) -> list[Account]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM accounts ORDER BY created_at ASC"
            ).fetchall()
        return [self._row_to_account(row) for row in rows]

    @staticmethod
    def _row_to_account(row: sqlite3.Row) -> Account:
        return Account(
            id=row["id"],
            email=row["email"],
            name=row["name"],
            title=row["title"] or "",
            role_slug=row["role_slug"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            last_login_at=_parse_iso(row["last_login_at"]),
        )

    # ── Device bindings ────────────────────────────────────────
    def upsert_device_binding(
        self,
        *,
        binding_id: str,
        account_id: str,
        device_id: str,
        fingerprint: str,
        platform: str,
    ) -> DeviceBinding:
        enrolled_at = _now_iso()
        with self._lock:
            self._conn.execute(
                "INSERT INTO device_bindings(id, account_id, device_id, fingerprint, platform, enrolled_at) "
                "VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(account_id, device_id) DO UPDATE SET "
                "fingerprint=excluded.fingerprint, platform=excluded.platform, "
                "enrolled_at=excluded.enrolled_at, revoked_at=NULL",
                (binding_id, account_id, device_id, fingerprint, platform, enrolled_at),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM device_bindings WHERE account_id=? AND device_id=?",
                (account_id, device_id),
            ).fetchone()
        return self._row_to_binding(row)

    def find_active_binding(
        self, device_id: str, fingerprint: str
    ) -> DeviceBinding | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM device_bindings "
                "WHERE device_id=? AND fingerprint=? AND revoked_at IS NULL "
                "LIMIT 1",
                (device_id, fingerprint),
            ).fetchone()
        if not row:
            return None
        return self._row_to_binding(row)

    def list_bindings_for_account(self, account_id: str) -> list[DeviceBinding]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM device_bindings WHERE account_id = ? ORDER BY enrolled_at DESC",
                (account_id,),
            ).fetchall()
        return [self._row_to_binding(row) for row in rows]

    def revoke_binding(self, binding_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE device_bindings SET revoked_at = ? WHERE id = ?",
                (_now_iso(), binding_id),
            )
            self._conn.commit()

    @staticmethod
    def _row_to_binding(row: sqlite3.Row) -> DeviceBinding:
        return DeviceBinding(
            id=row["id"],
            account_id=row["account_id"],
            device_id=row["device_id"],
            fingerprint=row["fingerprint"],
            platform=row["platform"],
            enrolled_at=datetime.fromisoformat(row["enrolled_at"]),
            revoked_at=_parse_iso(row["revoked_at"]),
        )
