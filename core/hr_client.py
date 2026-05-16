"""HTTP client for the HR/payroll system REST API."""

from __future__ import annotations

import asyncio
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class HRClientError(Exception):
    """Raised when an HR API call fails."""


class HRClient:
    """Async-friendly HTTP client for the HR system, using a service account JWT."""

    def __init__(self, base_url: str, service_email: str, service_password: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._email = service_email
        self._password = service_password
        self._token: str | None = None
        self._token_expiry: float = 0.0
        self._lock = threading.Lock()

    # ── Authentication ────────────────────────────────────────────────────────

    def _get_token(self) -> str:
        with self._lock:
            if self._token and time.time() < self._token_expiry:
                return self._token
            payload = json.dumps({"email": self._email, "password": self._password}).encode()
            req = urllib.request.Request(
                f"{self._base_url}/api/auth/login",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())
            except urllib.error.HTTPError as exc:
                raise HRClientError(f"HR auth failed: {exc.code} {exc.reason}") from exc
            except Exception as exc:
                raise HRClientError(f"HR auth error: {exc}") from exc
            self._token = data.get("access_token") or data.get("token") or ""
            if not self._token:
                raise HRClientError("HR login did not return a token.")
            self._token_expiry = time.time() + 50 * 60  # assume 60m JWT, refresh at 50m
            return self._token

    def _request(self, method: str, path: str, body: dict | None = None) -> Any:
        token = self._get_token()
        url = f"{self._base_url}{path}"
        data = json.dumps(body).encode() if body is not None else None
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}
        if data:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode(errors="replace")
            raise HRClientError(f"HR API {method} {path} → {exc.code}: {body_text}") from exc
        except Exception as exc:
            raise HRClientError(f"HR API error: {exc}") from exc

    async def _async(self, method: str, path: str, body: dict | None = None) -> Any:
        return await asyncio.to_thread(self._request, method, path, body)

    # ── Read endpoints ────────────────────────────────────────────────────────

    async def get_dashboard(self) -> dict:
        return await self._async("GET", "/api/dashboard/summary")

    async def get_employees(self, department: str = "", search: str = "") -> list:
        params = urllib.parse.urlencode({k: v for k, v in [("department", department), ("search", search)] if v})
        path = f"/api/employees{'?' + params if params else ''}"
        result = await self._async("GET", path)
        return result if isinstance(result, list) else result.get("items", result)

    async def get_attendance_summary(self, from_date: str, to_date: str, employee_id: str = "") -> Any:
        params = {"from_date": from_date, "to_date": to_date}
        if employee_id:
            params["employee_id"] = employee_id
        path = "/api/attendance/summary?" + urllib.parse.urlencode(params)
        return await self._async("GET", path)

    async def get_payroll_runs(self, year: int | None = None, month: int | None = None) -> list:
        params = {k: v for k, v in [("year", year), ("month", month)] if v is not None}
        path = "/api/payroll/runs" + ("?" + urllib.parse.urlencode(params) if params else "")
        result = await self._async("GET", path)
        return result if isinstance(result, list) else result.get("items", result)

    async def get_payroll_items(self, run_id: int) -> list:
        result = await self._async("GET", f"/api/payroll/runs/{run_id}/items")
        return result if isinstance(result, list) else result.get("items", result)

    async def get_leave_requests(self, status: str = "", employee_id: str = "") -> list:
        params = {k: v for k, v in [("status", status), ("employee_id", employee_id)] if v}
        path = "/api/leave/requests" + ("?" + urllib.parse.urlencode(params) if params else "")
        result = await self._async("GET", path)
        return result if isinstance(result, list) else result.get("items", result)

    async def get_overtime_requests(self, status: str = "") -> list:
        path = "/api/overtime/requests" + (f"?status={status}" if status else "")
        result = await self._async("GET", path)
        return result if isinstance(result, list) else result.get("items", result)

    # ── Write endpoints ───────────────────────────────────────────────────────

    async def add_attendance_note(
        self, employee_id: str, attendance_date: str, status: str, note: str
    ) -> dict:
        return await self._async("POST", "/api/attendance/status-note", {
            "employee_id": employee_id,
            "attendance_date": attendance_date,
            "status": status,
            "note": note,
        })

    async def update_leave_request(self, request_id: int, status: str, note: str = "") -> dict:
        body: dict = {"status": status}
        if note:
            body["note"] = note
        return await self._async("PATCH", f"/api/leave/requests/{request_id}", body)

    async def update_overtime_request(self, request_id: int, action: str, note: str = "") -> dict:
        body: dict = {"hr_status": action}
        if note:
            body["note"] = note
        return await self._async("PATCH", f"/api/overtime/requests/{request_id}", body)

    async def create_payroll_run(
        self, year: int, month: int, period_start: str, period_end: str
    ) -> dict:
        return await self._async("POST", "/api/payroll/runs", {
            "year": year,
            "month": month,
            "period_start": period_start,
            "period_end": period_end,
        })

    async def send_payroll_emails(self, run_id: int, employee_ids: list[str] | None = None) -> dict:
        body: dict = {"run_id": run_id}
        if employee_ids:
            body["employee_id_list"] = employee_ids
        return await self._async("POST", "/api/payroll/email", body)

    async def finalize_payroll_run(self, run_id: int) -> dict:
        return await self._async("POST", f"/api/payroll/runs/{run_id}/finalize", {})
