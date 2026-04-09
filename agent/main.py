"""Simple device agent that registers itself and sends periodic heartbeats."""

from __future__ import annotations

import json
import os
import platform
import socket
import sys
import time
from urllib import error, request


def main() -> None:
    center_url = _require_env("CODI_CENTER_URL").rstrip("/")
    shared_token = _require_env("CODI_DEVICE_API_TOKEN")
    interval_seconds = _parse_positive_int(
        os.getenv("CODI_DEVICE_HEARTBEAT_INTERVAL", "30"),
        "CODI_DEVICE_HEARTBEAT_INTERVAL",
    )

    payload = _build_registration_payload()
    _post_json(f"{center_url}/api/device/register", payload, shared_token)
    print(
        f"Device {payload['device_id']} terdaftar ke {center_url}. "
        f"Heartbeat tiap {interval_seconds} detik.",
        flush=True,
    )

    while True:
        time.sleep(interval_seconds)
        _post_json(f"{center_url}/api/device/heartbeat", payload, shared_token)
        print(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] heartbeat sent for {payload['device_id']}",
            flush=True,
        )


def _build_registration_payload() -> dict[str, object]:
    hostname = socket.gethostname().strip() or "unknown-host"
    device_id = _normalize_device_id(
        os.getenv("CODI_DEVICE_ID")
        or hostname
    )
    label = (os.getenv("CODI_DEVICE_LABEL") or hostname).strip() or hostname
    device_type = (
        os.getenv("CODI_DEVICE_TYPE")
        or _default_device_type()
    ).strip().lower() or "desktop"
    platform_name = (os.getenv("CODI_DEVICE_PLATFORM") or platform.platform()).strip()
    capabilities = _split_csv(
        os.getenv("CODI_DEVICE_CAPABILITIES", _default_capabilities(device_type))
    )
    agent_version = (os.getenv("CODI_DEVICE_AGENT_VERSION") or "v1").strip() or "v1"

    return {
        "device_id": device_id,
        "label": label,
        "device_type": device_type,
        "hostname": hostname,
        "platform": platform_name,
        "capabilities": capabilities,
        "agent_version": agent_version,
    }


def _post_json(url: str, payload: dict[str, object], shared_token: str) -> None:
    raw_payload = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    req = request.Request(
        url,
        data=raw_payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {shared_token}",
        },
    )
    try:
        with request.urlopen(req, timeout=15) as response:
            status_code = response.getcode()
            if status_code >= 400:
                raise RuntimeError(f"HTTP {status_code}")
    except error.HTTPError as exc:
        raise SystemExit(f"Device agent gagal menghubungi pusat: HTTP {exc.code}") from exc
    except error.URLError as exc:
        raise SystemExit(f"Device agent gagal menghubungi pusat: {exc.reason}") from exc


def _default_device_type() -> str:
    if platform.system().lower() == "linux" and os.getenv("DISPLAY"):
        return "desktop"
    return "server"


def _default_capabilities(device_type: str) -> str:
    if device_type == "server":
        return "shell,repo,systemd"
    return "shell,repo,system_activity,screenshot,desktop"


def _require_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise SystemExit(f"{name} wajib diisi.")
    return value


def _split_csv(raw: str) -> list[str]:
    seen: dict[str, None] = {}
    for item in raw.split(","):
        normalized = item.strip().lower()
        if normalized:
            seen[normalized] = None
    return list(seen.keys())


def _normalize_device_id(value: str) -> str:
    normalized = "".join(
        char.lower() if char.isalnum() or char in "._:-" else "-"
        for char in value.strip()
    ).strip("-")
    if not normalized:
        raise SystemExit("CODI_DEVICE_ID tidak valid.")
    return normalized


def _parse_positive_int(raw: str, name: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} harus berupa angka bulat positif.") from exc
    if value <= 0:
        raise SystemExit(f"{name} harus lebih besar dari 0.")
    return value


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
