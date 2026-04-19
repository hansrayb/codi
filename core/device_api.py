"""HTTP API for device-agent register and heartbeat calls."""

from __future__ import annotations

import json
import threading
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

from core.device_registry import (
    DeviceRegistryError,
    DeviceRegistryManager,
    parse_device_registration,
)
from core.device_tasks import DeviceTaskError, DeviceTaskQueue


class DeviceApiServer:
    """Serve a small authenticated HTTP API for device register/heartbeat."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        shared_token: str,
        registry: DeviceRegistryManager,
        logger,
        task_queue: DeviceTaskQueue | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._shared_token = shared_token
        self._registry = registry
        self._task_queue = task_queue
        self._logger = logger
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._notify_fn_cell: list[Callable[[str], None] | None] = [None]

    def set_notify_fn(self, fn: Callable[[str], None]) -> None:
        """Set a thread-safe callback to send Telegram notifications."""

        self._notify_fn_cell[0] = fn

    def start(self) -> None:
        """Start the device API server in a background thread."""

        if self._server is not None:
            return
        handler_cls = self._build_handler_class()
        server = ThreadingHTTPServer((self._host, self._port), handler_cls)
        server.daemon_threads = True
        self._server = server
        self._thread = threading.Thread(
            target=server.serve_forever,
            name="codi-device-api",
            daemon=True,
        )
        self._thread.start()
        self._logger.info(
            "action=device_api_started | host=%s | port=%s",
            self._host,
            server.server_port,
        )

    @property
    def bound_port(self) -> int:
        """Return the currently bound TCP port, or the configured one if not started."""

        if self._server is None:
            return self._port
        return int(self._server.server_port)

    def stop(self) -> None:
        """Stop the device API server if it is running."""

        server = self._server
        if server is None:
            return
        server.shutdown()
        server.server_close()
        self._server = None
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=2)
        self._logger.info("action=device_api_stopped")

    def _build_handler_class(self):
        registry = self._registry
        task_queue = self._task_queue
        logger = self._logger
        shared_token = self._shared_token
        notify_fn_cell = self._notify_fn_cell

        class Handler(BaseHTTPRequestHandler):
            server_version = "CodiDeviceAPI/1.0"

            def do_GET(self) -> None:  # noqa: N802
                if self.path != "/healthz":
                    self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
                    return
                self._send_json(HTTPStatus.OK, {"ok": True, "status": "ok"})

            def do_POST(self) -> None:  # noqa: N802
                if not self._is_authorized():
                    self._send_json(
                        HTTPStatus.UNAUTHORIZED,
                        {"ok": False, "error": "unauthorized"},
                    )
                    return

                if self.path == "/api/device/tasks/poll":
                    self._handle_task_poll()
                    return
                if self.path == "/api/device/tasks/result":
                    self._handle_task_result()
                    return
                if self.path == "/api/device/tasks/enqueue":
                    self._handle_task_enqueue()
                    return

                if self.path not in {"/api/device/register", "/api/device/heartbeat"}:
                    self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
                    return

                try:
                    payload = self._read_json_body()
                    registration = parse_device_registration(payload)
                    if self.path == "/api/device/register":
                        record = registry.register_device(
                            registration,
                            remote_addr=self.client_address[0] if self.client_address else None,
                        )
                        event = "device_register"
                    else:
                        record = registry.record_heartbeat(
                            registration,
                            remote_addr=self.client_address[0] if self.client_address else None,
                        )
                        event = "device_heartbeat"
                except DeviceRegistryError as exc:
                    self._send_json(
                        HTTPStatus.BAD_REQUEST,
                        {"ok": False, "error": str(exc)},
                    )
                    return
                except json.JSONDecodeError:
                    self._send_json(
                        HTTPStatus.BAD_REQUEST,
                        {"ok": False, "error": "invalid_json"},
                    )
                    return
                except Exception:
                    logger.exception("action=device_api_request_failed | path=%s", self.path)
                    self._send_json(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        {"ok": False, "error": "internal_error"},
                    )
                    return

                logger.info(
                    "action=%s | device_id=%s | ip=%s",
                    event,
                    record.device_id,
                    self.client_address[0] if self.client_address else "-",
                )
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "device_id": record.device_id,
                        "label": record.label,
                    },
                )

            def _handle_task_poll(self) -> None:
                if task_queue is None:
                    self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "task_queue_disabled"})
                    return
                try:
                    payload = self._read_json_body()
                    registration = parse_device_registration(payload)
                    registry.record_heartbeat(
                        registration,
                        remote_addr=self.client_address[0] if self.client_address else None,
                    )
                    task = task_queue.poll(
                        device_id=registration.device_id,
                        capabilities=registration.capabilities,
                    )
                except DeviceRegistryError as exc:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                    return
                except json.JSONDecodeError:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid_json"})
                    return
                except Exception:
                    logger.exception("action=device_task_poll_failed")
                    self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": "internal_error"})
                    return

                if task is None:
                    self._send_json(HTTPStatus.OK, {"ok": True, "task": None})
                    return
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "task": {
                            "task_id": task.task_id,
                            "kind": task.kind,
                            "payload": task.payload,
                        },
                    },
                )

            def _handle_task_result(self) -> None:
                if task_queue is None:
                    self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "task_queue_disabled"})
                    return
                try:
                    payload = self._read_json_body()
                    device_id = str(payload.get("device_id") or "").strip()
                    task_id = str(payload.get("task_id") or "").strip()
                    ok = bool(payload.get("ok"))
                    result = payload.get("result")
                    error_text = payload.get("error")
                    if not device_id or not task_id:
                        raise DeviceTaskError("device_id dan task_id wajib diisi.")
                    task = task_queue.complete(
                        device_id=device_id,
                        task_id=task_id,
                        ok=ok,
                        result=result if isinstance(result, dict) else {},
                        error=str(error_text) if error_text else None,
                    )
                except DeviceTaskError as exc:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                    return
                except json.JSONDecodeError:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid_json"})
                    return
                except Exception:
                    logger.exception("action=device_task_result_failed")
                    self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": "internal_error"})
                    return

                logger.info(
                    "action=device_task_result | device_id=%s | task=%s | status=%s",
                    task.device_id,
                    task.task_id,
                    task.status,
                )
                if task.kind == "self_update":
                    _notify_self_update(task, registry, notify_fn_cell[0])
                self._send_json(HTTPStatus.OK, {"ok": True, "task_id": task.task_id, "status": task.status})

            def _handle_task_enqueue(self) -> None:
                if task_queue is None:
                    self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "task_queue_disabled"})
                    return
                try:
                    payload = self._read_json_body()
                    device_id_raw = str(payload.get("device_id") or "").strip()
                    kind = str(payload.get("kind") or "").strip()
                    task_payload = payload.get("payload", {})
                    if not device_id_raw or not kind:
                        raise DeviceTaskError("device_id dan kind wajib diisi.")
                    if not isinstance(task_payload, dict):
                        task_payload = {}
                    if device_id_raw == "all":
                        device_ids = registry.get_all_device_ids()
                    else:
                        device_ids = [device_id_raw]
                    created = []
                    for dev_id in device_ids:
                        task = task_queue.enqueue(
                            device_id=dev_id,
                            requested_by=0,
                            kind=kind,
                            payload=task_payload,
                        )
                        created.append({"device_id": dev_id, "task_id": task.task_id})
                        logger.info(
                            "action=device_task_enqueue_api | device_id=%s | task=%s | kind=%s",
                            dev_id,
                            task.task_id,
                            kind,
                        )
                except DeviceTaskError as exc:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                    return
                except json.JSONDecodeError:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid_json"})
                    return
                except Exception:
                    logger.exception("action=device_task_enqueue_failed")
                    self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": "internal_error"})
                    return
                self._send_json(HTTPStatus.OK, {"ok": True, "tasks": created})

            def log_message(self, fmt: str, *args) -> None:
                return

            def _read_json_body(self) -> dict[str, object]:
                content_length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(content_length)
                if not raw:
                    raise DeviceRegistryError("Body request kosong.")
                payload = json.loads(raw.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise DeviceRegistryError("Body JSON harus berupa object.")
                return payload

            def _is_authorized(self) -> bool:
                auth_header = (self.headers.get("Authorization") or "").strip()
                if auth_header.startswith("Bearer "):
                    return auth_header[7:].strip() == shared_token
                token_header = (self.headers.get("X-Codi-Agent-Token") or "").strip()
                return token_header == shared_token

            def _send_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
                body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
                self.send_response(status.value)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Handler


def _notify_self_update(task, registry: DeviceRegistryManager, notify_fn: Callable[[str], None] | None) -> None:
    if notify_fn is None:
        return
    device_record = registry.resolve_device(task.device_id)
    label = escape(device_record.label if device_record else task.device_id)
    device_id = escape(task.device_id)
    if task.status == "completed":
        output = str((task.result or {}).get("output") or "").strip()
        output_line = f"\n\n<code>{escape(output[:500])}</code>" if output else ""
        text = (
            f"🔄 <b>Agent diperbarui</b>\n\n"
            f"Device: <b>{label}</b> (<code>{device_id}</code>){output_line}"
        )
    else:
        error = escape((task.error or "error tidak diketahui")[:300])
        text = (
            f"❌ <b>Agent gagal diperbarui</b>\n\n"
            f"Device: <b>{label}</b> (<code>{device_id}</code>)\n"
            f"Error: <code>{error}</code>"
        )
    try:
        notify_fn(text)
    except Exception:
        pass
