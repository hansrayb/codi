#!/usr/bin/env python3
"""Standalone server untuk tes mobile API (`/api/v1/*`) — TANPA Telegram bot.

Pakai `core.mobile_api.mobile_handle` langsung. Untuk tes integrasi
Flutter app ↔ HTTP nyata tanpa menjalankan main.py penuh.

Fase B: server ini sekarang wire AuthService nyata (SQLite + JWT) kalau
`CODI_JWT_SECRET` di env, atau fallback ke bootstrap shared-token kalau
tidak. Untuk seed superadmin: jalankan `python -m scripts.seed_auth` dulu.

Jalankan dari dir backend/:
    python scripts/serve_mobile_api.py
    python scripts/serve_mobile_api.py --port 8787 --token rahasia --host 0.0.0.0

Dari Flutter (HP fisik pakai IP LAN laptop):
    flutter run \\
      --dart-define=API_BASE_URL=http://<ip-laptop>:8787/api/v1 \\
      --dart-define=CODI_SHARED_TOKEN=<token>
"""

from __future__ import annotations

import argparse
import json
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

# Pastikan paket backend (core/) bisa di-import saat dijalankan dari mana saja.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.auth.models import AuthContext  # noqa: E402
from core.auth.service import AuthService, AuthServiceError  # noqa: E402
from core.mobile_api import mobile_handle  # noqa: E402

_PREFIX = "/api/v1"

_PUBLIC_AUTH_PATHS = {"/auth/login", "/auth/login-biometric", "/auth/refresh"}


def build_handler(
    token: str,
    auth_service: AuthService | None = None,
    allow_bootstrap: bool = True,
):
    class Handler(BaseHTTPRequestHandler):
        server_version = "CodiMobileApiDev/1.0"

        def log_message(self, fmt, *args):  # noqa: A003
            print(f"  {self.command} {self.path} → {args[1]}")

        def do_GET(self):  # noqa: N802
            self._dispatch("GET")

        def do_POST(self):  # noqa: N802
            self._dispatch("POST")

        def do_PATCH(self):  # noqa: N802
            self._dispatch("PATCH")

        def do_DELETE(self):  # noqa: N802
            self._dispatch("DELETE")

        def _dispatch(self, method: str) -> None:
            split = urlsplit(self.path)
            if not split.path.startswith(_PREFIX):
                self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return

            sub = split.path[len(_PREFIX):] or "/"
            is_public = method == "POST" and sub in _PUBLIC_AUTH_PATHS
            auth_ctx: AuthContext | None = None
            if not is_public:
                auth_ctx = self._resolve_auth()
                if auth_ctx is None:
                    self._send(
                        HTTPStatus.UNAUTHORIZED,
                        {"error": {"code": "unauthorized", "message": "Token tidak valid."}},
                    )
                    return

            query = {k: v[0] for k, v in parse_qs(split.query).items()}
            body = None
            if method in {"POST", "PATCH", "DELETE"}:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length else b""
                if raw:
                    try:
                        body = json.loads(raw.decode("utf-8"))
                    except json.JSONDecodeError:
                        self._send(
                            HTTPStatus.BAD_REQUEST,
                            {"error": {"code": "invalid_json", "message": "Body bukan JSON."}},
                        )
                        return

            status, payload = mobile_handle(
                method,
                sub,
                query,
                body,
                auth_ctx=auth_ctx,
                auth_service=auth_service,
            )
            self._send(status, payload)

        def _resolve_auth(self) -> AuthContext | None:
            header = (self.headers.get("Authorization") or "").strip()
            if not header.lower().startswith("bearer "):
                return None
            bearer = header[7:].strip()
            if not bearer:
                return None
            if auth_service is not None:
                try:
                    return auth_service.verify_access_token(bearer)
                except AuthServiceError:
                    pass
            if allow_bootstrap and token and bearer == token:
                return AuthContext(
                    account_id="bootstrap",
                    email="bootstrap@codi",
                    role_slug="bootstrap",
                    scopes=("dashboard:read", "insight:read", "chat:use"),
                    is_bootstrap=True,
                )
            return None

        def _send(self, status: HTTPStatus, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Dev server mobile API Codi")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--token", default="dev-token")
    args = parser.parse_args()

    # Wire AuthService kalau .env punya CODI_JWT_SECRET. Tanpa itu, server tetap
    # jalan dengan bootstrap shared-token (login email akan kembalikan 503).
    auth_service: AuthService | None = None
    try:
        from config import load_settings  # noqa: WPS433 (lazy import)
        from core.auth import AuthDb, JwtHelper

        settings = load_settings()
        if settings.codi_jwt_secret:
            db = AuthDb.connect(settings.auth_db_path)
            db.seed_default_roles()
            jwt = JwtHelper(
                secret=settings.codi_jwt_secret,
                access_ttl_minutes=settings.codi_jwt_access_ttl_minutes,
                refresh_ttl_days=settings.codi_jwt_refresh_ttl_days,
            )
            auth_service = AuthService(db, jwt)
            print(f"[auth] AuthService aktif (db={settings.auth_db_path})")
        else:
            print("[auth] CODI_JWT_SECRET kosong — hanya bootstrap shared-token")
    except Exception as exc:  # noqa: BLE001
        print(f"[auth] gagal init ({exc}); fallback bootstrap shared-token saja")

    handler = build_handler(args.token, auth_service=auth_service)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Mobile API dev server → http://{args.host}:{args.port}{_PREFIX}")
    print(f"Bootstrap token (Bearer fallback): {args.token}")
    print("Tekan Ctrl+C untuk berhenti.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDihentikan.")
        server.shutdown()


if __name__ == "__main__":
    main()
