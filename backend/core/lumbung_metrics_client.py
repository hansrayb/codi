"""Read-only HTTP client untuk NestJS Lumbung Emas `/executive/metrics/*`.

Codi memanggil endpoint agregasi nyata (dibangun di backend NestJS) lalu
me-reshape ke kontrak app (`core/mobile_metrics.py`). Client ini:

- GET only — tidak ada mutasi (Codi tak menyentuh DB di arsitektur ini).
- Auth via **login akun service** (`POST /api/auth/login` {email,password}) →
  cache access token → re-login otomatis saat kedaluwarsa / kena 401.
  (Access token TTL ~15m, jadi kita cache di bawah itu lalu login ulang.)
- Timeout pendek + retry ringan untuk error transient (jaringan / 5xx).

Pola sama dengan `hr_client.py`: login pakai service account, bukan token
statis (yang bakal mati dalam 15 menit).
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_TIMEOUT = 8.0
DEFAULT_RETRIES = 1
DEFAULT_TOKEN_TTL_SECONDS = 12 * 60  # < 15m JWT TTL; re-login sebelum kedaluwarsa.
_RETRY_BACKOFF_SECONDS = 0.4
_RETRYABLE_STATUS = {500, 502, 503, 504}


class LumbungMetricsError(Exception):
    """Raised when the NestJS metrics API is unreachable or returns an error."""


class LumbungMetricsClient:
    """GET client for the NestJS executive metrics endpoints, login-authenticated."""

    def __init__(
        self,
        metrics_url: str,
        email: str,
        password: str,
        *,
        login_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        token_ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS,
    ) -> None:
        self._base_url = metrics_url.rstrip("/")
        self._login_url = login_url or self._derive_login_url(self._base_url)
        self._email = email
        self._password = password
        self._timeout = timeout
        self._retries = max(0, retries)
        self._token_ttl = token_ttl_seconds
        self._token: str | None = None
        self._token_expiry = 0.0
        self._lock = threading.Lock()

    @staticmethod
    def _derive_login_url(metrics_url: str) -> str:
        # ".../api/executive/metrics" -> ".../api/auth/login"
        root = metrics_url.rsplit("/executive/metrics", 1)[0]
        return f"{root}/auth/login"

    def get_dashboard(self, period: str) -> dict[str, Any]:
        """Fetch `/dashboard?period=...` (raw NestJS shape)."""
        return self._get("/dashboard", {"period": period})

    def get_insight(self, period: str) -> dict[str, Any]:
        """Fetch `/insight?period=...` (raw NestJS shape)."""
        return self._get("/insight", {"period": period})

    # ── auth ──────────────────────────────────────────────────────────────────

    def _get_token(self, *, force: bool = False) -> str:
        with self._lock:
            if not force and self._token and time.time() < self._token_expiry:
                return self._token
            self._token = self._login()
            self._token_expiry = time.time() + self._token_ttl
            return self._token

    def _invalidate_token(self) -> None:
        with self._lock:
            self._token = None
            self._token_expiry = 0.0

    def _login(self) -> str:
        body = json.dumps({"email": self._email, "password": self._password}).encode()
        req = urllib.request.Request(
            self._login_url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Client": "codi-metrics-proxy",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error = LumbungMetricsError(f"metrics login → {exc.code} {exc.reason}")
            error.retryable = exc.code in _RETRYABLE_STATUS  # type: ignore[attr-defined]
            raise error from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            error = LumbungMetricsError(f"metrics login unreachable: {exc}")
            error.retryable = True  # type: ignore[attr-defined]
            raise error from exc
        except json.JSONDecodeError as exc:
            raise LumbungMetricsError(f"metrics login returned non-JSON: {exc}") from exc

        tokens = payload.get("tokens") if isinstance(payload, dict) else None
        token = (
            (tokens or {}).get("accessToken")
            or (payload or {}).get("accessToken")
            or (payload or {}).get("access_token")
        )
        if not token:
            raise LumbungMetricsError("metrics login did not return an access token")
        return str(token)

    # ── requests ────────────────────────────────────────────────────────────

    def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v})
        url = f"{self._base_url}{path}{('?' + query) if query else ''}"
        last_error: Exception | None = None

        for attempt in range(self._retries + 1):
            try:
                return self._fetch_get(url, self._get_token())
            except LumbungMetricsError as exc:
                last_error = exc
                # Token kedaluwarsa di tengah jalan: login ulang sekali & coba lagi.
                if getattr(exc, "auth_expired", False):
                    self._invalidate_token()
                    try:
                        return self._fetch_get(url, self._get_token(force=True))
                    except LumbungMetricsError as exc2:
                        last_error = exc2
                        exc = exc2
                if not getattr(exc, "retryable", False) or attempt == self._retries:
                    raise
                time.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))

        raise last_error or LumbungMetricsError("metrics request failed")

    def _fetch_get(self, url: str, token: str) -> dict[str, Any]:
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "X-Client": "codi-metrics-proxy",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error = LumbungMetricsError(f"metrics API {url} → {exc.code} {exc.reason}")
            error.retryable = exc.code in _RETRYABLE_STATUS  # type: ignore[attr-defined]
            error.auth_expired = exc.code in {401, 403}  # type: ignore[attr-defined]
            raise error from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            error = LumbungMetricsError(f"metrics API unreachable: {exc}")
            error.retryable = True  # type: ignore[attr-defined]
            raise error from exc
        except json.JSONDecodeError as exc:
            raise LumbungMetricsError(f"metrics API returned non-JSON: {exc}") from exc

        if not isinstance(payload, dict):
            raise LumbungMetricsError("metrics API returned unexpected (non-object) body")
        return payload
