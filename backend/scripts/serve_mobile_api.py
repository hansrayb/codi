#!/usr/bin/env python3
"""Standalone server untuk tes mobile API (`/api/v1/*`) — TANPA Telegram bot.

Pakai `core.mobile_api.mobile_handle` langsung. Untuk tes integrasi
Flutter app ↔ HTTP nyata tanpa menjalankan main.py penuh / .env.

Jalankan dari dir backend/:
    python scripts/serve_mobile_api.py
    python scripts/serve_mobile_api.py --port 8787 --token rahasia --host 0.0.0.0

Dari Flutter (HP fisik pakai IP LAN laptop):
    flutter run \\
      --dart-define=API_BASE_URL=http://<ip-laptop>:8787/api/v1 \\
      --dart-define=CODI_SHARED_TOKEN=<token>

Login app akan mengembalikan token yang sama (shared-token), request
berikutnya lolos auth otomatis.
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

from core.mobile_api import mobile_handle  # noqa: E402

_PREFIX = "/api/v1"


def build_handler(token: str):
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

        def _dispatch(self, method: str) -> None:
            split = urlsplit(self.path)
            if not split.path.startswith(_PREFIX):
                self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return

            sub = split.path[len(_PREFIX):] or "/"
            require_auth = not (method == "POST" and sub == "/auth/login")
            if require_auth and not self._authorized():
                self._send(
                    HTTPStatus.UNAUTHORIZED,
                    {"error": {"code": "unauthorized", "message": "Token tidak valid."}},
                )
                return

            query = {k: v[0] for k, v in parse_qs(split.query).items()}
            body = None
            if method in {"POST", "PATCH"}:
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
                method, sub, query, body, access_token=token
            )
            self._send(status, payload)

        def _authorized(self) -> bool:
            auth = (self.headers.get("Authorization") or "").strip()
            if auth.startswith("Bearer "):
                return auth[7:].strip() == token
            return False

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

    server = ThreadingHTTPServer((args.host, args.port), build_handler(args.token))
    print(f"Mobile API dev server → http://{args.host}:{args.port}{_PREFIX}")
    print(f"Token (Bearer): {args.token}")
    print("Tekan Ctrl+C untuk berhenti.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDihentikan.")
        server.shutdown()


if __name__ == "__main__":
    main()
