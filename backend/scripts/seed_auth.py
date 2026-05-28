"""Seed auth schema + superadmin awal.

Usage:
    cd backend
    python -m scripts.seed_auth

Membutuhkan env var:
- `CODI_JWT_SECRET` (untuk validasi config; tak dipakai langsung di sini)
- `SUPERADMIN_EMAIL` (default `hans@emasberlian.com`)
- `SUPERADMIN_PASSWORD` (wajib di-set)
- `SUPERADMIN_NAME`, `SUPERADMIN_TITLE` (opsional)
- `AUTH_DB_PATH` (lokasi SQLite; default `backend/data/codi-auth.db`)

Idempotent — aman dijalankan ulang. Kalau superadmin sudah ada, akan di-update
nama/title saja (password tidak ditimpa).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `python -m scripts.seed_auth` dari folder backend/
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import load_settings  # noqa: E402
from core.auth import AuthDb, AuthService, JwtHelper  # noqa: E402


def main() -> int:
    settings = load_settings()
    if not settings.superadmin_password:
        print(
            "ERROR: SUPERADMIN_PASSWORD belum di-set di .env.\n"
            "Tambahkan baris: SUPERADMIN_PASSWORD=<password kuat>",
            file=sys.stderr,
        )
        return 2
    if len(settings.superadmin_password) < 8:
        print(
            "ERROR: SUPERADMIN_PASSWORD minimal 8 karakter.",
            file=sys.stderr,
        )
        return 2
    if not settings.codi_jwt_secret:
        print(
            "ERROR: CODI_JWT_SECRET belum di-set di .env.\n"
            "Generate: python -c 'import secrets; print(secrets.token_hex(32))'",
            file=sys.stderr,
        )
        return 2

    db = AuthDb.connect(settings.auth_db_path)
    db.seed_default_roles()
    print(f"[ok] Schema siap di {settings.auth_db_path}")
    print(f"[ok] Seed roles: {[r.slug for r in db.list_roles()]}")

    jwt = JwtHelper(
        secret=settings.codi_jwt_secret,
        access_ttl_minutes=settings.codi_jwt_access_ttl_minutes,
        refresh_ttl_days=settings.codi_jwt_refresh_ttl_days,
    )
    service = AuthService(db, jwt)

    existing = db.get_account_by_email(settings.superadmin_email)
    if existing is not None:
        account, _ = existing
        print(
            f"[skip] Superadmin {settings.superadmin_email} sudah ada "
            f"(id={account.id}, role={account.role_slug}). Password TIDAK ditimpa.",
        )
        return 0

    account = service.create_account(
        email=settings.superadmin_email,
        password=settings.superadmin_password,
        name=settings.superadmin_name,
        title=settings.superadmin_title,
        role_slug="superadmin",
    )
    print(
        f"[ok] Superadmin dibuat:\n"
        f"     id    = {account.id}\n"
        f"     email = {account.email}\n"
        f"     role  = {account.role_slug}\n"
        f"     name  = {account.name}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
