"""MCP server — exposes Codi bot state and HR system tools to Claude Code.

Run via stdio (Claude Code spawns this as a subprocess):
  python mcp_codi_server.py

Env vars (set in Claude Code settings.json or shell):
  CODI_API_URL          http://127.0.0.1:8787  (Codi device API base)
  CODI_API_TOKEN        shared token for Codi device API
  HR_API_URL            https://hrga-api.emasmini.co.id  (HR system base URL)
  HR_SERVICE_EMAIL      service account email (maps to 'username' field)
  HR_SERVICE_PASSWORD   service account password
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import threading
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, CallToolResult

# ── Config from env ────────────────────────────────────────────────────────────

CODI_API_URL = os.environ.get("CODI_API_URL", "http://127.0.0.1:8787").rstrip("/")
CODI_TOKEN = os.environ.get("CODI_API_TOKEN", "")
HR_API_URL = os.environ.get("HR_API_URL", "https://hrga-api.emasmini.co.id").rstrip("/")
HR_EMAIL = os.environ.get("HR_SERVICE_EMAIL", "")
HR_PASSWORD = os.environ.get("HR_SERVICE_PASSWORD", "")

# ── Shared state ───────────────────────────────────────────────────────────────

_hr_token: str | None = None
_hr_token_expiry: float = 0.0
_hr_token_lock = threading.Lock()


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def _http(method: str, url: str, body: dict | None = None, headers: dict | None = None) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    h = headers or {}
    # Cloudflare auto-block default urllib UA ("Python-urllib/...").
    # Set browser-like UA + X-Codi-Client agar lolos Bot Fight Mode.
    h.setdefault(
        "User-Agent",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Codi-MCP/1.0",
    )
    h.setdefault("Accept", "application/json")
    if data:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        msg = exc.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {method} {url}: {msg}") from exc


def _codi(method: str, path: str, body: dict | None = None) -> Any:
    headers = {}
    if CODI_TOKEN:
        headers["Authorization"] = f"Bearer {CODI_TOKEN}"
    return _http(method, f"{CODI_API_URL}{path}", body, headers)


def _hr_token() -> str:
    global _hr_token, _hr_token_expiry
    with _hr_token_lock:
        if _hr_token and time.time() < _hr_token_expiry:
            return _hr_token
        data = _http("POST", f"{HR_API_URL}/api/auth/login", {"username": HR_EMAIL, "password": HR_PASSWORD})
        tok = data.get("access_token") or data.get("token") or ""
        if not tok:
            raise RuntimeError("HR login did not return a token.")
        _hr_token = tok
        _hr_token_expiry = time.time() + 50 * 60
        return _hr_token


def _hr(method: str, path: str, body: dict | None = None) -> Any:
    return _http(method, f"{HR_API_URL}{path}", body, {"Authorization": f"Bearer {_hr_token()}"})


def _ok(data: Any) -> CallToolResult:
    if isinstance(data, (dict, list)):
        text = json.dumps(data, ensure_ascii=False, indent=2)
    else:
        text = str(data)
    return CallToolResult(content=[TextContent(type="text", text=text)])


def _err(msg: str) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=f"ERROR: {msg}")], isError=True)


# ── Tool definitions ───────────────────────────────────────────────────────────

TOOLS: list[Tool] = [
    Tool(
        name="codi_get_status",
        description="Get Codi bot status: active sessions, online devices, config summary.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="codi_send_message",
        description="Send a chat message to Codi bot on behalf of a user (uses /api/chat). Returns Codi's reply.",
        inputSchema={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Message to send"},
                "user_id": {"type": "integer", "description": "Telegram user ID"},
            },
            "required": ["message", "user_id"],
        },
    ),
    Tool(
        name="codi_get_devices",
        description="List all devices registered with Codi (online and offline).",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    # ── HR read ──
    Tool(
        name="hr_get_dashboard",
        description="Get HR dashboard summary: total employees, attendance rate, pending approvals.",
        inputSchema={"type": "object", "properties": {}, "required": []},
    ),
    Tool(
        name="hr_get_employees",
        description="List employees from HR system. Optionally filter by department or search term.",
        inputSchema={
            "type": "object",
            "properties": {
                "department": {"type": "string", "default": ""},
                "search": {"type": "string", "default": ""},
            },
            "required": [],
        },
    ),
    Tool(
        name="hr_get_attendance",
        description="Get attendance summary for a date range. Optionally filter by employee_id.",
        inputSchema={
            "type": "object",
            "properties": {
                "from_date": {"type": "string", "description": "YYYY-MM-DD"},
                "to_date": {"type": "string", "description": "YYYY-MM-DD"},
                "employee_id": {"type": "string", "default": ""},
            },
            "required": ["from_date", "to_date"],
        },
    ),
    Tool(
        name="hr_get_payroll_runs",
        description="List payroll runs. Optionally filter by year and month.",
        inputSchema={
            "type": "object",
            "properties": {
                "year": {"type": "integer"},
                "month": {"type": "integer"},
            },
            "required": [],
        },
    ),
    Tool(
        name="hr_get_payroll_items",
        description="Get payroll detail items (per-employee breakdown) for a payroll run.",
        inputSchema={
            "type": "object",
            "properties": {
                "run_id": {"type": "integer", "description": "Payroll run ID"},
            },
            "required": ["run_id"],
        },
    ),
    Tool(
        name="hr_get_leave_requests",
        description="Get leave requests. Filter by status (pending/approved/rejected) or employee_id.",
        inputSchema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "default": ""},
                "employee_id": {"type": "string", "default": ""},
            },
            "required": [],
        },
    ),
    Tool(
        name="hr_get_overtime_requests",
        description="Get overtime requests. Filter by status.",
        inputSchema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "default": ""},
            },
            "required": [],
        },
    ),
    # ── HR write ──
    Tool(
        name="hr_add_attendance_note",
        description="Add a status note to an employee's attendance record (e.g. mark as sick, WFH, etc.).",
        inputSchema={
            "type": "object",
            "properties": {
                "employee_id": {"type": "string"},
                "attendance_date": {"type": "string", "description": "YYYY-MM-DD"},
                "status": {"type": "string", "description": "e.g. 'sick', 'wfh', 'izin'"},
                "note": {"type": "string"},
            },
            "required": ["employee_id", "attendance_date", "status", "note"],
        },
    ),
    Tool(
        name="hr_update_leave_request",
        description="Approve or reject a leave request.",
        inputSchema={
            "type": "object",
            "properties": {
                "request_id": {"type": "integer"},
                "status": {"type": "string", "description": "'approved' or 'rejected'"},
                "note": {"type": "string", "default": ""},
            },
            "required": ["request_id", "status"],
        },
    ),
    Tool(
        name="hr_update_overtime_request",
        description="Approve or reject an overtime request.",
        inputSchema={
            "type": "object",
            "properties": {
                "request_id": {"type": "integer"},
                "action": {"type": "string", "description": "'approved' or 'rejected'"},
                "note": {"type": "string", "default": ""},
            },
            "required": ["request_id", "action"],
        },
    ),
    Tool(
        name="hr_create_payroll_run",
        description="Create a new payroll run for a given month/year and period.",
        inputSchema={
            "type": "object",
            "properties": {
                "year": {"type": "integer"},
                "month": {"type": "integer"},
                "period_start": {"type": "string", "description": "YYYY-MM-DD"},
                "period_end": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["year", "month", "period_start", "period_end"],
        },
    ),
    Tool(
        name="hr_send_payroll_emails",
        description="Send payroll slip emails for a payroll run. Optionally limit to specific employee IDs.",
        inputSchema={
            "type": "object",
            "properties": {
                "run_id": {"type": "integer"},
                "employee_ids": {"type": "array", "items": {"type": "string"}, "default": []},
            },
            "required": ["run_id"],
        },
    ),
    Tool(
        name="hr_finalize_payroll_run",
        description="Finalize (lock) a payroll run so no further changes can be made.",
        inputSchema={
            "type": "object",
            "properties": {
                "run_id": {"type": "integer"},
            },
            "required": ["run_id"],
        },
    ),
    # ── Lumbung business metrics (dashboard data dari NestJS via Codi) ──
    Tool(
        name="lumbung_dashboard_summary",
        description=(
            "Ringkasan operasional bisnis Lumbung (omzet, order, transaksi, "
            "stok, dll). Pakai saat user tanya 'kondisi hari ini', "
            "'ringkasan', 'omzet bulan ini'. Period: today/week/month/year."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "description": "today / week / month (default) / year",
                    "default": "month",
                },
            },
        },
    ),
    Tool(
        name="lumbung_dashboard_insight",
        description=(
            "KPI + komposisi omzet + AI analysis untuk Lumbung. Lebih detail "
            "dari summary. Period: today/week/month/year."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "default": "month",
                },
            },
        },
    ),
    # ── Agent-to-agent messaging (peer messaging via Codi broker) ──
    Tool(
        name="agent_send",
        description=(
            "Kirim pesan ke agent Claude Code lain (peer) lewat Codi broker. "
            "Pakai `thread_id` (string bebas) untuk konteks lanjutan. Return msg id."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "sender": {"type": "string", "description": "Nama agent pengirim (mis. 'laptop-hans')."},
                "recipient": {"type": "string", "description": "Nama agent penerima (mis. 'server-codi')."},
                "content": {"type": "string", "description": "Isi pesan."},
                "thread_id": {"type": "string", "description": "Opsional — pengelompok thread."},
            },
            "required": ["sender", "recipient", "content"],
        },
    ),
    Tool(
        name="agent_inbox",
        description="Ambil pesan unread untuk agent ini (auto mark read). Return list message.",
        inputSchema={
            "type": "object",
            "properties": {
                "recipient": {"type": "string", "description": "Nama agent ini."},
                "limit": {"type": "integer", "description": "Maks pesan (default 50).", "default": 50},
                "mark_read": {"type": "boolean", "description": "Auto mark as read (default true).", "default": True},
            },
            "required": ["recipient"],
        },
    ),
    Tool(
        name="agent_wait_reply",
        description=(
            "Block sampai ada pesan baru untuk agent (opsional di thread tertentu), "
            "atau timeout. Default timeout 60s, max 300s."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "recipient": {"type": "string"},
                "thread_id": {"type": "string"},
                "since_id": {"type": "integer", "default": 0},
                "timeout": {"type": "integer", "default": 60},
            },
            "required": ["recipient"],
        },
    ),
    Tool(
        name="agent_history",
        description="Riwayat percakapan: pakai thread_id atau pasangan peer_a + peer_b.",
        inputSchema={
            "type": "object",
            "properties": {
                "thread_id": {"type": "string"},
                "peer_a": {"type": "string"},
                "peer_b": {"type": "string"},
                "limit": {"type": "integer", "default": 100},
            },
        },
    ),
]


# ── Server ─────────────────────────────────────────────────────────────────────

server = Server("codi-hr-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        result = await _dispatch(name, arguments)
        return result.content
    except Exception as exc:
        return _err(str(exc)).content


async def _dispatch(name: str, args: dict) -> CallToolResult:
    # ── Codi tools ─────────────────────────────────────────────────────────────
    if name == "codi_get_status":
        try:
            devices = await asyncio.to_thread(_codi, "GET", "/api/device/list")
        except Exception:
            devices = {"error": "device API unavailable (is ENABLE_DEVICE_REGISTRY=true?)"}
        return _ok({"codi_api": CODI_API_URL, "hr_api": HR_API_URL, "devices": devices})

    if name == "codi_get_devices":
        data = await asyncio.to_thread(_codi, "GET", "/api/device/list")
        return _ok(data)

    if name == "codi_send_message":
        data = await asyncio.to_thread(
            _codi, "POST", "/api/chat",
            {"message": args["message"], "user_id": args["user_id"]},
        )
        return _ok(data)

    # ── HR read ────────────────────────────────────────────────────────────────
    if name == "hr_get_dashboard":
        return _ok(await asyncio.to_thread(_hr, "GET", "/api/dashboard/summary"))

    if name == "hr_get_employees":
        dept = args.get("department", "")
        search = args.get("search", "")
        params = {k: v for k, v in [("department", dept), ("search", search)] if v}
        path = "/api/employees" + ("?" + urllib.parse.urlencode(params) if params else "")
        return _ok(await asyncio.to_thread(_hr, "GET", path))

    if name == "hr_get_attendance":
        params: dict = {"start_date": args["from_date"], "end_date": args["to_date"]}
        if args.get("employee_id"):
            params["user_id"] = args["employee_id"]
        path = "/api/attendance?" + urllib.parse.urlencode(params)
        return _ok(await asyncio.to_thread(_hr, "GET", path))

    if name == "hr_get_payroll_runs":
        params = {k: v for k, v in [("year", args.get("year")), ("month", args.get("month"))] if v is not None}
        path = "/api/payroll/runs" + ("?" + urllib.parse.urlencode(params) if params else "")
        return _ok(await asyncio.to_thread(_hr, "GET", path))

    if name == "hr_get_payroll_items":
        path = f"/api/payroll/runs/{args['run_id']}/items"
        return _ok(await asyncio.to_thread(_hr, "GET", path))

    if name == "hr_get_leave_requests":
        params = {k: v for k, v in [("status", args.get("status", "")), ("employee_id", args.get("employee_id", ""))] if v}
        path = "/api/leave-requests" + ("?" + urllib.parse.urlencode(params) if params else "")
        return _ok(await asyncio.to_thread(_hr, "GET", path))

    if name == "hr_get_overtime_requests":
        status = args.get("status", "")
        path = "/api/overtime-requests" + (f"?status={status}" if status else "")
        return _ok(await asyncio.to_thread(_hr, "GET", path))

    # ── HR write ───────────────────────────────────────────────────────────────
    if name == "hr_add_attendance_note":
        return _ok(await asyncio.to_thread(_hr, "POST", "/api/attendance/notes", {
            "employee_id": args["employee_id"],
            "attendance_date": args["attendance_date"],
            "status": args["status"],
            "note": args["note"],
        }))

    if name == "hr_update_leave_request":
        body: dict = {"status": args["status"]}
        if args.get("note"):
            body["note"] = args["note"]
        path = f"/api/leave-requests/{args['request_id']}/status"
        return _ok(await asyncio.to_thread(_hr, "PUT", path, body))

    if name == "hr_update_overtime_request":
        body = {"status": args["action"]}
        if args.get("note"):
            body["note"] = args["note"]
        path = f"/api/overtime-requests/{args['request_id']}/status"
        return _ok(await asyncio.to_thread(_hr, "PUT", path, body))

    if name == "hr_create_payroll_run":
        return _ok(await asyncio.to_thread(_hr, "POST", "/api/payroll/run", {
            "year": args["year"],
            "month": args["month"],
            "period_start": args["period_start"],
            "period_end": args["period_end"],
        }))

    if name == "hr_send_payroll_emails":
        body = {"run_id": args["run_id"]}
        if args.get("employee_ids"):
            body["employee_id_list"] = args["employee_ids"]
        return _ok(await asyncio.to_thread(_hr, "POST", f"/api/payroll/runs/{args['run_id']}/email", body))

    if name == "hr_finalize_payroll_run":
        path = f"/api/payroll/runs/{args['run_id']}/finalize"
        return _ok(await asyncio.to_thread(_hr, "POST", path, {}))

    # ── Lumbung business metrics ──────────────────────────────────────────────
    if name == "lumbung_dashboard_summary":
        period = args.get("period", "month")
        return _ok(await asyncio.to_thread(
            _codi, "GET", f"/api/v1/dashboard/summary?period={period}"
        ))

    if name == "lumbung_dashboard_insight":
        period = args.get("period", "month")
        return _ok(await asyncio.to_thread(
            _codi, "GET", f"/api/v1/dashboard/insight?period={period}"
        ))

    # ── Agent-to-agent messaging ──────────────────────────────────────────────
    if name == "agent_send":
        body = {
            "sender": args["sender"],
            "recipient": args["recipient"],
            "content": args["content"],
        }
        if args.get("thread_id"):
            body["thread_id"] = args["thread_id"]
        return _ok(await asyncio.to_thread(_codi, "POST", "/api/v1/agent/send", body))

    if name == "agent_inbox":
        body = {
            "recipient": args["recipient"],
            "limit": args.get("limit", 50),
            "mark_read": args.get("mark_read", True),
        }
        return _ok(await asyncio.to_thread(_codi, "POST", "/api/v1/agent/inbox", body))

    if name == "agent_wait_reply":
        body: dict[str, Any] = {
            "recipient": args["recipient"],
            "since_id": args.get("since_id", 0),
            "timeout": args.get("timeout", 60),
        }
        if args.get("thread_id"):
            body["thread_id"] = args["thread_id"]
        return _ok(await asyncio.to_thread(_codi, "POST", "/api/v1/agent/wait", body))

    if name == "agent_history":
        body = {"limit": args.get("limit", 100)}
        if args.get("thread_id"):
            body["thread_id"] = args["thread_id"]
        if args.get("peer_a"):
            body["peer_a"] = args["peer_a"]
        if args.get("peer_b"):
            body["peer_b"] = args["peer_b"]
        return _ok(await asyncio.to_thread(_codi, "POST", "/api/v1/agent/history", body))

    return _err(f"Unknown tool: {name}")


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
