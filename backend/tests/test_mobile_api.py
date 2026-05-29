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
