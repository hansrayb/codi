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

import asyncio
import logging
import os
from datetime import date, datetime, timedelta, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable

from core import mobile_metrics
from core.auth.models import AuthContext
from core.auth.rbac import AuthError, require_scope
from core.auth.service import AuthService, AuthServiceError
from core.hr_client import HRClient, HRClientError
from core.lumbung_metrics_client import LumbungMetricsError

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
    session_manager: Any = None,
    chat_history: Any = None,
) -> JsonResult:
    """Dispatch satu request mobile.

    `path` sudah tanpa prefix `/api/v1` dan tanpa query string.
    `auth_ctx` = hasil verifikasi token (None untuk login/refresh).
    `auth_service` = service auth; bila None, endpoint auth/accounts gagal.
    `chat_fn` = sync chat callable (msg, user_id, scope) -> reply text.
                Bila None, `/chat/messages` return stub fallback.
    `session_manager` = SessionManager (read-only) untuk `/me/sessions`.
                Bila None, endpoint return empty snapshot.
    `chat_history` = ChatHistoryStore untuk persist `/chat/*`. Bila None,
                endpoint conversations return list kosong, POST tetap balas
                tanpa simpan.
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
            session_manager=session_manager,
            chat_history=chat_history,
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
    session_manager: Any = None,
    chat_history: Any = None,
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
    if method == "GET" and path == "/me/sessions":
        return _me_sessions(session_manager)
    if method == "GET" and path == "/dashboard/summary":
        require_scope(auth_ctx, "dashboard:read")
        return _dashboard_summary(query.get("period", "month"))
    if method == "GET" and path == "/dashboard/insight":
        require_scope(auth_ctx, "insight:read")
        return _dashboard_insight(query.get("period", "month"))
    if method == "GET" and path == "/reports":
        require_scope(auth_ctx, "reports:read")
        return _reports(query.get("period", "all"))
    if method == "GET" and path == "/reports/detail":
        require_scope(auth_ctx, "reports:read")
        return _reports_detail(query.get("ref", ""))
    if method == "POST" and path == "/chat/messages":
        require_scope(auth_ctx, "chat:use")
        return _chat_messages(body, chat_fn, auth_ctx=auth_ctx, chat_history=chat_history)
    if method == "GET" and path == "/chat/conversations":
        require_scope(auth_ctx, "chat:use")
        return _chat_conversations(auth_ctx=auth_ctx, chat_history=chat_history)
    if (
        method == "GET"
        and path.startswith("/chat/conversations/")
        and path.endswith("/messages")
    ):
        require_scope(auth_ctx, "chat:use")
        conv_id = path[len("/chat/conversations/") : -len("/messages")]
        return _chat_conversation_messages(
            conv_id, auth_ctx=auth_ctx, chat_history=chat_history,
        )

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


def _me_sessions(session_manager: Any) -> JsonResult:
    """Snapshot sesi Codi aktif (read-only). Bot-wide, bukan per-user.

    Source: `SessionManager.list_sessions_snapshot()` (sync). Mapping ke
    kontrak app: id, role, repo, repo_name, started_at, last_activity_at,
    idle_seconds. Field tambahan (status, case_id, owner_user_id,
    message_count) untuk diagnosis — frontend abaikan yang tak dikenal.
    """
    if session_manager is None:
        return HTTPStatus.OK, {"active": 0, "sessions": []}
    try:
        raw_sessions = session_manager.list_sessions_snapshot()
    except Exception as exc:  # noqa: BLE001 — degrade gracefully
        logger.warning("session_manager.list_sessions_snapshot failed: %s", exc)
        return HTTPStatus.OK, {"active": 0, "sessions": []}
    now = datetime.now(timezone.utc)
    items: list[dict[str, Any]] = []
    for s in raw_sessions:
        try:
            started = getattr(s, "created_at", None)
            last_act = getattr(s, "last_activity_at", None)
            repo = str(getattr(s, "cwd", "") or "")
            repo_name = Path(repo).name if repo else ""
            idle_seconds: int | None = None
            if isinstance(last_act, datetime):
                idle_seconds = max(0, int((now - last_act).total_seconds()))
            items.append({
                "id": str(getattr(s, "session_id", "") or ""),
                "role": str(getattr(s, "role", "") or ""),
                "repo": repo,
                "repo_name": repo_name,
                "started_at": started.isoformat() if isinstance(started, datetime) else None,
                "last_activity_at": (
                    last_act.isoformat() if isinstance(last_act, datetime) else None
                ),
                "idle_seconds": idle_seconds,
                "status": str(getattr(s, "status", "") or ""),
                "case_id": getattr(s, "case_id", None),
                "user_id": getattr(s, "owner_user_id", None),
                "message_count": int(getattr(s, "message_count", 0) or 0),
            })
        except Exception as exc:  # noqa: BLE001
            logger.warning("session shape unexpected: %s", exc)
    # Sort: most recently active first.
    items.sort(
        key=lambda it: it.get("last_activity_at") or "",
        reverse=True,
    )
    return HTTPStatus.OK, {"active": len(items), "sessions": items}


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


_JKT = timezone(timedelta(hours=7))
_MONTHS_ID = [
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]
# Cap how many payroll runs we pre-fetch items for (avoid runaway parallel
# load if HR ever returns hundreds of historical runs).
_MAX_PAYROLL_RUNS = 24


def _build_hr_client() -> HRClient | None:
    base = (os.getenv("HR_API_URL") or "").strip()
    email = (os.getenv("HR_SERVICE_EMAIL") or "").strip()
    password = (os.getenv("HR_SERVICE_PASSWORD") or "").strip()
    enabled = (os.getenv("HR_ENABLED", "false") or "").strip().lower() in (
        "1", "true", "yes", "on",
    )
    if not enabled or not base or not email or not password:
        return None
    return HRClient(base, email, password)


def _month_label_id(year: int, month: int) -> str:
    if 1 <= month <= 12:
        return f"{_MONTHS_ID[month]} {year}"
    return f"{year}-{month:02d}"


def _rp(amount: float | int) -> str:
    return "Rp " + f"{int(amount):,}".replace(",", ".")


def _period_cutoff(period: str, now: datetime) -> date | None:
    """Earliest date to include for ``period``; None for ``all``."""
    if period == "month":
        return now.replace(day=1).date()
    if period == "quarter":
        y, m = now.year, now.month - 2
        while m <= 0:
            m += 12
            y -= 1
        return date(y, m, 1)
    if period == "year":
        return now.replace(month=1, day=1).date()
    return None


def _classify_group(created_at: str, now: datetime) -> str:
    try:
        d = date.fromisoformat(created_at[:10])
    except (ValueError, IndexError):
        return "Lebih Lama"
    if d.year == now.year and d.month == now.month:
        return "Terbaru"
    prev_m, prev_y = (now.month - 1, now.year) if now.month > 1 else (12, now.year - 1)
    if d.year == prev_y and d.month == prev_m:
        return "Bulan Lalu"
    return "Lebih Lama"


async def _gather_payroll(
    hr: HRClient, items_out: list[dict[str, Any]], now: datetime, period: str
) -> int:
    """Append payroll items to ``items_out``, return total net_pay for current month."""
    payroll_current_month = 0
    try:
        runs = await hr.get_payroll_runs()
    except HRClientError as exc:
        logger.warning("hr_get_payroll_runs failed: %s", exc)
        return 0
    if not isinstance(runs, list):
        return 0
    cutoff = _period_cutoff(period, now)

    async def _fetch(run: dict) -> tuple[dict, list]:
        try:
            return run, await hr.get_payroll_items(int(run["id"]))
        except (HRClientError, KeyError, ValueError) as exc:
            logger.warning("hr_get_payroll_items run_id=%s failed: %s", run.get("id"), exc)
            return run, []

    fetched = await asyncio.gather(*[_fetch(r) for r in runs[:_MAX_PAYROLL_RUNS]])
    for run, run_items in fetched:
        try:
            total = sum(float(it.get("net_pay") or 0) for it in run_items)
            n_emp = len(run_items)
            year = int(run.get("year") or 0)
            month = int(run.get("month") or 0)
            period_start = str(run.get("period_start") or "")[:10]
            period_end = str(run.get("period_end") or "")[:10]
            created_at = period_start or str(run.get("created_at") or "")[:10]
            status = "finalized" if str(run.get("status")) == "finalized" else "draft"
            # Aggregate payroll_insight BEFORE cutoff — the run for the current
            # period (e.g. Run 6 / May) may have period_start in the prior month
            # and get filtered from the list, but it's still the relevant total.
            if year == now.year and month == now.month:
                payroll_current_month += int(total)
            if cutoff and created_at:
                try:
                    if date.fromisoformat(created_at) < cutoff:
                        continue
                except ValueError:
                    pass
            items_out.append({
                "title": f"Payroll {_month_label_id(year, month)}",
                "category": "payroll",
                "status": status,
                "created_at": created_at,
                "meta": (
                    f"{period_start} → {period_end} · {n_emp} karyawan · {_rp(total)}"
                ),
                "detail_ref": f"payroll:{int(run['id'])}",
            })
        except (TypeError, ValueError) as exc:
            logger.warning("payroll run shape unexpected: %s", exc)
    return payroll_current_month


async def _gather_attendance(
    hr: HRClient, items_out: list[dict[str, Any]], now: datetime, period: str
) -> None:
    """Append per-month attendance recap items."""
    cutoff = _period_cutoff(period, now) or date(now.year - 1, 1, 1)
    from_date = cutoff.isoformat()
    to_date = now.date().isoformat()
    try:
        rows = await hr.get_attendance_summary(from_date, to_date)
    except HRClientError as exc:
        logger.warning("hr_attendance failed: %s", exc)
        return
    if not isinstance(rows, list):
        return
    buckets: dict[tuple[int, int], dict[str, Any]] = {}
    for row in rows:
        d_str = str(row.get("attendance_date") or "")[:10]
        if not d_str:
            continue
        try:
            d = date.fromisoformat(d_str)
        except ValueError:
            continue
        key = (d.year, d.month)
        b = buckets.setdefault(key, {"users": set(), "records": 0, "min": d, "max": d})
        if row.get("user_id") is not None:
            b["users"].add(row["user_id"])
        b["records"] += 1
        if d < b["min"]:
            b["min"] = d
        if d > b["max"]:
            b["max"] = d
    for (year, month), b in sorted(buckets.items(), reverse=True):
        items_out.append({
            "title": f"Rekap Absensi {_month_label_id(year, month)}",
            "category": "absensi",
            "status": "finalized",
            "created_at": b["max"].isoformat(),
            "meta": (
                f"{len(b['users'])} karyawan · {b['records']} record · "
                f"{b['min'].isoformat()} → {b['max'].isoformat()}"
            ),
            "detail_ref": f"absensi:{year:04d}-{month:02d}",
        })


def _gather_omzet(items_out: list[dict[str, Any]], now: datetime) -> int:
    """Append current-month omzet item, return revenue.total (0 if unavailable)."""
    try:
        summary = mobile_metrics.dashboard_summary("month")
    except (LumbungMetricsError, Exception) as exc:  # noqa: BLE001
        logger.warning("lumbung omzet unavailable: %s", exc)
        return 0
    revenue = (summary.get("revenue") or {}) if isinstance(summary, dict) else {}
    total = int(revenue.get("total") or 0)
    rng = summary.get("period_range") or {} if isinstance(summary, dict) else {}
    end_date = str(rng.get("end") or now.date().isoformat())[:10]
    label = summary.get("period_label") if isinstance(summary, dict) else None
    if not label:
        label = _month_label_id(now.year, now.month)
    orders = 0
    if isinstance(summary, dict):
        orders = int((summary.get("quick_stats") or {}).get("orders_total") or 0)
    # Use end_date's month for the detail ref; fall back to current month.
    try:
        ref_date = date.fromisoformat(end_date)
    except ValueError:
        ref_date = now.date()
    items_out.append({
        "title": f"Ringkasan Omzet — {label}",
        "category": "omzet",
        "status": "finalized",
        "created_at": end_date,
        "meta": f"{_rp(total)} · {orders} order",
        "detail_ref": f"omzet:{ref_date.year:04d}-{ref_date.month:02d}",
    })
    return total


def _build_payroll_insight(
    omzet: int, payroll: int, now: datetime
) -> dict[str, Any] | None:
    if omzet <= 0 or payroll <= 0:
        return None
    ratio_pct = round(payroll / omzet * 100, 1)
    if ratio_pct < 35:
        status, advice = (
            "sehat",
            "porsi sehat dan masih jauh dari batas waspada (35%).",
        )
    elif ratio_pct < 50:
        status, advice = (
            "waspada",
            "porsi mendekati batas — pantau ketat margin operasional.",
        )
    else:
        status, advice = (
            "kritis",
            "porsi terlalu besar — review struktur biaya tenaga kerja.",
        )
    label = _month_label_id(now.year, now.month)
    return {
        "period_label": label,
        "omzet": omzet,
        "payroll": payroll,
        "ratio_pct": ratio_pct,
        "status": status,
        "conclusion": (
            f"Payroll {label} mengambil {ratio_pct}% dari omzet — {advice}"
        ),
    }


async def _fetch_real_reports(period: str, now: datetime) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    payroll_current = 0
    hr = _build_hr_client()
    if hr is not None:
        payroll_current = await _gather_payroll(hr, items, now, period)
        await _gather_attendance(hr, items, now, period)
    omzet_total = _gather_omzet(items, now)

    insight = _build_payroll_insight(omzet_total, payroll_current, now)

    buckets: dict[str, list[dict[str, Any]]] = {
        "Terbaru": [], "Bulan Lalu": [], "Lebih Lama": [],
    }
    for it in items:
        buckets[_classify_group(it["created_at"], now)].append(it)
    for k in buckets:
        buckets[k].sort(key=lambda x: x.get("created_at") or "", reverse=True)

    groups: list[dict[str, Any]] = []
    if buckets["Terbaru"]:
        groups.append({"label": "Terbaru", "items": buckets["Terbaru"]})
    if buckets["Bulan Lalu"] and period != "month":
        groups.append({"label": "Bulan Lalu", "items": buckets["Bulan Lalu"]})
    if buckets["Lebih Lama"] and period in ("year", "all"):
        groups.append({"label": "Lebih Lama", "items": buckets["Lebih Lama"]})

    result: dict[str, Any] = {"period": period, "groups": groups}
    if insight is not None:
        result["payroll_insight"] = insight
    return result


def _reports(period: str) -> JsonResult:
    """Real data via HR + Lumbung; fallback ke fixture bila keduanya tak terjangkau."""
    try:
        now = datetime.now(_JKT)
        result = asyncio.run(_fetch_real_reports(period, now))
        if not result.get("groups") and "payroll_insight" not in result:
            logger.warning("reports real path yielded empty result; serving fixture")
            return HTTPStatus.OK, _fixture_reports(period)
        return HTTPStatus.OK, result
    except Exception as exc:  # noqa: BLE001
        logger.warning("reports real path failed: %s — serving fixture", exc)
        return HTTPStatus.OK, _fixture_reports(period)


# ── /reports/detail ────────────────────────────────────────────────────────


def _detail_unavailable(
    ref: str, category: str, title: str, note: str
) -> dict[str, Any]:
    """Build a partial detail response when the underlying source is down."""
    return {
        "ref": ref,
        "category": category,
        "title": title,
        "status": "finalized",
        "summary": [{"label": "Status", "value": note}],
        "rows": [{"label": note, "sub": "", "value": ""}],
    }


def _month_range(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    next_year, next_month = (year, month + 1) if month < 12 else (year + 1, 1)
    end = date(next_year, next_month, 1) - timedelta(days=1)
    return start, end


async def _detail_payroll(ref: str, run_id: int) -> dict[str, Any] | None:
    hr = _build_hr_client()
    if hr is None:
        return _detail_unavailable(
            ref, "payroll", f"Payroll #{run_id}", "HR backend belum dikonfigurasi.",
        )
    try:
        runs = await hr.get_payroll_runs()
    except HRClientError as exc:
        logger.warning("payroll detail get_payroll_runs failed: %s", exc)
        return _detail_unavailable(
            ref, "payroll", f"Payroll #{run_id}", "Data payroll tidak tersedia.",
        )
    run = next((r for r in runs if int(r.get("id") or 0) == run_id), None)
    if run is None:
        return None  # → 404
    try:
        items = await hr.get_payroll_items(run_id)
    except HRClientError as exc:
        logger.warning("payroll detail get_payroll_items failed: %s", exc)
        items = []
    year = int(run.get("year") or 0)
    month = int(run.get("month") or 0)
    period_start = str(run.get("period_start") or "")[:10]
    period_end = str(run.get("period_end") or "")[:10]
    status = "finalized" if str(run.get("status")) == "finalized" else "draft"
    title = f"Payroll {_month_label_id(year, month)}"
    total = sum(float(it.get("net_pay") or 0) for it in items)
    summary = [
        {"label": "Periode", "value": f"{period_start} → {period_end}"},
        {"label": "Karyawan", "value": f"{len(items)} orang"},
        {"label": "Total Net", "value": _rp(total)},
        {"label": "Status", "value": "Finalized" if status == "finalized" else "Draft"},
    ]
    rows = []
    for it in items:
        net = float(it.get("net_pay") or 0)
        rows.append({
            "label": str(it.get("employee_name") or "—"),
            "sub": str(it.get("department_name") or it.get("position_name") or "—"),
            "value": _rp(net),
            # Stable numeric key for sorting; app may ignore.
            "_sort": net,
        })
    rows.sort(key=lambda r: -r.get("_sort", 0))
    for r in rows:
        r.pop("_sort", None)
    if not rows:
        rows = [{"label": "Belum ada item payroll.", "sub": "", "value": ""}]
    return {
        "ref": ref, "category": "payroll", "title": title, "status": status,
        "summary": summary, "rows": rows,
    }


async def _detail_absensi(ref: str, year: int, month: int) -> dict[str, Any] | None:
    if not (1 <= month <= 12):
        return None
    title = f"Rekap Absensi {_month_label_id(year, month)}"
    hr = _build_hr_client()
    if hr is None:
        return _detail_unavailable(
            ref, "absensi", title, "HR backend belum dikonfigurasi.",
        )
    start, end = _month_range(year, month)
    try:
        rows_raw = await hr.get_attendance_summary(start.isoformat(), end.isoformat())
    except HRClientError as exc:
        logger.warning("absensi detail fetch failed: %s", exc)
        return _detail_unavailable(
            ref, "absensi", title, "Data absensi tidak tersedia.",
        )
    if not isinstance(rows_raw, list):
        rows_raw = []
    by_user: dict[Any, dict[str, Any]] = {}
    total_records = 0
    for row in rows_raw:
        uid = row.get("user_id")
        if uid is None:
            continue
        entry = by_user.setdefault(uid, {
            "name": str(row.get("user_name") or "—"),
            "counts": {},
            "records": 0,
        })
        entry["records"] += 1
        total_records += 1
        st = str(row.get("status") or "").upper() or "UNKNOWN"
        entry["counts"][st] = entry["counts"].get(st, 0) + 1
    summary = [
        {"label": "Periode", "value": f"{start.isoformat()} → {end.isoformat()}"},
        {"label": "Karyawan", "value": f"{len(by_user)} orang"},
        {"label": "Total Record", "value": str(total_records)},
    ]
    label_map = (
        ("Hadir", "PRESENT"),
        ("Telat", "LATE"),
        ("Alpa", "ABSENT"),
        ("Izin", "PERMIT"),
        ("Sakit", "SICK"),
    )
    rows: list[dict[str, Any]] = []
    for entry in by_user.values():
        parts = []
        counts = entry["counts"]
        for lab, key in label_map:
            if counts.get(key, 0) > 0:
                parts.append(f"{lab}: {counts[key]}")
        for k, v in counts.items():
            if k not in {key for _, key in label_map} and v > 0:
                parts.append(f"{k.title()}: {v}")
        rows.append({
            "label": entry["name"],
            "sub": " · ".join(parts) if parts else "—",
            "value": f"{entry['records']} hari",
        })
    rows.sort(key=lambda r: r["label"].lower())
    if not rows:
        rows = [{"label": "Belum ada record absensi.", "sub": "", "value": ""}]
    return {
        "ref": ref, "category": "absensi", "title": title, "status": "finalized",
        "summary": summary, "rows": rows,
    }


def _detail_omzet(ref: str, year: int, month: int) -> dict[str, Any] | None:
    if not (1 <= month <= 12):
        return None
    title = f"Ringkasan Omzet {_month_label_id(year, month)}"
    try:
        summary_data = mobile_metrics.dashboard_summary("month")
    except (LumbungMetricsError, Exception) as exc:  # noqa: BLE001
        logger.warning("omzet detail summary fetch failed: %s", exc)
        return _detail_unavailable(
            ref, "omzet", title, "Lumbung metrics tidak tersedia.",
        )
    if not isinstance(summary_data, dict):
        summary_data = {}
    try:
        insight_data = mobile_metrics.dashboard_insight("month")
        if not isinstance(insight_data, dict):
            insight_data = {}
    except (LumbungMetricsError, Exception) as exc:  # noqa: BLE001
        logger.warning("omzet detail insight fetch failed: %s", exc)
        insight_data = {}

    revenue = (summary_data.get("revenue") or {})
    rev_total = int(revenue.get("total") or 0)
    orders = int((summary_data.get("quick_stats") or {}).get("orders_total") or 0)
    period_label = (
        summary_data.get("period_label") or _month_label_id(year, month)
    )
    summary = [
        {"label": "Periode", "value": str(period_label)},
        {"label": "Total Omzet", "value": _rp(rev_total)},
        {"label": "Order", "value": f"{orders} transaksi"},
    ]
    rows: list[dict[str, Any]] = []
    # Composition segments (Penjualan Emas vs Rotasi Masuk).
    composition = insight_data.get("composition") or {}
    for seg in composition.get("segments") or []:
        pct = seg.get("pct")
        sub = f"{pct}% dari total" if pct is not None else ""
        rows.append({
            "label": str(seg.get("label") or "—"),
            "sub": sub,
            "value": _rp(int(seg.get("value") or 0)),
        })
    # KPIs (Omzet, Order, Avg Ticket, Potensi Hilang).
    for kpi in insight_data.get("kpis") or []:
        unit = str(kpi.get("unit") or "")
        raw_value = kpi.get("value")
        if unit == "IDR":
            value = _rp(int(raw_value or 0))
        elif unit:
            value = f"{raw_value} {unit}".strip()
        else:
            value = str(raw_value if raw_value is not None else "—")
        rows.append({
            "label": str(kpi.get("label") or ""),
            "sub": str(kpi.get("delta_label") or ""),
            "value": value,
        })
    if not rows:
        rows = [{"label": "Belum ada breakdown omzet.", "sub": "", "value": ""}]
    return {
        "ref": ref, "category": "omzet", "title": title, "status": "finalized",
        "summary": summary, "rows": rows,
    }


async def _fetch_reports_detail(ref: str) -> dict[str, Any] | None:
    """Return detail dict, or None if ref is invalid/unknown (caller → 404)."""
    if not ref or ":" not in ref:
        return None
    category, _, key = ref.partition(":")
    category = category.strip().lower()
    key = key.strip()

    if category == "payroll":
        try:
            run_id = int(key)
        except ValueError:
            return None
        return await _detail_payroll(ref, run_id)

    if category in ("absensi", "omzet"):
        try:
            y_str, m_str = key.split("-", 1)
            year = int(y_str)
            month = int(m_str)
        except ValueError:
            return None
        if category == "absensi":
            return await _detail_absensi(ref, year, month)
        return _detail_omzet(ref, year, month)

    return None


def _reports_detail(ref: str) -> JsonResult:
    try:
        result = asyncio.run(_fetch_reports_detail(ref))
    except Exception as exc:  # noqa: BLE001
        logger.warning("reports/detail failed: %s", exc)
        return HTTPStatus.INTERNAL_SERVER_ERROR, _error("internal", "Server error.")
    if result is None:
        return HTTPStatus.NOT_FOUND, _error(
            "not_found", "Detail laporan tidak ditemukan.",
        )
    return HTTPStatus.OK, result


def _fixture_reports(period: str) -> dict[str, Any]:
    terbaru = {
        "label": "Terbaru",
        "items": [
            {
                "title": "Ringkasan Omzet — Mei 2026",
                "category": "omzet",
                "status": "finalized",
                "created_at": "2026-05-17",
                "meta": "17 Mei 2026 · 4 hal",
            },
            {
                "title": "Payroll Run — Mei 2026",
                "category": "payroll",
                "status": "draft",
                "created_at": "2026-05-15",
                "meta": "15 Mei 2026 · 22 karyawan · Rp 159 jt",
            },
            {
                "title": "Rekap Absensi — Mei 2026",
                "category": "absensi",
                "status": "finalized",
                "created_at": "2026-05-14",
                "meta": "14 Mei 2026 · 22 karyawan",
            },
        ],
    }
    bulan_lalu = {
        "label": "Bulan Lalu",
        "items": [
            {
                "title": "Ringkasan Omzet — April 2026",
                "category": "omzet",
                "status": "finalized",
                "created_at": "2026-04-30",
                "meta": "30 Apr 2026 · 3 hal",
            },
            {
                "title": "Payroll Run — April 2026",
                "category": "payroll",
                "status": "finalized",
                "created_at": "2026-04-16",
                "meta": "16 Apr 2026 · 22 karyawan · Rp 154 jt",
            },
        ],
    }
    groups = [terbaru] if period == "month" else [terbaru, bulan_lalu]
    return {"period": period, "groups": groups}


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
    """Hilangkan HTML tag Telegram, decode entity, normalize whitespace.

    Markdown DIPERTAHANKAN — mobile render via flutter_markdown (bold,
    heading, table jadi visual). HTML cuma artefak format Telegram, perlu
    di-strip karena mobile tak render HTML.
    """
    if not raw:
        return raw
    s = _HTML_LINK.sub(r"\1", raw)
    s = _HTML_TAG.sub("", s)
    s = _html.unescape(s)
    s = _MULTI_NEWLINE.sub("\n\n", s)
    s = "\n".join(line.rstrip() for line in s.splitlines())
    return s.strip()

_DEFAULT_SUGGESTIONS = [
    "Perbandingan dengan April",
    "Proyeksi akhir bulan",
    "Status karyawan",
]


def _chat_messages(
    body: dict[str, Any] | None,
    chat_fn: ChatFn | None,
    *,
    auth_ctx: AuthContext | None = None,
    chat_history: Any = None,
) -> JsonResult:
    payload = body or {}
    message = str(payload.get("message") or "").strip()
    requested_conv_id = str(payload.get("conversation_id") or "").strip() or None
    if not message:
        return HTTPStatus.BAD_REQUEST, _error(
            "invalid_payload", "message wajib diisi."
        )

    account_id = str(getattr(auth_ctx, "account_id", "") or "")

    conversation_id: str | None = None
    if chat_history is not None and account_id:
        try:
            conversation_id = chat_history.ensure_conversation(
                account_id=account_id,
                conversation_id=requested_conv_id,
                seed_title_text=message,
            )
            chat_history.append_message(
                conversation_id=conversation_id, role="user", text=message,
            )
        except Exception as exc:  # noqa: BLE001 — persist best-effort
            logger.warning("chat_history persist user failed: %s", exc)
            conversation_id = None

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

    assistant_msg_id = f"msg_{int(_time.time() * 1000)}"
    if (
        chat_history is not None
        and account_id
        and conversation_id is not None
    ):
        try:
            persisted = chat_history.append_message(
                conversation_id=conversation_id,
                role="assistant",
                text=reply_text,
            )
            assistant_msg_id = persisted.get("id") or assistant_msg_id
        except Exception as exc:  # noqa: BLE001
            logger.warning("chat_history persist assistant failed: %s", exc)

    response: dict[str, Any] = {
        "conversation_id": conversation_id or requested_conv_id or "conv_001",
        "message_id": assistant_msg_id,
        "role": "assistant",
        "content": {"type": "text", "text": reply_text},
        "suggestions": _DEFAULT_SUGGESTIONS,
        "metadata": {
            "response_time_ms": response_ms,
            "model": model,
            "tokens_used": 0,
        },
    }
    return HTTPStatus.OK, response


def _chat_conversations(
    *,
    auth_ctx: AuthContext | None = None,
    chat_history: Any = None,
) -> JsonResult:
    account_id = str(getattr(auth_ctx, "account_id", "") or "")
    if chat_history is None or not account_id:
        return HTTPStatus.OK, {"conversations": [], "next_cursor": None}
    try:
        items = chat_history.list_conversations(account_id=account_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("chat_history list failed: %s", exc)
        return HTTPStatus.OK, {"conversations": [], "next_cursor": None}
    return HTTPStatus.OK, {"conversations": items, "next_cursor": None}


def _chat_conversation_messages(
    conversation_id: str,
    *,
    auth_ctx: AuthContext | None = None,
    chat_history: Any = None,
) -> JsonResult:
    account_id = str(getattr(auth_ctx, "account_id", "") or "")
    if chat_history is None or not account_id or not conversation_id:
        return HTTPStatus.NOT_FOUND, _error(
            "not_found", "Percakapan tidak ditemukan.",
        )
    try:
        messages = chat_history.get_messages(
            conversation_id=conversation_id, account_id=account_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("chat_history get_messages failed: %s", exc)
        return HTTPStatus.NOT_FOUND, _error(
            "not_found", "Percakapan tidak ditemukan.",
        )
    if messages is None:
        return HTTPStatus.NOT_FOUND, _error(
            "not_found", "Percakapan tidak ditemukan.",
        )
    return HTTPStatus.OK, {
        "conversation_id": conversation_id,
        "messages": messages,
    }
