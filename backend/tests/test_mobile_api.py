"""Test bentuk JSON mobile API (`/api/v1/*`) — pakai bootstrap auth context.

Login/CRUD account flow di-cover oleh `test_auth.py`. Test ini fokus shape
endpoint baca (dashboard, insight, chat) yang tetap aksesibel pakai bootstrap
token legacy.
"""

from datetime import datetime
from http import HTTPStatus

import pytest

from core import mobile_api
from core.auth.models import AuthContext
from core.hr_client import HRClientError
from core.mobile_api import mobile_handle


_BOOTSTRAP_CTX = AuthContext(
    account_id="bootstrap",
    email="bootstrap@codi",
    role_slug="bootstrap",
    scopes=("dashboard:read", "insight:read", "chat:use"),
    is_bootstrap=True,
)


def _ok(method, path, query=None, body=None):
    status, payload = mobile_handle(
        method,
        path,
        query or {},
        body,
        auth_ctx=_BOOTSTRAP_CTX,
        auth_service=None,
    )
    assert status == HTTPStatus.OK, (path, status, payload)
    return payload


def test_me_bootstrap_shape():
    p = _ok("GET", "/me")
    assert p["role"] == "bootstrap"
    assert p["preferences"]["language"] == "id"
    assert "dashboard:read" in p["scopes"]


def test_dashboard_summary_shape():
    p = _ok("GET", "/dashboard/summary", query={"period": "month"})
    assert p["period"] == "month"
    assert p["revenue"]["total"] == 828882000
    assert len(p["revenue"]["sparkline"]) == 7
    assert len(p["chart_daily"]["data"]) == 7
    assert len(p["highlights"]) == 3
    assert len(p["ai_summary"]["paragraphs"]) == 3


def test_dashboard_insight_shape():
    p = _ok("GET", "/dashboard/insight")
    assert len(p["kpis"]) == 4
    assert len(p["composition"]["segments"]) == 2
    assert len(p["ai_analysis"]["sections"]) == 3


_REPORTS_CTX = AuthContext(
    account_id="acc_test",
    email="test@codi",
    role_slug="director",
    scopes=("reports:read",),
    is_bootstrap=False,
)


def test_reports_shape():
    status, p = mobile_handle(
        "GET", "/reports", {"period": "all"}, None,
        auth_ctx=_REPORTS_CTX, auth_service=None,
    )
    assert status == HTTPStatus.OK
    assert p["period"] == "all"
    assert len(p["groups"]) == 2
    assert p["groups"][0]["label"] == "Terbaru"
    assert len(p["groups"][0]["items"]) == 3
    assert p["groups"][0]["items"][0]["category"] == "omzet"


def test_reports_period_month_narrows():
    _, p = mobile_handle(
        "GET", "/reports", {"period": "month"}, None,
        auth_ctx=_REPORTS_CTX, auth_service=None,
    )
    assert len(p["groups"]) == 1


# ── /reports real path: mock HR + Lumbung; cover success, fallback,
#    payroll_insight thresholds. No network in tests.


class _FakeHRClient:
    """Async-shaped fake matching mobile_api._gather_payroll/_gather_attendance."""

    def __init__(self, *, runs=None, items_by_run=None, attendance=None, error=None):
        self._runs = runs or []
        self._items_by_run = items_by_run or {}
        self._attendance = attendance or []
        self._error = error

    async def get_payroll_runs(self, year=None, month=None):
        if self._error:
            raise HRClientError(self._error)
        return list(self._runs)

    async def get_payroll_items(self, run_id: int):
        if self._error:
            raise HRClientError(self._error)
        return list(self._items_by_run.get(int(run_id), []))

    async def get_attendance_summary(self, from_date: str, to_date: str, employee_id: str = ""):
        if self._error:
            raise HRClientError(self._error)
        return list(self._attendance)


def _omzet_fixture(total: int, orders: int, period_label: str, end_date: str):
    def _fn(_period):
        return {
            "period": "month",
            "period_label": period_label,
            "period_range": {"start": "2026-05-01", "end": end_date},
            "revenue": {"total": total},
            "quick_stats": {"orders_total": orders},
        }
    return _fn


@pytest.fixture
def _patch_reports_realpath(monkeypatch):
    """Yield a callable that wires fake HRClient + dashboard_summary into mobile_api."""

    def _apply(*, hr, omzet_total=1_000_000_000, omzet_orders=50, period_label="Mei 2026", end_date="2026-05-29"):
        monkeypatch.setattr(mobile_api, "_build_hr_client", lambda: hr)
        monkeypatch.setattr(
            mobile_api.mobile_metrics,
            "dashboard_summary",
            _omzet_fixture(omzet_total, omzet_orders, period_label, end_date),
        )

    return _apply


def _now_ym():
    """Current year+month so test fixtures land in 'Terbaru' bucket."""
    d = datetime.now(mobile_api._JKT)
    return d.year, d.month


def _make_runs_with_current_month_payroll(net_pay_total: int, n_items: int = 2):
    """Build a payroll run dated for the current month so payroll_insight triggers."""
    y, m = _now_ym()
    today_iso = datetime.now(mobile_api._JKT).date().isoformat()
    run = {
        "id": 99,
        "year": y,
        "month": m,
        "period_start": today_iso,
        "period_end": today_iso,
        "status": "finalized",
        "created_at": today_iso,
    }
    per = net_pay_total / n_items if n_items else 0
    items = [{"id": i, "net_pay": per} for i in range(n_items)]
    return [run], {99: items}


def test_reports_real_path_includes_omzet_and_payroll_items(_patch_reports_realpath):
    runs, items_by_run = _make_runs_with_current_month_payroll(200_000_000)
    hr = _FakeHRClient(runs=runs, items_by_run=items_by_run, attendance=[])
    _patch_reports_realpath(hr=hr, omzet_total=1_000_000_000, omzet_orders=50)

    status, p = mobile_handle(
        "GET", "/reports", {"period": "all"}, None,
        auth_ctx=_REPORTS_CTX, auth_service=None,
    )
    assert status == HTTPStatus.OK
    cats = [it["category"] for g in p["groups"] for it in g["items"]]
    assert "omzet" in cats and "payroll" in cats
    omzet_item = next(it for g in p["groups"] for it in g["items"] if it["category"] == "omzet")
    assert "Rp 1.000.000.000" in omzet_item["meta"]
    assert "50 order" in omzet_item["meta"]


def test_reports_payroll_insight_sehat(_patch_reports_realpath):
    # 200M / 1B = 20% → < 35 → sehat
    runs, items = _make_runs_with_current_month_payroll(200_000_000)
    _patch_reports_realpath(
        hr=_FakeHRClient(runs=runs, items_by_run=items), omzet_total=1_000_000_000,
    )
    _, p = mobile_handle("GET", "/reports", {"period": "month"}, None,
                        auth_ctx=_REPORTS_CTX, auth_service=None)
    insight = p["payroll_insight"]
    assert insight["status"] == "sehat"
    assert insight["ratio_pct"] == 20.0
    assert insight["omzet"] == 1_000_000_000
    assert insight["payroll"] == 200_000_000


def test_reports_payroll_insight_waspada(_patch_reports_realpath):
    # 400M / 1B = 40% → 35 ≤ ratio < 50 → waspada
    runs, items = _make_runs_with_current_month_payroll(400_000_000)
    _patch_reports_realpath(
        hr=_FakeHRClient(runs=runs, items_by_run=items), omzet_total=1_000_000_000,
    )
    _, p = mobile_handle("GET", "/reports", {"period": "month"}, None,
                        auth_ctx=_REPORTS_CTX, auth_service=None)
    assert p["payroll_insight"]["status"] == "waspada"
    assert p["payroll_insight"]["ratio_pct"] == 40.0


def test_reports_payroll_insight_kritis(_patch_reports_realpath):
    # 600M / 1B = 60% → ≥ 50 → kritis
    runs, items = _make_runs_with_current_month_payroll(600_000_000)
    _patch_reports_realpath(
        hr=_FakeHRClient(runs=runs, items_by_run=items), omzet_total=1_000_000_000,
    )
    _, p = mobile_handle("GET", "/reports", {"period": "month"}, None,
                        auth_ctx=_REPORTS_CTX, auth_service=None)
    assert p["payroll_insight"]["status"] == "kritis"


def test_reports_falls_back_to_fixture_when_hr_errors(_patch_reports_realpath, monkeypatch):
    # HR fails AND Lumbung not configured → no omzet, no payroll → empty groups → fixture.
    hr = _FakeHRClient(error="HR down")
    monkeypatch.setattr(mobile_api, "_build_hr_client", lambda: hr)

    def _no_omzet(_period):
        from core.lumbung_metrics_client import LumbungMetricsError
        raise LumbungMetricsError("not configured")

    monkeypatch.setattr(mobile_api.mobile_metrics, "dashboard_summary", _no_omzet)
    status, p = mobile_handle(
        "GET", "/reports", {"period": "all"}, None,
        auth_ctx=_REPORTS_CTX, auth_service=None,
    )
    assert status == HTTPStatus.OK
    # Fallback fixture has 2 groups for period != month.
    assert len(p["groups"]) == 2
    assert p["groups"][0]["label"] == "Terbaru"
    assert "payroll_insight" not in p


def test_reports_payroll_insight_absent_without_omzet(_patch_reports_realpath):
    # Payroll present but omzet 0 → ratio undefined → no payroll_insight.
    runs, items = _make_runs_with_current_month_payroll(100_000_000)
    _patch_reports_realpath(
        hr=_FakeHRClient(runs=runs, items_by_run=items), omzet_total=0,
    )
    _, p = mobile_handle("GET", "/reports", {"period": "month"}, None,
                        auth_ctx=_REPORTS_CTX, auth_service=None)
    assert "payroll_insight" not in p


def test_reports_items_have_detail_ref(_patch_reports_realpath):
    runs, items_by_run = _make_runs_with_current_month_payroll(200_000_000)
    hr = _FakeHRClient(runs=runs, items_by_run=items_by_run, attendance=[])
    _patch_reports_realpath(hr=hr, omzet_total=1_000_000_000)
    _, p = mobile_handle(
        "GET", "/reports", {"period": "all"}, None,
        auth_ctx=_REPORTS_CTX, auth_service=None,
    )
    refs = [it.get("detail_ref") for g in p["groups"] for it in g["items"]]
    assert all(r and ":" in r for r in refs), refs
    # Payroll ref shape "payroll:<int>", omzet "omzet:YYYY-MM".
    assert any(r.startswith("payroll:") for r in refs)
    assert any(r.startswith("omzet:") for r in refs)


# ── /reports/detail ─────────────────────────────────────────────────────


_PAYROLL_RUN_FIXTURE = {
    "id": 6,
    "year": 2026,
    "month": 5,
    "period_start": "2026-04-26",
    "period_end": "2026-05-25",
    "status": "finalized",
    "created_at": "2026-04-26T00:00:00+00:00",
}

_PAYROLL_ITEMS_FIXTURE = [
    {"id": 1, "run_id": 6, "employee_id": "108", "employee_name": "Aan Hendralio",
     "department_name": "HRGA", "position_name": "Supervisor", "net_pay": 7114351},
    {"id": 2, "run_id": 6, "employee_id": "109", "employee_name": "Budi Santoso",
     "department_name": "Operasional", "position_name": "Staff", "net_pay": 5230000},
    {"id": 3, "run_id": 6, "employee_id": "110", "employee_name": "Citra Dewi",
     "department_name": "Finance", "position_name": "Manager", "net_pay": 8500000},
]


def _detail(ref: str, *, expect_status=HTTPStatus.OK):
    status, p = mobile_handle(
        "GET", "/reports/detail", {"ref": ref}, None,
        auth_ctx=_REPORTS_CTX, auth_service=None,
    )
    assert status == expect_status, (ref, status, p)
    return p


def test_reports_detail_payroll_shape(monkeypatch):
    hr = _FakeHRClient(
        runs=[_PAYROLL_RUN_FIXTURE],
        items_by_run={6: _PAYROLL_ITEMS_FIXTURE},
    )
    monkeypatch.setattr(mobile_api, "_build_hr_client", lambda: hr)
    p = _detail("payroll:6")
    assert p["ref"] == "payroll:6"
    assert p["category"] == "payroll"
    assert p["status"] == "finalized"
    assert "Mei 2026" in p["title"]
    summary_labels = {row["label"] for row in p["summary"]}
    assert {"Periode", "Karyawan", "Total Net", "Status"} <= summary_labels
    # rows sorted by net_pay desc → Citra (8.5jt) first.
    assert p["rows"][0]["label"] == "Citra Dewi"
    assert "Rp 8.500.000" in p["rows"][0]["value"]
    assert p["rows"][0]["sub"] == "Finance"


def test_reports_detail_payroll_run_not_found_404(monkeypatch):
    hr = _FakeHRClient(runs=[_PAYROLL_RUN_FIXTURE], items_by_run={6: _PAYROLL_ITEMS_FIXTURE})
    monkeypatch.setattr(mobile_api, "_build_hr_client", lambda: hr)
    _detail("payroll:999", expect_status=HTTPStatus.NOT_FOUND)


def test_reports_detail_payroll_hr_unavailable(monkeypatch):
    monkeypatch.setattr(mobile_api, "_build_hr_client", lambda: None)
    p = _detail("payroll:6")
    # Graceful: summary + rows[1] note row.
    assert p["category"] == "payroll"
    assert p["rows"]
    assert "HR backend" in p["summary"][0]["value"]


def test_reports_detail_absensi_shape(monkeypatch):
    attendance = [
        {"user_id": 108, "user_name": "Aan", "attendance_date": "2026-05-02", "status": "PRESENT"},
        {"user_id": 108, "user_name": "Aan", "attendance_date": "2026-05-03", "status": "LATE"},
        {"user_id": 108, "user_name": "Aan", "attendance_date": "2026-05-04", "status": "PRESENT"},
        {"user_id": 109, "user_name": "Budi", "attendance_date": "2026-05-02", "status": "PRESENT"},
        {"user_id": 109, "user_name": "Budi", "attendance_date": "2026-05-03", "status": "ABSENT"},
    ]
    hr = _FakeHRClient(runs=[], items_by_run={}, attendance=attendance)
    monkeypatch.setattr(mobile_api, "_build_hr_client", lambda: hr)
    p = _detail("absensi:2026-05")
    assert p["ref"] == "absensi:2026-05"
    assert p["category"] == "absensi"
    assert "Mei 2026" in p["title"]
    assert len(p["rows"]) == 2
    # rows sorted by name asc → Aan before Budi.
    assert p["rows"][0]["label"] == "Aan"
    assert "Hadir: 2" in p["rows"][0]["sub"]
    assert "Telat: 1" in p["rows"][0]["sub"]
    assert "Alpa: 1" in p["rows"][1]["sub"]


def test_reports_detail_absensi_hr_unavailable(monkeypatch):
    monkeypatch.setattr(mobile_api, "_build_hr_client", lambda: None)
    p = _detail("absensi:2026-05")
    assert p["category"] == "absensi"
    assert "Mei 2026" in p["title"]
    assert p["summary"][0]["label"] == "Status"
    assert "HR backend" in p["summary"][0]["value"]


def test_reports_detail_omzet_shape(monkeypatch):
    monkeypatch.setattr(mobile_api, "_build_hr_client", lambda: None)

    def _summary(_p):
        return {
            "period": "month",
            "period_label": "Mei 2026",
            "revenue": {"total": 1_000_000_000},
            "quick_stats": {"orders_total": 50},
        }

    def _insight(_p):
        return {
            "kpis": [
                {"key": "revenue_total", "label": "Omzet Total",
                 "value": 1_000_000_000, "unit": "IDR", "delta_label": "+10% MoM"},
                {"key": "orders_settled", "label": "Order Settled",
                 "value": 50, "unit": "tx", "delta_label": "30 retail · 20 rotasi"},
            ],
            "composition": {
                "total": 1_000_000_000,
                "segments": [
                    {"label": "Penjualan Emas", "value": 700_000_000, "pct": 70.0},
                    {"label": "Rotasi Masuk", "value": 300_000_000, "pct": 30.0},
                ],
            },
        }

    monkeypatch.setattr(mobile_api.mobile_metrics, "dashboard_summary", _summary)
    monkeypatch.setattr(mobile_api.mobile_metrics, "dashboard_insight", _insight)
    p = _detail("omzet:2026-05")
    assert p["ref"] == "omzet:2026-05"
    assert p["category"] == "omzet"
    assert "Mei 2026" in p["title"]
    summary_labels = [s["label"] for s in p["summary"]]
    assert summary_labels == ["Periode", "Total Omzet", "Order"]
    assert any("Rp 1.000.000.000" in s["value"] for s in p["summary"])
    # rows: 2 composition + 2 KPI
    assert any(r["label"] == "Penjualan Emas" and "Rp 700.000.000" in r["value"] for r in p["rows"])
    assert any(r["label"] == "Order Settled" and r["value"] == "50 tx" for r in p["rows"])


def test_reports_detail_omzet_lumbung_unavailable(monkeypatch):
    monkeypatch.setattr(mobile_api, "_build_hr_client", lambda: None)
    from core.lumbung_metrics_client import LumbungMetricsError

    def _raise(_p):
        raise LumbungMetricsError("down")

    monkeypatch.setattr(mobile_api.mobile_metrics, "dashboard_summary", _raise)
    p = _detail("omzet:2026-05")
    assert p["category"] == "omzet"
    assert "Lumbung" in p["summary"][0]["value"]


def test_reports_detail_invalid_ref_returns_404():
    _detail("", expect_status=HTTPStatus.NOT_FOUND)
    _detail("no_colon", expect_status=HTTPStatus.NOT_FOUND)
    _detail("unknown:foo", expect_status=HTTPStatus.NOT_FOUND)
    _detail("payroll:not-int", expect_status=HTTPStatus.NOT_FOUND)
    _detail("absensi:2026-13", expect_status=HTTPStatus.NOT_FOUND)
    _detail("omzet:bad-key", expect_status=HTTPStatus.NOT_FOUND)


def test_chat_messages_returns_reply():
    p = _ok("POST", "/chat/messages", body={"message": "halo"})
    assert p["role"] == "assistant"
    assert p["content"]["type"] == "text"
    assert len(p["suggestions"]) == 3


def test_chat_conversations_list():
    p = _ok("GET", "/chat/conversations")
    assert p["conversations"][0]["id"] == "conv_001"


def test_chat_conversation_messages():
    p = _ok("GET", "/chat/conversations/conv_001/messages")
    assert p["conversation_id"] == "conv_001"
    assert p["messages"][1]["content"]["card"]["badge"]["label"] == "SEHAT"


def test_unknown_path_404():
    status, _ = mobile_handle(
        "GET", "/nope", {}, None, auth_ctx=_BOOTSTRAP_CTX, auth_service=None
    )
    assert status == HTTPStatus.NOT_FOUND


def test_no_ctx_returns_401():
    status, payload = mobile_handle(
        "GET", "/me", {}, None, auth_ctx=None, auth_service=None
    )
    assert status == HTTPStatus.UNAUTHORIZED
    assert payload["error"]["code"] == "unauthorized"


def test_login_without_service_returns_503():
    status, payload = mobile_handle(
        "POST",
        "/auth/login",
        {},
        {"email": "x@x.com", "password": "x"},
        auth_ctx=None,
        auth_service=None,
    )
    assert status == HTTPStatus.SERVICE_UNAVAILABLE
    assert payload["error"]["code"] == "auth_unavailable"
