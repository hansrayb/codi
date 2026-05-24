"""Tests for the NestJS → app-contract reshape (`core/mobile_metrics.py`)."""

import json
import urllib.error
from datetime import datetime
from http import HTTPStatus

from core import lumbung_metrics_client as client_mod
from core import mobile_api, mobile_metrics
from core.lumbung_metrics_client import LumbungMetricsClient, LumbungMetricsError

NOW = datetime(2026, 5, 24, 12, 0, 0, tzinfo=mobile_metrics.JKT)

# ── canned raw NestJS responses ──────────────────────────────────────────────
NEST_DASHBOARD = {
    "period": "month",
    "period_label": "Bulan Ini",
    "period_range": {"start": "2026-04-30T17:00:00.000Z", "end": "2026-05-31T17:00:00.000Z"},
    "is_partial": True,
    "days_elapsed": 24,
    "days_in_period": 31,
    "updated_at": "2026-05-24T05:00:00.000Z",
    "revenue": {
        "total": 1321457105,
        "growth_mom_pct": 268,
        "projection_full_period": 1706882094,
        "sparkline": [
            {"date": "2026-05-23", "value": 42384000},
            {"date": "2026-05-24", "value": 0},
        ],
        "breakdown": {
            "retail": {"value": 880860250, "orders": 88, "weight_gram": 320.8},
            "rotasi": {"value": 230609000, "orders": 43, "weight_gram": 85},
        },
    },
    "quick_stats": {
        "orders_total": 147, "orders_retail": 88, "orders_rotasi": 43,
        "conversion_rate_pct": 99.32, "conversion_rate_delta_pct": -0.68,
        "expense_total": 20616000, "expense_pct_of_revenue": 1.56,
    },
    "chart_daily": {"data": [
        {"date": "2026-05-23", "label": "Sab", "retail": 12762000, "rotasi": 29622000},
        {"date": "2026-05-24", "label": "Min", "retail": 0, "rotasi": 0},
    ]},
    "highlights": [
        {"id": "orders-pending", "severity": "info", "title": "1 order menunggu",
         "description": "x", "timestamp": "2026-05-24T05:00:00.000Z", "category": "orders"},
        {"id": "expense-high", "severity": "warning", "title": "Beban komisi tinggi",
         "description": "y", "timestamp": "2026-05-24T05:00:00.000Z", "category": "expense"},
    ],
}

NEST_INSIGHT = {
    "period": "month",
    "kpis": [
        {"key": "revenue_total", "label": "Total Omzet", "value": 1321457105, "unit": "IDR",
         "delta_pct": 268, "delta_label": "+268% vs bulan lalu", "trend": "up"},
        {"key": "orders_settled", "label": "Order Lunas", "value": 147, "unit": "order",
         "delta_pct": 406.9, "delta_label": "+406.9% vs bulan lalu", "trend": "up"},
        {"key": "avg_ticket", "label": "Rata-rata Transaksi", "value": 8989504, "unit": "IDR",
         "delta_pct": -27.4, "delta_label": "-27.4% vs bulan lalu", "trend": "down"},
        {"key": "potential_lost", "label": "Potensi Omzet Hilang", "value": 2815000, "unit": "IDR",
         "delta_pct": None, "delta_label": "Baru", "trend": "flat"},
    ],
    "composition": {"total": 1111469250, "segments": [
        {"label": "Retail", "value": 880860250, "pct": 79.25, "color": "#2563EB"},
        {"label": "Rotasi", "value": 230609000, "pct": 20.75, "color": "#06B6D4"},
    ]},
    "metadata": {"data_points": 148, "sources_count": 2},
}


# ── reshape: summary ─────────────────────────────────────────────────────────
def test_reshape_summary_matches_contract():
    out = mobile_metrics.reshape_summary(NEST_DASHBOARD, "month", now=NOW)

    assert out["period"] == "month"
    assert out["period_label"] == "Mei 2026"
    # NestJS ISO ts → Jakarta date-only; end = start + (days_elapsed - 1).
    assert out["period_range"] == {"start": "2026-05-01", "end": "2026-05-24"}
    assert out["updated_at"] == "2026-05-24T12:00:00+07:00"

    assert out["revenue"]["currency"] == "IDR"
    assert out["revenue"]["total"] == 1321457105
    assert out["revenue"]["sparkline"][0] == {"date": "2026-05-23", "value": 42384000}
    assert out["revenue"]["breakdown"]["retail"]["orders"] == 88

    assert out["quick_stats"]["conversion_rate_pct"] == 99.32
    assert out["quick_stats"]["conversion_rate_delta_pct"] == -0.68


def test_reshape_summary_severity_and_chart_mapping():
    out = mobile_metrics.reshape_summary(NEST_DASHBOARD, "month", now=NOW)

    assert [h["severity"] for h in out["highlights"]] == ["info", "red"]  # warning → red
    assert out["highlights"][0]["timestamp"].endswith("+07:00")

    chart = out["chart_daily"]
    assert chart["label"] == "Tren Omzet 7 Hari Terakhir"
    assert chart["subtitle"] == "Penjualan emas vs Rotasi"
    assert chart["data"][0]["label"] == "23"  # weekday → day-of-month number


def test_reshape_summary_ai_summary_is_templated_no_pii():
    out = mobile_metrics.reshape_summary(NEST_DASHBOARD, "month", now=NOW)
    ai = out["ai_summary"]

    assert ai["model"] == "template-v1"
    assert ai["status"] == "healthy"  # growth>0, conv>=70, expense<=8
    assert len(ai["paragraphs"]) == 3
    assert ai["paragraphs"][1]["type"] == "positive"  # conversion 99.32% >= 95
    assert ai["sources"] == ["payment_orders", "user_commission_ledger"]
    blob = json.dumps(out, ensure_ascii=False)
    assert "@" not in blob and "NIK" not in blob


# ── reshape: insight ─────────────────────────────────────────────────────────
def test_reshape_insight_matches_contract():
    out = mobile_metrics.reshape_insight(NEST_INSIGHT, "month", now=NOW)

    assert out["period_label"] == "1 – 24 Mei 2026"
    assert out["updated_at"] == "2026-05-24T12:00:00+07:00"

    kpis = {k["key"]: k for k in out["kpis"]}
    assert kpis["revenue_total"]["label"] == "Omzet Total"
    assert kpis["orders_settled"]["unit"] == "tx"
    assert kpis["revenue_total"]["delta_pct"] == 268
    # null delta_pct (potential_lost) is dropped to match contract.
    assert "delta_pct" not in kpis["potential_lost"]

    comp = out["composition"]
    assert comp["label"] == "Komposisi Omzet"
    assert comp["segments"][0] == {"label": "Penjualan Emas", "value": 880860250, "pct": 79.25, "color": "gold"}
    assert comp["segments"][1]["label"] == "Rotasi Masuk"
    assert comp["segments"][1]["color"] == "navy"


def test_reshape_insight_ai_analysis_metadata():
    out = mobile_metrics.reshape_insight(NEST_INSIGHT, "month", now=NOW)
    ai = out["ai_analysis"]
    assert [s["type"] for s in ai["sections"]] == ["healthy", "attention", "note"]
    assert ai["metadata"] == {"data_points": 148, "sources_count": 2, "confidence": "high"}


# ── client ───────────────────────────────────────────────────────────────────
class _FakeResp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_client_get_parses_json(monkeypatch):
    monkeypatch.setattr(
        client_mod.urllib.request, "urlopen",
        lambda req, timeout=0: _FakeResp(NEST_DASHBOARD),
    )
    client = LumbungMetricsClient("http://nest/api/executive/metrics", "tok")
    assert client.get_dashboard("month")["revenue"]["total"] == 1321457105


def test_client_retries_then_raises(monkeypatch):
    calls = []

    def _boom(req, timeout=0):
        calls.append(1)
        raise urllib.error.URLError("down")

    monkeypatch.setattr(client_mod.urllib.request, "urlopen", _boom)
    client = LumbungMetricsClient("http://nest", "tok", retries=1)
    try:
        client.get_insight("month")
        raise AssertionError("expected LumbungMetricsError")
    except LumbungMetricsError:
        pass
    assert len(calls) == 2  # initial try + 1 retry


# ── mobile_api fallback ──────────────────────────────────────────────────────
def test_mobile_api_falls_back_to_fixture_when_unconfigured(monkeypatch):
    monkeypatch.delenv("LUMBUNG_METRICS_TOKEN", raising=False)
    status, payload = mobile_api.mobile_handle(
        "GET", "/dashboard/summary", {"period": "month"}, None, access_token="t"
    )
    assert status == HTTPStatus.OK
    assert payload["revenue"]["total"] == 828882000  # the fixture value


def test_mobile_api_uses_live_metrics_when_available(monkeypatch):
    monkeypatch.setattr(
        mobile_metrics, "dashboard_summary",
        lambda period: {"period": period, "live": True},
    )
    status, payload = mobile_api.mobile_handle(
        "GET", "/dashboard/summary", {"period": "week"}, None, access_token="t"
    )
    assert status == HTTPStatus.OK
    assert payload == {"period": "week", "live": True}
