"""Mobile API (`/api/v1/*`) untuk app Emas Berlian Insight.

Fase A1 — **stub/fixture**. Endpoint mengembalikan JSON ber-bentuk sesuai
`app/docs/04-API-CONTRACT.md` agar Flutter bisa integrasi HTTP nyata
(Fase B), walau data masih dummy. Fase A2 nanti ganti fixture dengan
agregasi business DB asli.

Handler murni (tanpa ketergantungan internal server) — di-dispatch dari
`core/device_api.py`. Auth via shared-token (Bearer) ditangani server.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

# Token akses stub — pada A1 sama dengan DEVICE_API_SHARED_TOKEN. Flutter
# kirim balik sebagai `Authorization: Bearer <token>` (divalidasi server).
_STUB_USER = {
    "id": "user_leo_001",
    "name": "Leo Sastra C.W.",
    "title": "Direktur Utama",
    "initials": "LS",
    "role": "director",
}

JsonResult = tuple[HTTPStatus, dict[str, Any]]


def mobile_handle(
    method: str,
    path: str,
    query: dict[str, str],
    body: dict[str, Any] | None,
    *,
    access_token: str,
) -> JsonResult:
    """Dispatch satu request mobile.

    `path` sudah tanpa prefix `/api/v1` dan tanpa query string.
    `access_token` = token yang server pakai untuk auth (dikembalikan
    di login agar request berikutnya lolos `_is_authorized`).
    """
    if method == "POST" and path == "/auth/login":
        return _auth_login(body, access_token=access_token)
    if method == "POST" and path == "/auth/refresh":
        return _auth_refresh(access_token=access_token)
    if method == "POST" and path == "/auth/logout":
        return HTTPStatus.OK, {"ok": True}
    if method == "GET" and path == "/me":
        return _me()
    if method == "PATCH" and path == "/me/preferences":
        return _me(preferences_override=body)
    if method == "GET" and path == "/dashboard/summary":
        return _dashboard_summary(query.get("period", "month"))
    if method == "GET" and path == "/dashboard/insight":
        return _dashboard_insight(query.get("period", "month"))
    if method == "POST" and path == "/chat/messages":
        return _chat_messages(body)
    if method == "GET" and path == "/chat/conversations":
        return _chat_conversations()
    if (
        method == "GET"
        and path.startswith("/chat/conversations/")
        and path.endswith("/messages")
    ):
        conv_id = path[len("/chat/conversations/") : -len("/messages")]
        return _chat_conversation_messages(conv_id)

    return HTTPStatus.NOT_FOUND, {
        "error": {"code": "not_found", "message": "Endpoint tidak ditemukan."},
    }


# ── Auth ────────────────────────────────────────────────────────────
def _auth_login(body: dict[str, Any] | None, *, access_token: str) -> JsonResult:
    return HTTPStatus.OK, {
        "access_token": access_token,
        "refresh_token": access_token,
        "expires_in": 604800,
        "user": _STUB_USER,
    }


def _auth_refresh(*, access_token: str) -> JsonResult:
    return HTTPStatus.OK, {
        "access_token": access_token,
        "refresh_token": access_token,
        "expires_in": 604800,
    }


def _me(preferences_override: dict[str, Any] | None = None) -> JsonResult:
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
    return HTTPStatus.OK, {
        **_STUB_USER,
        "email": "leo@lumbungemas.co.id",
        "preferences": prefs,
        "session": {
            "last_login_at": "2026-05-17T07:30:00+07:00",
            "device": "Android",
        },
    }


# ── Dashboard ───────────────────────────────────────────────────────
def _dashboard_summary(period: str) -> JsonResult:
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
def _chat_messages(body: dict[str, Any] | None) -> JsonResult:
    return HTTPStatus.OK, {
        "conversation_id": (body or {}).get("conversation_id") or "conv_001",
        "message_id": "msg_stub",
        "role": "assistant",
        "content": {
            "type": "text",
            "text": (
                "Mohon maaf Bapak, kemampuan analisis real-time masih dalam "
                "pengembangan. Integrasi data Codi akan segera tersedia."
            ),
        },
        "suggestions": [
            "Perbandingan dengan April",
            "Proyeksi akhir bulan",
            "Status karyawan",
        ],
        "metadata": {
            "response_time_ms": 820,
            "model": "claude-sonnet-4-6",
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
