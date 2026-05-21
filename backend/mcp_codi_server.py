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
    if data:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
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

    return _err(f"Unknown tool: {name}")


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
