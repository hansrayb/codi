"""Test stub mobile API (`/api/v1/*`) — bentuk JSON sesuai kontrak."""

from http import HTTPStatus

from core.mobile_api import mobile_handle

TOKEN = "test-token"


def _ok(method, path, query=None, body=None):
    status, payload = mobile_handle(
        method, path, query or {}, body, access_token=TOKEN
    )
    assert status == HTTPStatus.OK, (path, status, payload)
    return payload


def test_login_returns_token_and_user():
    p = _ok("POST", "/auth/login", body={"device_id": "x"})
    assert p["access_token"] == TOKEN
    assert p["user"]["initials"] == "LS"
    assert p["expires_in"] == 604800


def test_me_shape():
    p = _ok("GET", "/me")
    assert p["role"] == "director"
    assert "preferences" in p
    assert p["preferences"]["language"] == "id"


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
    status, _ = mobile_handle("GET", "/nope", {}, None, access_token=TOKEN)
    assert status == HTTPStatus.NOT_FOUND
