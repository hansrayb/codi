"""Test bentuk JSON mobile API (`/api/v1/*`) — pakai bootstrap auth context.

Login/CRUD account flow di-cover oleh `test_auth.py`. Test ini fokus shape
endpoint baca (dashboard, insight, chat) yang tetap aksesibel pakai bootstrap
token legacy.
"""

from http import HTTPStatus

from core.auth.models import AuthContext
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
