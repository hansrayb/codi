"""JWT sign/verify helper (HS256)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt


class JwtError(Exception):
    """Token tidak valid / expired / signature salah."""


@dataclass(frozen=True)
class JwtHelper:
    """Sign + verify JWT pakai HS256.

    `access_ttl_minutes` = umur access token (request normal).
    `refresh_ttl_days`   = umur refresh token (rotasi access token).
    """

    secret: str
    access_ttl_minutes: int = 60 * 24 * 7
    refresh_ttl_days: int = 30
    issuer: str = "codi"

    def sign_access(
        self,
        *,
        account_id: str,
        email: str,
        role_slug: str,
        scopes: tuple[str, ...] | list[str],
    ) -> tuple[str, int]:
        """Return `(token, expires_in_seconds)`."""
        ttl = timedelta(minutes=self.access_ttl_minutes)
        payload = self._base_payload(
            account_id=account_id,
            email=email,
            role_slug=role_slug,
            ttl=ttl,
            extra={"scopes": list(scopes), "typ": "access"},
        )
        token = jwt.encode(payload, self.secret, algorithm="HS256")
        return token, int(ttl.total_seconds())

    def sign_refresh(
        self,
        *,
        account_id: str,
        email: str,
        role_slug: str,
    ) -> str:
        ttl = timedelta(days=self.refresh_ttl_days)
        payload = self._base_payload(
            account_id=account_id,
            email=email,
            role_slug=role_slug,
            ttl=ttl,
            extra={"typ": "refresh"},
        )
        return jwt.encode(payload, self.secret, algorithm="HS256")

    def verify(self, token: str, *, expected_typ: str = "access") -> dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=["HS256"],
                options={"require": ["exp", "iat", "sub"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise JwtError("token_expired") from exc
        except jwt.InvalidTokenError as exc:
            raise JwtError("token_invalid") from exc
        if payload.get("typ") != expected_typ:
            raise JwtError("token_wrong_type")
        if payload.get("iss") != self.issuer:
            raise JwtError("token_wrong_issuer")
        return payload

    def _base_payload(
        self,
        *,
        account_id: str,
        email: str,
        role_slug: str,
        ttl: timedelta,
        extra: dict[str, Any],
    ) -> dict[str, Any]:
        now = datetime.now(tz=timezone.utc)
        return {
            "iss": self.issuer,
            "sub": account_id,
            "email": email,
            "role": role_slug,
            "iat": int(now.timestamp()),
            "exp": int((now + ttl).timestamp()),
            **extra,
        }
