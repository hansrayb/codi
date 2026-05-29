"""Test bentuk JSON mobile API (`/api/v1/*`) — pakai bootstrap auth context.

Login/CRUD account flow di-cover oleh `test_auth.py`. Test ini fokus shape
endpoint baca (dashboard, insight, chat) yang tetap aksesibel pakai bootstrap
token legacy.
"""

from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from types import SimpleNamespace

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


# ── /me/sessions ────────────────────────────────────────────────────


class _FakeSessionManager:
    def __init__(self, sessions=None, *, raise_exc=None):
        self._sessions = sessions or []
        self._raise = raise_exc

    def list_sessions_snapshot(self):
        if self._raise:
            raise self._raise
        return list(self._sessions)


def _mk_session(
    *,
    session_id="s-01",
    role="advisor",
    cwd="/home/odc/lumbungemas-prod",
    created_at=None,
    last_activity_at=None,
    status="idle",
    case_id=None,
    owner_user_id=5354020279,
    message_count=3,
):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        session_id=session_id,
        role=role,
        cwd=cwd,
        created_at=created_at or (now - timedelta(minutes=30)),
        last_activity_at=last_activity_at or (now - timedelta(minutes=12)),
        status=status,
        case_id=case_id,
        owner_user_id=owner_user_id,
        message_count=message_count,
    )


def _sessions(*, mgr, ctx=_BOOTSTRAP_CTX):
    status, p = mobile_handle(
        "GET", "/me/sessions", {}, None,
        auth_ctx=ctx, auth_service=None, session_manager=mgr,
    )
    assert status == HTTPStatus.OK, (status, p)
    return p


def test_me_sessions_empty_without_manager():
    p = _sessions(mgr=None)
    assert p == {"active": 0, "sessions": []}


def test_me_sessions_empty_with_empty_manager():
    p = _sessions(mgr=_FakeSessionManager(sessions=[]))
    assert p == {"active": 0, "sessions": []}


def test_me_sessions_shape_with_two_sessions():
    s1 = _mk_session(
        session_id="s-01", role="advisor",
        cwd="/home/odc/lumbungemas-prod", status="idle",
        message_count=4,
    )
    s2 = _mk_session(
        session_id="s-02", role="builder",
        cwd="/home/odc/ai-agent-telegram", status="busy",
        case_id="c-01",
        last_activity_at=datetime.now(timezone.utc),  # newer → sorts first
        message_count=2,
    )
    p = _sessions(mgr=_FakeSessionManager(sessions=[s1, s2]))
    assert p["active"] == 2
    assert len(p["sessions"]) == 2
    # Sort by last_activity_at desc → s2 (newer) first.
    first, second = p["sessions"]
    assert first["id"] == "s-02"
    assert first["role"] == "builder"
    assert first["repo"] == "/home/odc/ai-agent-telegram"
    assert first["repo_name"] == "ai-agent-telegram"
    assert first["status"] == "busy"
    assert first["case_id"] == "c-01"
    assert first["user_id"] == 5354020279
    assert isinstance(first["started_at"], str) and "T" in first["started_at"]
    assert isinstance(first["last_activity_at"], str)
    assert isinstance(first["idle_seconds"], int) and first["idle_seconds"] >= 0
    assert first["message_count"] == 2
    # second item carries the older session.
    assert second["id"] == "s-01"
    assert second["repo_name"] == "lumbungemas-prod"
    assert second["status"] == "idle"


def test_me_sessions_graceful_on_manager_error():
    mgr = _FakeSessionManager(raise_exc=RuntimeError("boom"))
    p = _sessions(mgr=mgr)
    assert p == {"active": 0, "sessions": []}


def test_me_sessions_requires_auth():
    status, payload = mobile_handle(
        "GET", "/me/sessions", {}, None,
        auth_ctx=None, auth_service=None,
        session_manager=_FakeSessionManager(sessions=[_mk_session()]),
    )
    assert status == HTTPStatus.UNAUTHORIZED
    assert payload["error"]["code"] == "unauthorized"


def test_me_sessions_idle_seconds_monotonic_nonneg():
    # If last_activity_at is in the future (clock skew), idle_seconds clamps to 0.
    future = datetime.now(timezone.utc) + timedelta(seconds=30)
    p = _sessions(mgr=_FakeSessionManager(sessions=[
        _mk_session(last_activity_at=future),
    ]))
    assert p["active"] == 1
    assert p["sessions"][0]["idle_seconds"] == 0


def test_chat_messages_returns_reply():
    # No chat_history wired → still returns a reply (best-effort persist skipped).
    p = _ok("POST", "/chat/messages", body={"message": "halo"})
    assert p["role"] == "assistant"
    assert p["content"]["type"] == "text"
    assert len(p["suggestions"]) == 3


def test_chat_conversations_empty_without_store():
    # chat_history not wired → return empty (no fixture).
    p = _ok("GET", "/chat/conversations")
    assert p == {"conversations": [], "next_cursor": None}


def test_chat_conversation_messages_404_without_store():
    status, payload = mobile_handle(
        "GET", "/chat/conversations/conv_001/messages", {}, None,
        auth_ctx=_BOOTSTRAP_CTX, auth_service=None,
    )
    assert status == HTTPStatus.NOT_FOUND
    assert payload["error"]["code"] == "not_found"


# ── Chat history persist round-trip ─────────────────────────────────


def _fresh_chat_store(tmp_path):
    from core.chat_history import ChatHistoryStore
    return ChatHistoryStore.connect(tmp_path / "chat-history.db")


def _fake_chat_fn(reply: str = "Halo! Codi siap."):
    def _fn(_msg, _uid, _scope):
        return reply
    return _fn


def test_chat_post_creates_conversation_and_persists_turns(tmp_path):
    store = _fresh_chat_store(tmp_path)
    status, p = mobile_handle(
        "POST", "/chat/messages", {},
        {"message": "Bagaimana omzet hari ini?"},
        auth_ctx=_BOOTSTRAP_CTX, auth_service=None,
        chat_fn=_fake_chat_fn("Omzet hari ini Rp 15 jt."),
        chat_history=store,
    )
    assert status == HTTPStatus.OK
    conv_id = p["conversation_id"]
    assert conv_id and conv_id.startswith("conv_")
    assert "Omzet hari ini Rp 15 jt." in p["content"]["text"]

    # Conversation lists this new id.
    _, lst = mobile_handle(
        "GET", "/chat/conversations", {}, None,
        auth_ctx=_BOOTSTRAP_CTX, auth_service=None, chat_history=store,
    )
    assert len(lst["conversations"]) == 1
    conv = lst["conversations"][0]
    assert conv["id"] == conv_id
    assert conv["message_count"] == 2
    assert conv["title"].startswith("Bagaimana omzet")
    assert "Omzet hari ini" in conv["preview"]

    # Messages: 2 (user + assistant), in order.
    _, msgs = mobile_handle(
        "GET", f"/chat/conversations/{conv_id}/messages", {}, None,
        auth_ctx=_BOOTSTRAP_CTX, auth_service=None, chat_history=store,
    )
    assert msgs["conversation_id"] == conv_id
    assert len(msgs["messages"]) == 2
    assert msgs["messages"][0]["role"] == "user"
    assert msgs["messages"][0]["content"]["text"] == "Bagaimana omzet hari ini?"
    assert msgs["messages"][1]["role"] == "assistant"
    assert "Omzet hari ini" in msgs["messages"][1]["content"]["text"]


def test_chat_post_continues_conversation_with_id(tmp_path):
    store = _fresh_chat_store(tmp_path)
    _, p1 = mobile_handle(
        "POST", "/chat/messages", {}, {"message": "pertama"},
        auth_ctx=_BOOTSTRAP_CTX, auth_service=None,
        chat_fn=_fake_chat_fn("balas 1"), chat_history=store,
    )
    conv_id = p1["conversation_id"]
    _, p2 = mobile_handle(
        "POST", "/chat/messages", {},
        {"message": "lanjut", "conversation_id": conv_id},
        auth_ctx=_BOOTSTRAP_CTX, auth_service=None,
        chat_fn=_fake_chat_fn("balas 2"), chat_history=store,
    )
    assert p2["conversation_id"] == conv_id

    _, lst = mobile_handle(
        "GET", "/chat/conversations", {}, None,
        auth_ctx=_BOOTSTRAP_CTX, auth_service=None, chat_history=store,
    )
    # Still 1 conversation, but with 4 messages now.
    assert len(lst["conversations"]) == 1
    assert lst["conversations"][0]["message_count"] == 4


def test_chat_post_with_unknown_conv_id_creates_new(tmp_path):
    # If client sends a conversation_id that isn't owned by this account,
    # we create a fresh one and return its id (don't leak/cross accounts).
    store = _fresh_chat_store(tmp_path)
    _, p = mobile_handle(
        "POST", "/chat/messages", {},
        {"message": "hi", "conversation_id": "conv_nonexistent"},
        auth_ctx=_BOOTSTRAP_CTX, auth_service=None,
        chat_fn=_fake_chat_fn("ok"), chat_history=store,
    )
    assert p["conversation_id"] != "conv_nonexistent"
    assert p["conversation_id"].startswith("conv_")


def test_chat_get_messages_404_for_unknown_id(tmp_path):
    store = _fresh_chat_store(tmp_path)
    status, payload = mobile_handle(
        "GET", "/chat/conversations/conv_bogus/messages", {}, None,
        auth_ctx=_BOOTSTRAP_CTX, auth_service=None, chat_history=store,
    )
    assert status == HTTPStatus.NOT_FOUND
    assert payload["error"]["code"] == "not_found"


def test_chat_post_graceful_on_store_error():
    # Store raises on every method → POST still returns a reply.
    class _BrokenStore:
        def ensure_conversation(self, **_):
            raise RuntimeError("disk full")

        def append_message(self, **_):
            raise RuntimeError("disk full")

        def list_conversations(self, **_):
            raise RuntimeError("disk full")

        def get_messages(self, **_):
            raise RuntimeError("disk full")

    status, p = mobile_handle(
        "POST", "/chat/messages", {}, {"message": "hi"},
        auth_ctx=_BOOTSTRAP_CTX, auth_service=None,
        chat_fn=_fake_chat_fn("ok"), chat_history=_BrokenStore(),
    )
    assert status == HTTPStatus.OK
    assert p["content"]["text"]  # reply still flows
    # conversation_id falls back; not crashing is the contract.

    # GET conversations graceful → empty.
    _, lst = mobile_handle(
        "GET", "/chat/conversations", {}, None,
        auth_ctx=_BOOTSTRAP_CTX, auth_service=None, chat_history=_BrokenStore(),
    )
    assert lst == {"conversations": [], "next_cursor": None}

    # GET messages graceful → 404.
    status2, payload2 = mobile_handle(
        "GET", "/chat/conversations/conv_x/messages", {}, None,
        auth_ctx=_BOOTSTRAP_CTX, auth_service=None, chat_history=_BrokenStore(),
    )
    assert status2 == HTTPStatus.NOT_FOUND


def test_chat_conversations_scoped_per_account(tmp_path):
    """User A's conversations must not appear for user B."""
    store = _fresh_chat_store(tmp_path)
    ctx_a = AuthContext(
        account_id="acc_a", email="a@x", role_slug="dir",
        scopes=("chat:use",), is_bootstrap=False,
    )
    ctx_b = AuthContext(
        account_id="acc_b", email="b@x", role_slug="dir",
        scopes=("chat:use",), is_bootstrap=False,
    )
    _, p_a = mobile_handle(
        "POST", "/chat/messages", {}, {"message": "halo A"},
        auth_ctx=ctx_a, auth_service=None,
        chat_fn=_fake_chat_fn("reply"), chat_history=store,
    )
    a_conv = p_a["conversation_id"]
    _, lst_b = mobile_handle(
        "GET", "/chat/conversations", {}, None,
        auth_ctx=ctx_b, auth_service=None, chat_history=store,
    )
    assert lst_b["conversations"] == []
    # B can't read A's messages either.
    status, _ = mobile_handle(
        "GET", f"/chat/conversations/{a_conv}/messages", {}, None,
        auth_ctx=ctx_b, auth_service=None, chat_history=store,
    )
    assert status == HTTPStatus.NOT_FOUND


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
