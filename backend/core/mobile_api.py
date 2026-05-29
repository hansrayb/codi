"""Mobile API (`/api/v1/*`) untuk app Emas Berlian Insight.

Fase B — auth + RBAC nyata:
- `/auth/login` email + password → JWT access/refresh
- `/auth/login-biometric` device_id + fingerprint → JWT (post-enroll)
- `/auth/enroll-biometric` (authed) bind device fingerprint ke account
- `/auth/refresh` rotasi access token
- `/accounts/*` CRUD (RBAC: scope `accounts:*`)
- `/dashboard/*`, `/insight`, `/chat/*`, `/me` gate via `require_scope`

Dispatch dari `core/device_api.py` — `auth_ctx` diisi server setelah
verifikasi JWT (atau shared-token bootstrap fase A1).
"""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any, Callable

from core import mobile_metrics
from core.auth.models import AuthContext
from core.auth.rbac import AuthError, require_scope
from core.auth.service import AuthService, AuthServiceError

# Sync chat callable signature: (message, user_id, scope) -> reply text.
ChatFn = Callable[[str, int, str], str]

logger = logging.getLogger(__name__)

JsonResult = tuple[HTTPStatus, dict[str, Any]]


# ── Entry point ─────────────────────────────────────────────────────
def mobile_handle(
    method: str,
    path: str,
    query: dict[str, str],
    body: dict[str, Any] | None,
    *,
    auth_ctx: AuthContext | None,
    auth_service: AuthService | None,
    chat_fn: ChatFn | None = None,
) -> JsonResult:
    """Dispatch satu request mobile.

    `path` sudah tanpa prefix `/api/v1` dan tanpa query string.
    `auth_ctx` = hasil verifikasi token (None untuk login/refresh).
    `auth_service` = service auth; bila None, endpoint auth/accounts gagal.
    `chat_fn` = sync chat callable (msg, user_id, scope) -> reply text.
                Bila None, `/chat/messages` return stub fallback.
    """
    try:
        return _dispatch(
            method=method,
            path=path,
            query=query,
            body=body,
            auth_ctx=auth_ctx,
            auth_service=auth_service,
            chat_fn=chat_fn,
        )
    except AuthError as exc:
        return _http(exc.http_status), _error(exc.code, exc.message)
    except AuthServiceError as exc:
        return _http(exc.http_status), _error(exc.code, exc.message)


def _dispatch(
    *,
    method: str,
    path: str,
    query: dict[str, str],
    body: dict[str, Any] | None,
    auth_ctx: AuthContext | None,
    auth_service: AuthService | None,
    chat_fn: ChatFn | None,
) -> JsonResult:
    # ── Public auth endpoints ────────────────────────────────
    if method == "POST" and path == "/auth/login":
        return _auth_login(body, auth_service)
    if method == "POST" and path == "/auth/login-biometric":
        return _auth_login_biometric(body, auth_service)
    if method == "POST" and path == "/auth/refresh":
        return _auth_refresh(body, auth_service)
    if method == "POST" and path == "/auth/logout":
        return HTTPStatus.OK, {"ok": True}

    # ── Authed endpoints ────────────────────────────────────
    if auth_ctx is None:
        return HTTPStatus.UNAUTHORIZED, _error("unauthorized", "Token tidak valid.")

    if method == "POST" and path == "/auth/enroll-biometric":
        return _auth_enroll_biometric(body, auth_ctx, auth_service)
    if method == "GET" and path == "/me":
        return _me(auth_ctx, auth_service)
    if method == "PATCH" and path == "/me/preferences":
        return _me(auth_ctx, auth_service, preferences_override=body)
    if method == "GET" and path == "/dashboard/summary":
        require_scope(auth_ctx, "dashboard:read")
        return _dashboard_summary(query.get("period", "month"))
    if method == "GET" and path == "/dashboard/insight":
        require_scope(auth_ctx, "insight:read")
        return _dashboard_insight(query.get("period", "month"))
    if method == "POST" and path == "/chat/messages":
        require_scope(auth_ctx, "chat:use")
        return _chat_messages(body, chat_fn)
    if method == "GET" and path == "/chat/conversations":
        require_scope(auth_ctx, "chat:use")
        return _chat_conversations()
    if (
        method == "GET"
        and path.startswith("/chat/conversations/")
        and path.endswith("/messages")
    ):
        require_scope(auth_ctx, "chat:use")
        conv_id = path[len("/chat/conversations/") : -len("/messages")]
        return _chat_conversation_messages(conv_id)

    # ── Account management ─────────────────────────────────
    if method == "GET" and path == "/accounts":
        require_scope(auth_ctx, "accounts:read")
        return _accounts_list(auth_service)
    if method == "POST" and path == "/accounts":
        require_scope(auth_ctx, "accounts:create")
        return _accounts_create(body, auth_service)
    if method == "GET" and path == "/accounts/roles":
        require_scope(auth_ctx, "accounts:read")
        return _accounts_roles(auth_service)
    if method == "PATCH" and path.startswith("/accounts/") and path.endswith("/role"):
        require_scope_any(auth_ctx, ("accounts:update", "accounts:update_role"))
        account_id = path[len("/accounts/") : -len("/role")]
        return _accounts_update_role(account_id, body, auth_ctx, auth_service)
    if method == "PATCH" and path.startswith("/accounts/") and path.endswith("/status"):
        require_scope(auth_ctx, "accounts:update")
        account_id = path[len("/accounts/") : -len("/status")]
        return _accounts_update_status(account_id, body, auth_ctx, auth_service)
    if method == "PATCH" and path.startswith("/accounts/") and path.endswith("/password"):
        require_scope(auth_ctx, "accounts:update")
        account_id = path[len("/accounts/") : -len("/password")]
        return _accounts_reset_password(account_id, body, auth_service)
    if (
        method == "PATCH"
        and path.startswith("/accounts/")
        and not path.endswith("/role")
        and not path.endswith("/status")
        and not path.endswith("/password")
    ):
        require_scope(auth_ctx, "accounts:update")
        account_id = path[len("/accounts/") :]
        return _accounts_update_profile(account_id, body, auth_service)
    if (
        method == "DELETE"
        and path.startswith("/accounts/")
        and "/devices/" not in path
        and not path.endswith("/role")
        and not path.endswith("/status")
        and not path.endswith("/password")
    ):
        require_scope(auth_ctx, "accounts:delete")
        account_id = path[len("/accounts/") :]
        return _accounts_delete(account_id, auth_ctx, auth_service)
    if method == "GET" and path.startswith("/accounts/") and path.endswith("/devices"):
        require_scope(auth_ctx, "accounts:read")
        account_id = path[len("/accounts/") : -len("/devices")]
        return _accounts_devices(account_id, auth_service)
    if (
        method == "DELETE"
        and path.startswith("/accounts/")
        and "/devices/" in path
    ):
        require_scope(auth_ctx, "accounts:update")
        binding_id = path.rsplit("/", 1)[-1]
        return _accounts_revoke_device(binding_id, auth_service)

    return HTTPStatus.NOT_FOUND, _error("not_found", "Endpoint tidak ditemukan.")


# ── Helpers ─────────────────────────────────────────────────────────
def _ensure_service(service: AuthService | None) -> AuthService:
    if service is None:
        raise AuthServiceError(
            "auth_unavailable",
            "Auth service belum siap di server.",
            http_status=503,
        )
    return service


def require_scope_any(auth_ctx: AuthContext | None, scopes: tuple[str, ...]) -> None:
    """Helper: butuh salah satu scope di tuple."""
    from core.auth.rbac import has_scope as _has_scope

    for scope in scopes:
        if _has_scope(auth_ctx, scope):
            return
    raise AuthError(
        "forbidden",
        f"Akses ditolak. Salah satu scope diperlukan: {', '.join(scopes)}.",
        http_status=403,
    )


def _http(status_code: int) -> HTTPStatus:
    try:
        return HTTPStatus(status_code)
    except ValueError:
        return HTTPStatus.INTERNAL_SERVER_ERROR


def _error(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


def _account_to_dict(account: Any) -> dict[str, Any]:
    return {
        "id": account.id,
        "email": account.email,
        "name": account.name,
        "title": account.title,
        "role": account.role_slug,
        "status": account.status,
        "created_at": account.created_at.isoformat(),
        "last_login_at": account.last_login_at.isoformat() if account.last_login_at else None,
    }


def _login_result_to_dict(result: Any) -> dict[str, Any]:
    return {
        "access_token": result.access_token,
        "refresh_token": result.refresh_token,
        "expires_in": result.expires_in,
        "scopes": list(result.scopes),
        "user": _account_to_dict(result.account),
    }


# ── Auth handlers ───────────────────────────────────────────────────
def _auth_login(body: dict[str, Any] | None, service: AuthService | None) -> JsonResult:
    service = _ensure_service(service)
    payload = body or {}
    email = str(payload.get("email") or "")
    password = str(payload.get("password") or "")
    result = service.login_email(email, password)
    return HTTPStatus.OK, _login_result_to_dict(result)


def _auth_login_biometric(
    body: dict[str, Any] | None, service: AuthService | None
) -> JsonResult:
    service = _ensure_service(service)
    payload = body or {}
    device_id = str(payload.get("device_id") or "")
    fingerprint = str(payload.get("device_fingerprint") or payload.get("fingerprint") or "")
    result = service.login_biometric(device_id=device_id, fingerprint=fingerprint)
    return HTTPStatus.OK, _login_result_to_dict(result)


def _auth_refresh(body: dict[str, Any] | None, service: AuthService | None) -> JsonResult:
    service = _ensure_service(service)
    payload = body or {}
    refresh_token = str(payload.get("refresh_token") or "")
    if not refresh_token:
        raise AuthServiceError("invalid_payload", "refresh_token wajib.")
    result = service.refresh(refresh_token)
    return HTTPStatus.OK, _login_result_to_dict(result)


def _auth_enroll_biometric(
    body: dict[str, Any] | None,
    auth_ctx: AuthContext,
    service: AuthService | None,
) -> JsonResult:
    service = _ensure_service(service)
    if auth_ctx.is_bootstrap:
        raise AuthError(
            "forbidden",
            "Bootstrap token tak bisa enroll device.",
            http_status=403,
        )
    payload = body or {}
    device_id = str(payload.get("device_id") or "")
    fingerprint = str(payload.get("device_fingerprint") or payload.get("fingerprint") or "")
    platform = str(payload.get("platform") or "")
    binding = service.enroll_device(
        account_id=auth_ctx.account_id,
        device_id=device_id,
        fingerprint=fingerprint,
        platform=platform,
    )
    return HTTPStatus.OK, {
        "binding_id": binding.id,
        "device_id": binding.device_id,
        "platform": binding.platform,
        "enrolled_at": binding.enrolled_at.isoformat(),
    }


def _me(
    auth_ctx: AuthContext,
    service: AuthService | None,
    preferences_override: dict[str, Any] | None = None,
) -> JsonResult:
    prefs: dict[str, Any] = {
        "language": "id",
        "notification": {
            "daily_summary": True,
            "anomaly_alerts": True,
            "quiet_hours": {"start": "22:00", "end": "06:00"},
        },
    }
    if preferences_override:
        prefs = {**prefs, **preferences_override}
    if auth_ctx.is_bootstrap or service is None:
        return HTTPStatus.OK, {
            "id": auth_ctx.account_id,
            "email": auth_ctx.email or "bootstrap@codi",
            "name": "Bootstrap",
            "title": "",
            "role": auth_ctx.role_slug,
            "scopes": list(auth_ctx.scopes),
            "preferences": prefs,
        }
    account = service._db.get_account_by_id(auth_ctx.account_id)  # noqa: SLF001
    if account is None:
        raise AuthServiceError("not_found", "Akun tidak ditemukan.", http_status=404)
    return HTTPStatus.OK, {
        **_account_to_dict(account),
        "scopes": list(auth_ctx.scopes),
        "preferences": prefs,
        "session": {
            "last_login_at": account.last_login_at.isoformat() if account.last_login_at else None,
        },
    }


# ── Account CRUD ────────────────────────────────────────────────────
def _accounts_list(service: AuthService | None) -> JsonResult:
    service = _ensure_service(service)
    accounts = service.list_accounts()
    return HTTPStatus.OK, {
        "accounts": [_account_to_dict(a) for a in accounts],
    }


def _accounts_create(body: dict[str, Any] | None, service: AuthService | None) -> JsonResult:
    service = _ensure_service(service)
    payload = body or {}
    account = service.create_account(
        email=str(payload.get("email") or ""),
        password=str(payload.get("password") or ""),
        name=str(payload.get("name") or ""),
        title=str(payload.get("title") or ""),
        role_slug=str(payload.get("role") or payload.get("role_slug") or ""),
    )
    return HTTPStatus.CREATED, _account_to_dict(account)


def _accounts_roles(service: AuthService | None) -> JsonResult:
    service = _ensure_service(service)
    roles = service.list_roles()
    return HTTPStatus.OK, {
        "roles": [
            {"slug": r.slug, "name": r.name, "scopes": list(r.scopes)} for r in roles
        ],
    }


def _accounts_update_role(
    account_id: str,
    body: dict[str, Any] | None,
    auth_ctx: AuthContext,
    service: AuthService | None,
) -> JsonResult:
    service = _ensure_service(service)
    role_slug = str((body or {}).get("role") or (body or {}).get("role_slug") or "")
    account = service.update_account_role(
        account_id, role_slug, actor_id=auth_ctx.account_id
    )
    return HTTPStatus.OK, _account_to_dict(account)


def _accounts_update_status(
    account_id: str,
    body: dict[str, Any] | None,
    auth_ctx: AuthContext,
    service: AuthService | None,
) -> JsonResult:
    service = _ensure_service(service)
    status = str((body or {}).get("status") or "")
    account = service.update_account_status(
        account_id, status, actor_id=auth_ctx.account_id
    )
    return HTTPStatus.OK, _account_to_dict(account)


def _accounts_update_profile(
    account_id: str,
    body: dict[str, Any] | None,
    service: AuthService | None,
) -> JsonResult:
    service = _ensure_service(service)
    payload = body or {}
    account = service.update_account_profile(
        account_id,
        name=str(payload['name']) if 'name' in payload else None,
        title=str(payload['title']) if 'title' in payload else None,
        email=str(payload['email']) if 'email' in payload else None,
    )
    return HTTPStatus.OK, _account_to_dict(account)


def _accounts_reset_password(
    account_id: str,
    body: dict[str, Any] | None,
    service: AuthService | None,
) -> JsonResult:
    service = _ensure_service(service)
    new_password = str((body or {}).get("password") or "")
    service.reset_password(account_id, new_password)
    return HTTPStatus.OK, {"ok": True}


def _accounts_delete(
    account_id: str,
    auth_ctx: AuthContext,
    service: AuthService | None,
) -> JsonResult:
    service = _ensure_service(service)
    service.delete_account(account_id, actor_id=auth_ctx.account_id)
    return HTTPStatus.NO_CONTENT, {}


def _accounts_devices(account_id: str, service: AuthService | None) -> JsonResult:
    service = _ensure_service(service)
    bindings = service.list_devices(account_id)
    return HTTPStatus.OK, {
        "devices": [
            {
                "id": b.id,
                "device_id": b.device_id,
                "platform": b.platform,
                "enrolled_at": b.enrolled_at.isoformat(),
                "revoked_at": b.revoked_at.isoformat() if b.revoked_at else None,
            }
            for b in bindings
        ],
    }


def _accounts_revoke_device(binding_id: str, service: AuthService | None) -> JsonResult:
    service = _ensure_service(service)
    service.revoke_device(binding_id)
    return HTTPStatus.OK, {"ok": True}


# ── Dashboard ───────────────────────────────────────────────────────
def _dashboard_summary(period: str) -> JsonResult:
    """Live NestJS metrics → kontrak app; fallback ke fixture bila tak terjangkau."""
    try:
        return HTTPStatus.OK, mobile_metrics.dashboard_summary(period)
    except Exception as exc:  # noqa: BLE001 — degrade gracefully to fixture
        logger.warning("Lumbung metrics summary unavailable, serving fixture: %s", exc)
        return _fixture_dashboard_summary(period)


def _fixture_dashboard_summary(period: str) -> JsonResult:
    return HTTPStatus.OK, {
        "period": period,
        "period_label": "Mei 2026",
        "period_range": {"start": "2026-05-01", "end": "2026-05-17"},
        "is_partial": True,
        "days_elapsed": 17,
        "days_in_period": 31,
        "updated_at": "2026-05-17T09:28:00+07:00",
        "revenue": {
            "total": 828882000,
            "currency": "IDR",
            "growth_mom_pct": 321.0,
            "projection_full_period": 1510000000,
            "sparkline": [
                {"date": "2026-05-11", "value": 35000000},
                {"date": "2026-05-12", "value": 58000000},
                {"date": "2026-05-13", "value": 33000000},
                {"date": "2026-05-14", "value": 70000000},
                {"date": "2026-05-15", "value": 82000000},
                {"date": "2026-05-16", "value": 66000000},
                {"date": "2026-05-17", "value": 93000000},
            ],
            "breakdown": {
                "retail": {"value": 656115000, "orders": 15, "weight_gram": 240.6},
                "rotasi": {"value": 172767000, "orders": 40, "weight_gram": 63.5},
            },
        },
        "quick_stats": {
            "orders_total": 55,
            "orders_retail": 15,
            "orders_rotasi": 40,
            "conversion_rate_pct": 68.8,
            "conversion_rate_delta_pct": -31.2,
            "expense_total": 10857500,
            "expense_pct_of_revenue": 1.3,
        },
        "ai_summary": {
            "id": "summary_2026051709",
            "generated_at": "2026-05-17T09:14:00+07:00",
            "model": "claude-sonnet-4-6",
            "tone": "executive_formal",
            "status": "healthy",
            "paragraphs": [
                {
                    "type": "positive",
                    "text": (
                        "Operasional kantor berada dalam kondisi sehat. Omzet "
                        "Mei sudah melampaui April dengan pertumbuhan signifikan, "
                        "didorong kembalinya penjualan emas retail (Rp 656 jt "
                        "dari 15 order)."
                    ),
                },
                {
                    "type": "warning",
                    "text": (
                        "Yang memerlukan perhatian: conversion rate turun ke "
                        "68,8% — terdapat Rp 127 jt potensi pendapatan dari 24 "
                        "order yang expired."
                    ),
                },
                {
                    "type": "note",
                    "text": (
                        "Beban komisi tetap rendah di 1,3% dari omzet — rasio "
                        "yang sangat sehat."
                    ),
                },
            ],
            "data_points_count": 12,
            "sources": ["payment_orders", "user_levels", "finance_ledger"],
        },
        "highlights": [
            {
                "id": "hl_001",
                "severity": "green",
                "title": "Penjualan emas retail kembali aktif",
                "description": (
                    "Rp 656 jt dari 15 order (240,6g) — bulan April nol "
                    "penjualan retail."
                ),
                "timestamp": "2026-05-14T14:30:00+07:00",
                "category": "revenue",
            },
            {
                "id": "hl_002",
                "severity": "red",
                "title": "24 order expired bulan ini",
                "description": (
                    "Total nilai Rp 127 jt tidak terbayar — conversion rate "
                    "turun dari 100% ke 68,8%."
                ),
                "timestamp": "2026-05-17T09:20:00+07:00",
                "category": "conversion",
            },
            {
                "id": "hl_003",
                "severity": "info",
                "title": "Payroll Mei sudah ter-generate",
                "description": (
                    "22 karyawan · total Rp 159 jt · sedang menunggu finalisasi "
                    "oleh HRGA."
                ),
                "timestamp": "2026-05-15T16:45:00+07:00",
                "category": "hr",
            },
        ],
        "chart_daily": {
            "label": "Tren Omzet 7 Hari Terakhir",
            "subtitle": "Penjualan emas vs Rotasi",
            "data": [
                {"date": "2026-05-11", "label": "11", "retail": 32000000, "rotasi": 18000000},
                {"date": "2026-05-12", "label": "12", "retail": 58000000, "rotasi": 30000000},
                {"date": "2026-05-13", "label": "13", "retail": 33000000, "rotasi": 26000000},
                {"date": "2026-05-14", "label": "14", "retail": 70000000, "rotasi": 33000000},
                {"date": "2026-05-15", "label": "15", "retail": 82000000, "rotasi": 38000000},
                {"date": "2026-05-16", "label": "16", "retail": 66000000, "rotasi": 28000000},
                {"date": "2026-05-17", "label": "17", "retail": 93000000, "rotasi": 36000000},
            ],
        },
    }


def _dashboard_insight(period: str) -> JsonResult:
    """Live NestJS metrics → kontrak app; fallback ke fixture bila tak terjangkau."""
    try:
        return HTTPStatus.OK, mobile_metrics.dashboard_insight(period)
    except Exception as exc:  # noqa: BLE001 — degrade gracefully to fixture
        logger.warning("Lumbung metrics insight unavailable, serving fixture: %s", exc)
        return _fixture_dashboard_insight(period)


def _fixture_dashboard_insight(period: str) -> JsonResult:
    return HTTPStatus.OK, {
        "period": period,
        "period_label": "1 – 17 Mei 2026",
        "updated_at": "2026-05-17T09:28:00+07:00",
        "kpis": [
            {
                "key": "revenue_total",
                "label": "Omzet Total",
                "value": 828882000,
                "unit": "IDR",
                "delta_pct": 321.0,
                "delta_label": "+321% MoM",
                "trend": "up",
            },
            {
                "key": "orders_settled",
                "label": "Order Settled",
                "value": 55,
                "unit": "tx",
                "delta_label": "15 retail · 40 rotasi",
                "trend": "up",
            },
            {
                "key": "avg_ticket",
                "label": "Avg. Ticket",
                "value": 15070000,
                "unit": "IDR",
                "delta_pct": 21.8,
                "delta_label": "+21,8%",
                "trend": "up",
            },
            {
                "key": "potential_lost",
                "label": "Potensi Hilang",
                "value": 127151000,
                "unit": "IDR",
                "delta_label": "24 order expired",
                "trend": "down",
            },
        ],
        "composition": {
            "label": "Komposisi Omzet",
            "total": 828882000,
            "segments": [
                {"label": "Penjualan Emas", "value": 656115000, "pct": 79.2, "color": "gold"},
                {"label": "Rotasi Masuk", "value": 172767000, "pct": 20.8, "color": "navy"},
            ],
        },
        "ai_analysis": {
            "id": "analysis_2026051709",
            "generated_at": "2026-05-17T09:14:00+07:00",
            "sections": [
                {
                    "type": "healthy",
                    "title": "Yang Sehat",
                    "content": (
                        "Omzet Mei naik tajam ke Rp 828,8 jt, melampaui April "
                        "berkat kembalinya penjualan emas retail."
                    ),
                },
                {
                    "type": "attention",
                    "title": "Yang Perlu Perhatian",
                    "content": (
                        "Conversion rate turun dari 100% di April ke 68,8% — "
                        "24 order expired senilai Rp 127 jt."
                    ),
                },
                {
                    "type": "note",
                    "title": "Catatan",
                    "content": (
                        "Data sistem baru sejak April 2026, perbandingan "
                        "historis masih terbatas."
                    ),
                },
            ],
            "metadata": {"data_points": 12, "sources_count": 4, "confidence": "high"},
        },
    }


# ── Chat ────────────────────────────────────────────────────────────
import html as _html  # noqa: E402 — keep imports inline near use
import re as _re  # noqa: E402
import time as _time  # noqa: E402

_STUB_REPLY = (
    "Mohon maaf Bapak, kemampuan analisis real-time masih dalam "
    "pengembangan. Integrasi data Codi akan segera tersedia."
)

# Strip tag Telegram HTML (kontrak Telegram bot): <b>, <i>, <u>, <s>,
# <code>, <pre>, <a>, <tg-spoiler>. Tag lain juga di-strip generik.
_HTML_TAG = _re.compile(r"<\s*/?\s*([a-zA-Z][a-zA-Z0-9-]*)\s*[^>]*>")
_HTML_LINK = _re.compile(
    r"<\s*a\s+[^>]*>(.*?)<\s*/\s*a\s*>", _re.IGNORECASE | _re.DOTALL
)
_MULTI_NEWLINE = _re.compile(r"\n{3,}")
# Markdown inline: **bold**, *italic*, __bold__, _italic_, `code`, ~~strike~~.
_MD_BOLD = _re.compile(r"\*\*([^*\n]+?)\*\*")
_MD_BOLD_UNDER = _re.compile(r"__([^_\n]+?)__")
_MD_ITALIC = _re.compile(r"(?<![*\w])\*([^*\n]+?)\*(?!\w)")
_MD_ITALIC_UNDER = _re.compile(r"(?<![_\w])_([^_\n]+?)_(?!\w)")
_MD_CODE_INLINE = _re.compile(r"`([^`\n]+?)`")
_MD_STRIKE = _re.compile(r"~~([^~\n]+?)~~")
# Block: triple-backtick code fence, link [label](href).
_MD_CODE_FENCE = _re.compile(
    r"```[a-zA-Z0-9_+-]*\n?([\s\S]*?)```", _re.MULTILINE
)
_MD_LINK = _re.compile(r"\[([^\]]+)\]\([^)]+\)")
# Heading lines: "## Heading" → "Heading".
_MD_HEADING = _re.compile(r"^\s{0,3}#{1,6}\s+", _re.MULTILINE)


def _clean_chat_text(raw: str) -> str:
    """Hilangkan HTML tag Telegram + markdown inline, decode entity,
    normalize whitespace.

    Output plain text rapi untuk mobile (bubble render Text plain, tak parse
    HTML/markdown). `<b>X</b>` dan `**X**` jadi `X`.
    """
    if not raw:
        return raw
    # 1. HTML cleanup.
    s = _HTML_LINK.sub(r"\1", raw)
    s = _HTML_TAG.sub("", s)
    s = _html.unescape(s)
    # 2. Markdown cleanup (drop markup, pertahankan content).
    s = _MD_CODE_FENCE.sub(r"\1", s)
    s = _MD_LINK.sub(r"\1", s)
    s = _MD_BOLD.sub(r"\1", s)
    s = _MD_BOLD_UNDER.sub(r"\1", s)
    s = _MD_ITALIC.sub(r"\1", s)
    s = _MD_ITALIC_UNDER.sub(r"\1", s)
    s = _MD_CODE_INLINE.sub(r"\1", s)
    s = _MD_STRIKE.sub(r"\1", s)
    s = _MD_HEADING.sub("", s)
    # 3. Whitespace normalize.
    s = _MULTI_NEWLINE.sub("\n\n", s)
    s = "\n".join(line.rstrip() for line in s.splitlines())
    return s.strip()

_DEFAULT_SUGGESTIONS = [
    "Perbandingan dengan April",
    "Proyeksi akhir bulan",
    "Status karyawan",
]


def _chat_messages(
    body: dict[str, Any] | None, chat_fn: ChatFn | None
) -> JsonResult:
    payload = body or {}
    message = str(payload.get("message") or "").strip()
    conversation_id = str(payload.get("conversation_id") or "") or "conv_001"
    if not message:
        return HTTPStatus.BAD_REQUEST, _error(
            "invalid_payload", "message wajib diisi."
        )

    reply_text = _STUB_REPLY
    response_ms = 0
    model = "stub"
    if chat_fn is not None:
        start = _time.monotonic()
        try:
            raw = chat_fn(message, 0, "advisor") or _STUB_REPLY
            reply_text = _clean_chat_text(raw)
            model = "claude-sonnet-4-6"
        except Exception as exc:  # noqa: BLE001
            logger.exception("chat_fn error: %s", exc)
            reply_text = (
                "Maaf, terjadi kesalahan saat memproses pesan. "
                "Silakan coba lagi sebentar lagi."
            )
        response_ms = int((_time.monotonic() - start) * 1000)

    return HTTPStatus.OK, {
        "conversation_id": conversation_id,
        "message_id": f"msg_{int(_time.time() * 1000)}",
        "role": "assistant",
        "content": {"type": "text", "text": reply_text},
        "suggestions": _DEFAULT_SUGGESTIONS,
        "metadata": {
            "response_time_ms": response_ms,
            "model": model,
            "tokens_used": 0,
        },
    }


def _chat_conversations() -> JsonResult:
    return HTTPStatus.OK, {
        "conversations": [
            {
                "id": "conv_001",
                "title": "Kondisi operasional bulan Mei",
                "last_message_at": "2026-05-17T09:44:00+07:00",
                "message_count": 4,
                "preview": "Tiga hal yang sebaiknya Bapak ketahui...",
            },
        ],
        "next_cursor": None,
    }


def _chat_conversation_messages(conversation_id: str) -> JsonResult:
    return HTTPStatus.OK, {
        "conversation_id": conversation_id,
        "messages": [
            {
                "id": "msg_001",
                "role": "user",
                "content": {
                    "type": "text",
                    "text": "Bagaimana kondisi operasional hari ini, Codi?",
                },
                "timestamp": "2026-05-17T09:42:00+07:00",
            },
            {
                "id": "msg_002",
                "role": "assistant",
                "content": {
                    "type": "rich",
                    "text": (
                        "Selamat pagi Bapak Leo. Berikut ringkasan kondisi "
                        "kantor hari ini:"
                    ),
                    "card": {
                        "title": "Status Mei 2026",
                        "badge": {"label": "SEHAT", "color": "green"},
                        "rows": [
                            {"label": "Omzet", "value": "Rp 828,8 jt", "trend": "up"},
                            {"label": "Pertumbuhan MoM", "value": "+321%", "trend": "up"},
                            {"label": "Conv. Rate", "value": "68,8%", "trend": "down"},
                            {"label": "Beban Komisi", "value": "1,3% omzet"},
                        ],
                        "inline_chart": {
                            "type": "sparkline",
                            "data": [12, 15, 10, 22, 30, 36, 42, 50],
                        },
                        "actions": [
                            {"label": "Lihat Ringkasan", "deep_link": "/insight?period=month"},
                            {"label": "Export PDF", "action": "export_pdf"},
                        ],
                    },
                },
                "timestamp": "2026-05-17T09:42:01+07:00",
            },
        ],
    }
