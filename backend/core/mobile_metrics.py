"""Reshape NestJS `/executive/metrics/*` → kontrak app Emas Berlian Insight.

Fase A2 (arsitektur Y): Codi jadi proxy + reshaper. Endpoint NestJS
mengembalikan agregasi nyata dengan bentuk sendiri; modul ini memetakannya
PERSIS ke `app/docs/04-API-CONTRACT.md` (lihat fixture di `mobile_api.py`).

`ai_summary`/`ai_analysis` di-generate dari template berbasis angka real
(belum LLM). Untuk versi LLM, panggil claude executor dari sini dan ganti
`_build_ai_summary`/`_build_ai_analysis` (model id → model nyata).

Fungsi reshape bersifat MURNI (input dict NestJS + `now`) sehingga mudah
ditest tanpa jaringan.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

from core.lumbung_metrics_client import LumbungMetricsClient, LumbungMetricsError

JKT = timezone(timedelta(hours=7))
_DEFAULT_URL = "http://localhost:4001/api/executive/metrics"

_MONTHS_ID = [
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]

# NestJS severity/category → app contract severity.
_SEVERITY_MAP = {"positive": "green", "info": "info", "warning": "red", "critical": "red"}

# KPI key → (label app, unit app). Nilai/trend tetap dari NestJS.
_KPI_LABELS = {
    "revenue_total": ("Omzet Total", "IDR"),
    "orders_settled": ("Order Settled", "tx"),
    "avg_ticket": ("Avg. Ticket", "IDR"),
    "potential_lost": ("Potensi Hilang", "IDR"),
}

# Segment komposisi NestJS → label + warna semantik app.
_SEGMENT_MAP = {"Retail": ("Penjualan Emas", "gold"), "Rotasi": ("Rotasi Masuk", "navy")}

_CHART_LABEL = "Tren Omzet 7 Hari Terakhir"
_CHART_SUBTITLE = "Penjualan emas vs Rotasi"


# ── orchestration (live fetch + reshape) ─────────────────────────────────────
def build_client() -> LumbungMetricsClient | None:
    """Build a client from env, or None if service credentials are not set."""
    email = (os.getenv("LUMBUNG_METRICS_EMAIL") or "").strip()
    password = (os.getenv("LUMBUNG_METRICS_PASSWORD") or "").strip()
    if not email or not password:
        return None
    base_url = (os.getenv("LUMBUNG_METRICS_URL") or _DEFAULT_URL).strip() or _DEFAULT_URL
    login_url = (os.getenv("LUMBUNG_METRICS_LOGIN_URL") or "").strip() or None
    return LumbungMetricsClient(base_url, email, password, login_url=login_url)


def dashboard_summary(
    period: str,
    *,
    client: LumbungMetricsClient | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Fetch + reshape `/dashboard/summary`. Raises LumbungMetricsError if down."""
    client = client or build_client()
    if client is None:
        raise LumbungMetricsError("LUMBUNG_METRICS_TOKEN not configured")
    nest = client.get_dashboard(period)
    return reshape_summary(nest, period, now=now or datetime.now(JKT))


def dashboard_insight(
    period: str,
    *,
    client: LumbungMetricsClient | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Fetch + reshape `/dashboard/insight`. Raises LumbungMetricsError if down."""
    client = client or build_client()
    if client is None:
        raise LumbungMetricsError("LUMBUNG_METRICS_TOKEN not configured")
    nest = client.get_insight(period)
    return reshape_insight(nest, period, now=now or datetime.now(JKT))


# ── reshape: summary ─────────────────────────────────────────────────────────
def reshape_summary(nest: dict[str, Any], period: str, *, now: datetime) -> dict[str, Any]:
    """Map NestJS dashboard → app `/dashboard/summary` contract."""
    rng = nest.get("period_range", {})
    start_date = _to_jkt_date(rng.get("start")) if rng.get("start") else now.date().isoformat()
    days_elapsed = int(nest.get("days_elapsed", 1))
    end_date = _add_days(start_date, max(0, days_elapsed - 1))

    revenue_src = nest.get("revenue", {})
    revenue = {
        "total": _int(revenue_src.get("total")),
        "currency": "IDR",
        "growth_mom_pct": _num(revenue_src.get("growth_mom_pct")),
        "projection_full_period": _int(revenue_src.get("projection_full_period")),
        "sparkline": [
            {"date": p.get("date"), "value": _int(p.get("value"))}
            for p in revenue_src.get("sparkline", [])
        ],
        "breakdown": revenue_src.get("breakdown", {}),
    }
    quick_src = nest.get("quick_stats", {})
    quick_stats = {
        "orders_total": _int(quick_src.get("orders_total")),
        "orders_retail": _int(quick_src.get("orders_retail")),
        "orders_rotasi": _int(quick_src.get("orders_rotasi")),
        "conversion_rate_pct": _num(quick_src.get("conversion_rate_pct")),
        "conversion_rate_delta_pct": _num(quick_src.get("conversion_rate_delta_pct")),
        "expense_total": _int(quick_src.get("expense_total")),
        "expense_pct_of_revenue": _num(quick_src.get("expense_pct_of_revenue")),
    }
    period_label = _summary_label(period, start_date, end_date)

    return {
        "period": nest.get("period", period),
        "period_label": period_label,
        "period_range": {"start": start_date, "end": end_date},
        "is_partial": bool(nest.get("is_partial", True)),
        "days_elapsed": days_elapsed,
        "days_in_period": int(nest.get("days_in_period", days_elapsed)),
        "updated_at": _to_jkt_iso(nest.get("updated_at")) or now.isoformat(),
        "revenue": revenue,
        "quick_stats": quick_stats,
        "ai_summary": _build_ai_summary(revenue, quick_stats, period_label, now),
        "highlights": [_map_highlight(h) for h in nest.get("highlights", [])],
        "chart_daily": _reshape_chart(nest.get("chart_daily", {}).get("data", [])),
    }


def _reshape_chart(data: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "label": _CHART_LABEL,
        "subtitle": _CHART_SUBTITLE,
        "data": [
            {
                "date": p.get("date"),
                "label": _day_label(p.get("date")),
                "retail": _int(p.get("retail")),
                "rotasi": _int(p.get("rotasi")),
            }
            for p in data
        ],
    }


def _map_highlight(h: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": h.get("id"),
        "severity": _SEVERITY_MAP.get(h.get("severity", ""), "info"),
        "title": h.get("title"),
        "description": h.get("description"),
        "timestamp": _to_jkt_iso(h.get("timestamp")),
        "category": h.get("category"),
    }


# ── reshape: insight ─────────────────────────────────────────────────────────
def reshape_insight(nest: dict[str, Any], period: str, *, now: datetime) -> dict[str, Any]:
    """Map NestJS insight → app `/dashboard/insight` contract."""
    kpis = [_map_kpi(k) for k in nest.get("kpis", [])]
    composition = _reshape_composition(nest.get("composition", {}))
    metadata = nest.get("metadata", {})
    return {
        "period": nest.get("period", period),
        "period_label": _insight_label(period, now),
        "updated_at": now.isoformat(),
        "kpis": kpis,
        "composition": composition,
        "ai_analysis": _build_ai_analysis(kpis, composition, metadata, now),
    }


def _map_kpi(k: dict[str, Any]) -> dict[str, Any]:
    key = k.get("key", "")
    label, unit = _KPI_LABELS.get(key, (k.get("label"), k.get("unit")))
    kpi: dict[str, Any] = {
        "key": key,
        "label": label,
        "value": _int(k.get("value")),
        "unit": unit,
        "delta_label": k.get("delta_label", ""),
        "trend": k.get("trend", "flat"),
    }
    if k.get("delta_pct") is not None:
        kpi["delta_pct"] = _num(k.get("delta_pct"))
    return kpi


def _reshape_composition(comp: dict[str, Any]) -> dict[str, Any]:
    segments = []
    for seg in comp.get("segments", []):
        label, color = _SEGMENT_MAP.get(seg.get("label", ""), (seg.get("label"), seg.get("color")))
        segments.append(
            {
                "label": label,
                "value": _int(seg.get("value")),
                "pct": _num(seg.get("pct")),
                "color": color,
            }
        )
    return {"label": "Komposisi Omzet", "total": _int(comp.get("total")), "segments": segments}


# ── AI template (dari angka real, belum LLM) ─────────────────────────────────
def _build_ai_summary(
    revenue: dict[str, Any], quick: dict[str, Any], period_label: str, now: datetime
) -> dict[str, Any]:
    total = revenue["total"]
    growth = revenue["growth_mom_pct"]
    retail = revenue.get("breakdown", {}).get("retail", {})
    conversion = quick["conversion_rate_pct"]
    expense_pct = quick["expense_pct_of_revenue"]

    status = "healthy"
    if growth < 0 or conversion < 70 or expense_pct > 8:
        status = "attention"

    positive = (
        f"Operasional kantor dalam kondisi {'sehat' if status == 'healthy' else 'perlu perhatian'}. "
        f"Omzet {period_label} mencapai {_rp(total)} ({_growth_phrase(growth)}), "
        f"ditopang penjualan emas retail {_rp(_int(retail.get('value')))} "
        f"dari {_int(retail.get('orders'))} order ({_gram(retail.get('weight_gram'))})."
    )
    if conversion < 95:
        second = {
            "type": "warning",
            "text": (
                f"Yang perlu perhatian: conversion rate {_pct(conversion)} — "
                f"sebagian order dibuat tapi belum terbayar."
            ),
        }
    else:
        second = {
            "type": "positive",
            "text": (
                f"Konversi pembayaran kuat di {_pct(conversion)} — hampir seluruh "
                f"order terbayar."
            ),
        }
    note = {
        "type": "note",
        "text": f"Beban komisi {_pct(expense_pct)} dari omzet — {_expense_phrase(expense_pct)}.",
    }

    return {
        "id": f"summary_{now:%Y%m%d%H}",
        "generated_at": now.isoformat(),
        "model": "template-v1",
        "tone": "executive_formal",
        "status": status,
        "paragraphs": [{"type": "positive", "text": positive}, second, note],
        "data_points_count": quick["orders_total"],
        "sources": ["payment_orders", "user_commission_ledger"],
    }


def _build_ai_analysis(
    kpis: list[dict[str, Any]], composition: dict[str, Any], metadata: dict[str, Any], now: datetime
) -> dict[str, Any]:
    by_key = {k["key"]: k for k in kpis}
    revenue_total = _int(by_key.get("revenue_total", {}).get("value"))
    revenue_delta = by_key.get("revenue_total", {}).get("delta_pct")
    avg_ticket = _int(by_key.get("avg_ticket", {}).get("value"))
    potential_lost = _int(by_key.get("potential_lost", {}).get("value"))
    segments = composition.get("segments", [])
    data_points = _int(metadata.get("data_points"))

    healthy = (
        f"Omzet mencapai {_rp(revenue_total)} ({_growth_phrase(revenue_delta)}), "
        f"dengan rata-rata transaksi {_rp(avg_ticket)}."
    )
    if potential_lost > 0:
        attention = (
            f"Terdapat potensi omzet belum terbayar {_rp(potential_lost)} — "
            f"pantau order yang tertunda atau expired."
        )
    else:
        attention = "Tidak ada potensi kehilangan signifikan pada periode ini."
    comp_phrase = (
        ", ".join(f"{_pct(s.get('pct'))} {s.get('label')}" for s in segments) or "—"
    )
    note = (
        f"Komposisi omzet: {comp_phrase}. Data sistem berjalan sejak April 2026 "
        f"sehingga pembanding historis masih terbatas."
    )

    return {
        "id": f"analysis_{now:%Y%m%d%H}",
        "generated_at": now.isoformat(),
        "sections": [
            {"type": "healthy", "title": "Yang Sehat", "content": healthy},
            {"type": "attention", "title": "Yang Perlu Perhatian", "content": attention},
            {"type": "note", "title": "Catatan", "content": note},
        ],
        "metadata": {
            "data_points": data_points,
            "sources_count": _int(metadata.get("sources_count")),
            "confidence": _confidence(data_points),
        },
    }


# ── labels & formatting ──────────────────────────────────────────────────────
def _summary_label(period: str, start_date: str, end_date: str) -> str:
    s = date.fromisoformat(start_date)
    e = date.fromisoformat(end_date)
    if period == "today":
        return f"{e.day} {_MONTHS_ID[e.month]} {e.year}"
    if period == "year":
        return str(e.year)
    if period == "week":
        return _range_label(s, e)
    return f"{_MONTHS_ID[s.month]} {s.year}"  # month


def _insight_label(period: str, now: datetime) -> str:
    today = now.date()
    if period == "today":
        return f"{today.day} {_MONTHS_ID[today.month]} {today.year}"
    if period == "year":
        return f"Jan – {_MONTHS_ID[today.month]} {today.year}"
    if period == "week":
        start = today - timedelta(days=today.weekday())
        return _range_label(start, today)
    start = today.replace(day=1)  # month
    return _range_label(start, today)


def _range_label(start: date, end: date) -> str:
    if start.month == end.month and start.year == end.year:
        return f"{start.day} – {end.day} {_MONTHS_ID[end.month]} {end.year}"
    return (
        f"{start.day} {_MONTHS_ID[start.month]} – "
        f"{end.day} {_MONTHS_ID[end.month]} {end.year}"
    )


def _rp(value: Any) -> str:
    n = _int(value)
    if n >= 1_000_000_000:
        return f"Rp {n / 1_000_000_000:.1f} M".replace(".", ",")
    if n >= 1_000_000:
        return f"Rp {n / 1_000_000:.1f} jt".replace(".", ",")
    if n >= 1_000:
        return f"Rp {round(n / 1_000)} rb"
    return f"Rp {n}"


def _pct(value: Any) -> str:
    x = _num(value)
    s = f"{x:.1f}"
    if s.endswith(".0"):
        s = s[:-2]
    return s.replace(".", ",") + "%"


def _growth_phrase(growth: Any) -> str:
    if growth is None:
        return "tanpa pembanding periode sebelumnya"
    x = _num(growth)
    if x > 0:
        return f"tumbuh +{_pct(x)} dibanding periode sebelumnya"
    if x < 0:
        return f"turun {_pct(abs(x))} dibanding periode sebelumnya"
    return "setara periode sebelumnya"


def _expense_phrase(expense_pct: float) -> str:
    if expense_pct < 2:
        return "rasio yang sangat sehat"
    if expense_pct < 5:
        return "rasio yang sehat"
    return "rasio yang perlu dipantau"


def _confidence(data_points: int) -> str:
    if data_points >= 30:
        return "high"
    if data_points >= 10:
        return "medium"
    return "low"


def _gram(value: Any) -> str:
    g = _num(value)
    s = f"{g:.1f}".replace(".", ",")
    return f"{s} g"


# ── primitive helpers ────────────────────────────────────────────────────────
def _int(value: Any) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _parse_iso(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _to_jkt_date(iso: str) -> str:
    return _parse_iso(iso).astimezone(JKT).date().isoformat()


def _to_jkt_iso(iso: str | None) -> str | None:
    if not iso:
        return None
    return _parse_iso(iso).astimezone(JKT).isoformat()


def _add_days(date_str: str, days: int) -> str:
    return (date.fromisoformat(date_str) + timedelta(days=days)).isoformat()


def _day_label(date_str: str | None) -> str:
    if not date_str:
        return ""
    try:
        return str(date.fromisoformat(date_str).day)
    except ValueError:
        return date_str
