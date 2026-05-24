"""Read-only HTTP client untuk NestJS Lumbung Emas `/executive/metrics/*`.

Codi memanggil endpoint agregasi nyata (dibangun di backend NestJS) lalu
me-reshape ke kontrak app (`core/mobile_metrics.py`). Client ini:

- GET only — tidak ada mutasi (Codi tak menyentuh DB di arsitektur ini).
- Auth via static bearer token (`LUMBUNG_METRICS_TOKEN`) — bukan login flow.
- Timeout pendek + retry ringan untuk error transient (jaringan / 5xx).

Berbeda dengan `hr_client.py` (yang login email/password), metrics endpoint
diakses dengan service token pre-issued yang dikonfigurasi via env.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_TIMEOUT = 8.0
DEFAULT_RETRIES = 1
_RETRY_BACKOFF_SECONDS = 0.4
_RETRYABLE_STATUS = {500, 502, 503, 504}


class LumbungMetricsError(Exception):
    """Raised when the NestJS metrics API is unreachable or returns an error."""


class LumbungMetricsClient:
    """Minimal GET client for the NestJS executive metrics endpoints."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._retries = max(0, retries)

    def get_dashboard(self, period: str) -> dict[str, Any]:
        """Fetch `/dashboard?period=...` (raw NestJS shape)."""
        return self._get("/dashboard", {"period": period})

    def get_insight(self, period: str) -> dict[str, Any]:
        """Fetch `/insight?period=...` (raw NestJS shape)."""
        return self._get("/insight", {"period": period})

    # ── internals ───────────────────────────────────────────────────────────

    def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v})
        url = f"{self._base_url}{path}{('?' + query) if query else ''}"
        last_error: Exception | None = None

        for attempt in range(self._retries + 1):
            try:
                return self._fetch(url)
            except LumbungMetricsError as exc:
                last_error = exc
                if not getattr(exc, "retryable", False) or attempt == self._retries:
                    raise
                time.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))

        # Unreachable, but keeps type-checkers happy.
        raise last_error or LumbungMetricsError("metrics request failed")

    def _fetch(self, url: str) -> dict[str, Any]:
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self._token}",
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
