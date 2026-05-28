"""Auth module untuk mobile direksi (Emas Berlian Insight).

Menyimpan account + role + device binding di SQLite (`codi-auth.db`).
JWT HS256 untuk access/refresh token. RBAC scope-based.

Public API utama:
- `AuthDb.connect(path)` — buka SQLite + init schema kalau belum ada
- `AuthService(db, jwt_helper)` — login, enroll, CRUD accounts
- `JwtHelper(secret, access_ttl, refresh_ttl)` — sign/verify token
- `require_scope(auth_ctx, scope)` — guard pemeriksaan scope
"""

from .db import AuthDb
from .jwt_helper import JwtHelper
from .models import Account, AuthContext, DeviceBinding, Role
from .rbac import AuthError, has_scope, require_scope
from .service import AuthService

__all__ = [
    "Account",
    "AuthContext",
    "AuthDb",
    "AuthError",
    "AuthService",
    "DeviceBinding",
    "JwtHelper",
    "Role",
    "has_scope",
    "require_scope",
]
