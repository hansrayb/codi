"""RBAC scope guard."""

from __future__ import annotations

from .models import AuthContext


class AuthError(Exception):
    """Akses ditolak (scope tak cukup atau token tak valid)."""

    def __init__(self, code: str, message: str, *, http_status: int = 403) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def has_scope(ctx: AuthContext | None, scope: str) -> bool:
    """Cek apakah `ctx` punya `scope`.

    Bootstrap token (legacy) **tak** dapat scope penuh — cuma dashboard:read +
    insight:read (cukup untuk app lama yang belum migrasi).
    """
    if ctx is None:
        return False
    if ctx.is_bootstrap:
        return scope in {"dashboard:read", "insight:read", "chat:use"}
    return scope in ctx.scopes


def require_scope(ctx: AuthContext | None, scope: str) -> None:
    """Raise `AuthError` kalau scope tidak terpenuhi."""
    if ctx is None:
        raise AuthError("unauthorized", "Token tidak valid.", http_status=401)
    if not has_scope(ctx, scope):
        raise AuthError(
            "forbidden",
            f"Akses ditolak. Scope '{scope}' diperlukan.",
            http_status=403,
        )
