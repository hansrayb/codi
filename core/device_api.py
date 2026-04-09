"""HTTP API for device-agent register and heartbeat calls."""

from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from core.device_registry import (
    DeviceRegistryError,
    DeviceRegistryManager,
    parse_device_registration,
)


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
    ) -> None:
        self._host = host
        self._port = port
        self._shared_token = shared_token
        self._registry = registry
        self._logger = logger
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

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
        logger = self._logger
        shared_token = self._shared_token

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
