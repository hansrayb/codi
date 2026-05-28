"""HTTP API for device-agent register and heartbeat calls."""

from __future__ import annotations

import asyncio
import json
import queue
import threading
import uuid
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Optional
from urllib.parse import parse_qs, urlsplit

from core.auth.models import AuthContext
from core.auth.service import AuthService, AuthServiceError
from core.device_registry import (
    DeviceRegistryError,
    DeviceRegistryManager,
    parse_device_registration,
)
from core.device_tasks import DeviceTaskError, DeviceTaskQueue
from core.mobile_api import mobile_handle

# Prefix endpoint app mobile (Emas Berlian Insight).
_MOBILE_PREFIX = "/api/v1"

# Sentinel pushed onto the SSE bridge queue to signal the stream is finished.
_SSE_DONE = object()
# Heartbeat interval (seconds) when no token arrives, keeps proxies from idling out.
_SSE_HEARTBEAT_SECONDS = 15


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
        auth_service: AuthService | None = None,
        allow_bootstrap_token: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._shared_token = shared_token
        self._registry = registry
        self._task_queue = task_queue
        self._logger = logger
        self._auth_service = auth_service
        self._allow_bootstrap_token = allow_bootstrap_token
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._notify_fn_cell: list[Callable[[str], None] | None] = [None]
        self._chat_fn_cell: list[Optional[Callable[[str, int], str]]] = [None]
        # Streaming chat: a coroutine factory + the asyncio loop + session store.
        # stream_factory(session_id, message, user_id, on_token, cancel_event) -> coroutine
        self._chat_stream_factory_cell: list[Optional[Callable[..., Any]]] = [None]
        self._loop_cell: list[Optional[asyncio.AbstractEventLoop]] = [None]
        self._session_store_cell: list[Any] = [None]

    def set_notify_fn(self, fn: Callable[[str], None]) -> None:
        """Set a thread-safe callback to send Telegram notifications."""

        self._notify_fn_cell[0] = fn

    def set_chat_fn(self, fn: Callable[[str, int, str], str]) -> None:
        """Set a sync callable (message, user_id, scope) -> reply for the /api/chat endpoint."""

        self._chat_fn_cell[0] = fn

    def set_chat_stream_factory(self, fn: Callable[..., Any]) -> None:
        """Set a coroutine factory for SSE streaming.

        Signature: factory(session_id, message, user_id, on_token, cancel_event)
        -> awaitable returning the full reply text. ``on_token`` is an async
        callable invoked per text delta; ``cancel_event`` is an asyncio.Event set
        when the client disconnects.
        """

        self._chat_stream_factory_cell[0] = fn

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Provide the asyncio loop used to schedule streaming coroutines."""

        self._loop_cell[0] = loop

    def set_session_store(self, store: Any) -> None:
        """Provide the CodiSessionStore for DELETE-based session clearing."""

        self._session_store_cell[0] = store

    def start(self) -> None:
        """Start the device API server in a background thread."""

        if self._server is not None:
            return
        handler_cls = self._build_handler_class()
        server = ThreadingHTTPServer((self._host, self._port), handler_cls)
        server.daemon_threads = True  # noqa: FBT003
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
        chat_fn_cell = self._chat_fn_cell
        chat_stream_factory_cell = self._chat_stream_factory_cell
        loop_cell = self._loop_cell
        session_store_cell = self._session_store_cell
        auth_service = self._auth_service
        allow_bootstrap = self._allow_bootstrap_token

        class Handler(BaseHTTPRequestHandler):
            server_version = "CodiDeviceAPI/1.0"

            def do_GET(self) -> None:  # noqa: N802
                split = urlsplit(self.path)
                if split.path.startswith(_MOBILE_PREFIX):
                    self._handle_mobile("GET", split, require_auth=True)
                    return
                if split.path != "/healthz":
                    self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
                    return
                self._send_json(HTTPStatus.OK, {"ok": True, "status": "ok"})

            def do_PATCH(self) -> None:  # noqa: N802
                split = urlsplit(self.path)
                if split.path.startswith(_MOBILE_PREFIX):
                    self._handle_mobile("PATCH", split, require_auth=True)
                    return
                self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})

            def do_POST(self) -> None:  # noqa: N802
                split = urlsplit(self.path)
                # Login mobile endpoints tak butuh token (token belum ada).
                if split.path in {
                    f"{_MOBILE_PREFIX}/auth/login",
                    f"{_MOBILE_PREFIX}/auth/login-biometric",
                    f"{_MOBILE_PREFIX}/auth/refresh",
                }:
                    self._handle_mobile("POST", split, require_auth=False)
                    return

                if split.path.startswith(_MOBILE_PREFIX):
                    # Mobile endpoint authed — auth context di-resolve di
                    # _handle_mobile (JWT account ATAU bootstrap shared-token).
                    self._handle_mobile("POST", split, require_auth=True)
                    return

                if not self._is_authorized():
                    self._send_json(
                        HTTPStatus.UNAUTHORIZED,
                        {"ok": False, "error": "unauthorized"},
                    )
                    return

                if self.path == "/api/chat":
                    accept = (self.headers.get("Accept") or "").lower()
                    if (
                        "text/event-stream" in accept
                        and chat_stream_factory_cell[0] is not None
                        and loop_cell[0] is not None
                    ):
                        self._handle_chat_stream()
                        return
                    self._handle_chat()
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

            def do_DELETE(self) -> None:  # noqa: N802
                split = urlsplit(self.path)
                if split.path.startswith(_MOBILE_PREFIX):
                    self._handle_mobile("DELETE", split, require_auth=True)
                    return
                if not self._is_authorized():
                    self._send_json(
                        HTTPStatus.UNAUTHORIZED,
                        {"ok": False, "error": "unauthorized"},
                    )
                    return
                prefix = "/api/chat/session/"
                if not self.path.startswith(prefix):
                    self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
                    return
                sid = self.path[len(prefix):].strip()
                store = session_store_cell[0]
                if sid and store is not None:
                    try:
                        store.delete(sid)
                    except Exception:
                        logger.exception("action=session_delete_failed | sid=%s", sid)
                self.send_response(HTTPStatus.NO_CONTENT.value)
                self.end_headers()

            def _handle_chat_stream(self) -> None:
                factory = chat_stream_factory_cell[0]
                loop = loop_cell[0]
                store = session_store_cell[0]
                if factory is None or loop is None:
                    self._send_json(
                        HTTPStatus.SERVICE_UNAVAILABLE,
                        {"ok": False, "error": "chat_stream_not_available"},
                    )
                    return

                # Parse + validate BEFORE writing any SSE byte so we can still
                # return a normal JSON error status on bad input.
                try:
                    payload = self._read_json_body()
                except json.JSONDecodeError:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid_json"})
                    return
                except DeviceRegistryError:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid_json"})
                    return
                message = str(payload.get("message") or "").strip()
                user_id = int(payload.get("user_id") or 0)
                session_id = str(payload.get("session_id") or "").strip()
                if not message:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "message_required"})
                    return
                if not session_id:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "session_required"})
                    return

                # Resolve the prior CLI thread for this dashboard session (history).
                prior_claude_sid = None
                if store is not None:
                    try:
                        prior_claude_sid = store.get_claude_session_id(session_id)
                    except Exception:
                        logger.exception("action=session_lookup_failed | sid=%s", session_id)

                # Open the SSE response.
                self.send_response(HTTPStatus.OK.value)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache, no-transform")
                self.send_header("Connection", "keep-alive")
                self.send_header("X-Accel-Buffering", "no")
                self.end_headers()

                frame_q: "queue.Queue[Any]" = queue.Queue()
                # asyncio.Event() calls get_event_loop() in Python 3.9, which
                # fails on a bare threading.Thread with no loop. Create it on
                # the asyncio loop thread instead.
                async def _mk_event() -> asyncio.Event:
                    return asyncio.Event()
                cancel_event: asyncio.Event = asyncio.run_coroutine_threadsafe(
                    _mk_event(), loop
                ).result(timeout=5)

                async def _on_token(delta: str) -> None:
                    frame_q.put(("token", delta))

                async def _drive() -> None:
                    try:
                        reply = await factory(
                            session_id=session_id,
                            message=message,
                            user_id=user_id,
                            on_token=_on_token,
                            claude_session_id=prior_claude_sid,
                            cancel_event=cancel_event,
                        )
                        # factory returns (text, new_claude_session_id)
                        new_sid = None
                        if isinstance(reply, tuple):
                            _text, new_sid = reply
                        if store is not None and new_sid:
                            try:
                                store.set_claude_session_id(session_id, new_sid)
                            except Exception:
                                logger.exception("action=session_persist_failed | sid=%s", session_id)
                        frame_q.put(("done", None))
                    except asyncio.TimeoutError:
                        frame_q.put(("error", ("timeout", "Codi belum selesai menjawab.")))
                    except FileNotFoundError:
                        frame_q.put(("error", ("internal", "Claude CLI tidak ditemukan.")))
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("action=chat_stream_failed | sid=%s", session_id)
                        frame_q.put(("error", ("internal", str(exc)[:200])))
                    finally:
                        frame_q.put(_SSE_DONE)

                future = asyncio.run_coroutine_threadsafe(_drive(), loop)

                # Emit meta frame first.
                meta = {"session_id": session_id, "message_id": str(uuid.uuid4())}
                if not self._sse_write(f"event: meta\ndata: {json.dumps(meta)}\n\n"):
                    loop.call_soon_threadsafe(cancel_event.set)
                    future.cancel()
                    return

                # Drain the bridge queue on this HTTP thread.
                while True:
                    try:
                        item = frame_q.get(timeout=_SSE_HEARTBEAT_SECONDS)
                    except queue.Empty:
                        if not self._sse_write(": ping\n\n"):
                            loop.call_soon_threadsafe(cancel_event.set)
                            break
                        continue
                    if item is _SSE_DONE:
                        break
                    kind, data = item
                    if kind == "token":
                        frame = f"event: token\ndata: {json.dumps({'delta': data})}\n\n"
                    elif kind == "done":
                        frame = "event: done\ndata: {\"finish_reason\":\"stop\"}\n\n"
                    elif kind == "error":
                        code, msg = data
                        frame = (
                            "event: error\n"
                            f"data: {json.dumps({'code': code, 'message': msg})}\n\n"
                        )
                    else:
                        continue
                    if not self._sse_write(frame):
                        # Client disconnected — cancel upstream so the LLM stops.
                        loop.call_soon_threadsafe(cancel_event.set)
                        break

            def _sse_write(self, frame: str) -> bool:
                """Write+flush an SSE frame. Returns False on client disconnect."""
                try:
                    self.wfile.write(frame.encode("utf-8"))
                    self.wfile.flush()
                    return True
                except (BrokenPipeError, ConnectionResetError, OSError):
                    return False

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

            def _handle_chat(self) -> None:
                chat_fn = chat_fn_cell[0]
                if chat_fn is None:
                    self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": "chat_not_available"})
                    return
                try:
                    payload = self._read_json_body()
                    message = str(payload.get("message") or "").strip()
                    user_id = int(payload.get("user_id") or 0)
                    scope = str(payload.get("scope") or "").strip()
                    if not message:
                        self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "message_required"})
                        return
                    reply = chat_fn(message, user_id, scope)
                    self._send_json(HTTPStatus.OK, {"ok": True, "reply": reply})
                except json.JSONDecodeError:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid_json"})
                except Exception:
                    logger.exception("action=chat_api_failed")
                    self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": "internal_error"})

            def log_message(self, fmt: str, *args) -> None:
                return

            def _handle_mobile(self, method: str, split, *, require_auth: bool) -> None:
                auth_ctx: AuthContext | None = None
                if require_auth:
                    auth_ctx = self._resolve_mobile_auth()
                    if auth_ctx is None:
                        self._send_json(
                            HTTPStatus.UNAUTHORIZED,
                            {"error": {"code": "unauthorized", "message": "Token tidak valid."}},
                        )
                        return
                sub_path = split.path[len(_MOBILE_PREFIX) :] or "/"
                query = {k: v[0] for k, v in parse_qs(split.query).items()}
                body: dict[str, Any] | None = None
                if method in {"POST", "PATCH", "DELETE"}:
                    try:
                        body = self._read_json_body()
                    except json.JSONDecodeError:
                        self._send_json(
                            HTTPStatus.BAD_REQUEST,
                            {"error": {"code": "invalid_json", "message": "Body bukan JSON valid."}},
                        )
                        return
                    except DeviceRegistryError:
                        body = None
                try:
                    status, payload = mobile_handle(
                        method,
                        sub_path,
                        query,
                        body,
                        auth_ctx=auth_ctx,
                        auth_service=auth_service,
                        chat_fn=chat_fn_cell[0],
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.exception("mobile_api error: %s", exc)
                    self._send_json(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        {"error": {"code": "internal", "message": "Kesalahan server."}},
                    )
                    return
                self._send_json(status, payload)

            def _resolve_mobile_auth(self) -> AuthContext | None:
                """Verifikasi token Authorization untuk endpoint mobile.

                Urutan: JWT (auth_service) → fallback bootstrap shared-token
                (kalau diizinkan dan match `shared_token`).
                """
                header = (self.headers.get("Authorization") or "").strip()
                if not header.lower().startswith("bearer "):
                    return None
                token = header[7:].strip()
                if not token:
                    return None
                if auth_service is not None:
                    try:
                        return auth_service.verify_access_token(token)
                    except AuthServiceError:
                        pass  # fall through to bootstrap fallback
                if allow_bootstrap and shared_token and token == shared_token:
                    return AuthContext(
                        account_id="bootstrap",
                        email="bootstrap@codi",
                        role_slug="bootstrap",
                        scopes=("dashboard:read", "insight:read", "chat:use"),
                        is_bootstrap=True,
                    )
                return None

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
