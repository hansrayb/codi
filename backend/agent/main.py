"""Simple device agent that registers itself and sends periodic heartbeats."""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import socket
import sqlite3
import sys
import time
from pathlib import Path
from urllib import error, request


def main() -> None:
    center_url = _require_env("CODI_CENTER_URL").rstrip("/")
    shared_token = _require_env("CODI_DEVICE_API_TOKEN")
    interval_seconds = _parse_positive_int(
        os.getenv("CODI_DEVICE_HEARTBEAT_INTERVAL", "30"),
        "CODI_DEVICE_HEARTBEAT_INTERVAL",
    )
    task_poll_interval_seconds = _parse_positive_int(
        os.getenv("CODI_DEVICE_TASK_POLL_INTERVAL", "5"),
        "CODI_DEVICE_TASK_POLL_INTERVAL",
    )

    payload = _build_registration_payload()
    _post_json(f"{center_url}/api/device/register", payload, shared_token)
    print(
        f"Device {payload['device_id']} terdaftar ke {center_url}. "
        f"Heartbeat tiap {interval_seconds} detik, poll task tiap {task_poll_interval_seconds} detik.",
        flush=True,
    )

    last_heartbeat_at = 0.0
    while True:
        now = time.monotonic()
        if now - last_heartbeat_at >= interval_seconds:
            _post_json(f"{center_url}/api/device/heartbeat", payload, shared_token)
            last_heartbeat_at = now
            print(
                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] heartbeat sent for {payload['device_id']}",
                flush=True,
            )
        task = _poll_task(center_url, payload, shared_token)
        if task is not None:
            _run_and_submit_task(center_url, payload["device_id"], task, shared_token)
        time.sleep(task_poll_interval_seconds)


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
    _post_json_for_response(url, payload, shared_token)


def _post_json_for_response(url: str, payload: dict[str, object], shared_token: str) -> dict[str, object]:
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
            raw_response = response.read().decode("utf-8")
            return json.loads(raw_response) if raw_response else {}
    except error.HTTPError as exc:
        raise SystemExit(f"Device agent gagal menghubungi pusat: HTTP {exc.code}") from exc
    except error.URLError as exc:
        raise SystemExit(f"Device agent gagal menghubungi pusat: {exc.reason}") from exc


def _poll_task(center_url: str, registration_payload: dict[str, object], shared_token: str) -> dict[str, object] | None:
    try:
        response = _post_json_for_response(
            f"{center_url}/api/device/tasks/poll",
            registration_payload,
            shared_token,
        )
    except SystemExit as exc:
        if "HTTP 404" in str(exc):
            return None
        raise
    task = response.get("task")
    return task if isinstance(task, dict) else None


def _run_and_submit_task(
    center_url: str,
    device_id: object,
    task: dict[str, object],
    shared_token: str,
) -> None:
    task_id = str(task.get("task_id") or "")
    kind = str(task.get("kind") or "")
    payload = task.get("payload") if isinstance(task.get("payload"), dict) else {}
    try:
        result = _execute_task(kind, payload)
        body = {
            "device_id": str(device_id),
            "task_id": task_id,
            "ok": True,
            "result": result,
        }
    except Exception as exc:
        body = {
            "device_id": str(device_id),
            "task_id": task_id,
            "ok": False,
            "error": str(exc),
        }
    _post_json(f"{center_url}/api/device/tasks/result", body, shared_token)
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] task {task_id} submitted", flush=True)
    if kind == "self_update" and body.get("ok"):
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] self_update selesai, agent restart.", flush=True)
        sys.exit(0)


def _execute_task(kind: str, payload: dict[str, object]) -> dict[str, object]:
    if kind == "host_status":
        return {"output": _host_status()}
    if kind == "self_update":
        return {"output": _self_update()}
    if kind == "natural_query":
        query = str(payload.get("query") or "").strip()
        cwd = _payload_cwd(payload)
        return {"output": _natural_query(query, cwd)}
    if kind == "repo_readonly_query":
        query = str(payload.get("query") or "").strip()
        cwd = _payload_cwd(payload)
        return {"output": _repo_readonly_query(query, cwd)}
    if kind == "late_this_month":
        return {"output": _late_this_month(_payload_cwd(payload))}
    if kind == "sqlite_schema":
        return {"output": _sqlite_schema(_payload_cwd(payload))}
    if kind == "sqlite_query":
        sql = str(payload.get("sql") or "").strip()
        return {"output": _sqlite_query(sql, _payload_cwd(payload))}
    raise RuntimeError(f"Task kind tidak didukung agent ini: {kind}")


def _host_status() -> str:
    uptime = _read_uptime()
    loadavg = ", ".join(str(item) for item in os.getloadavg()) if hasattr(os, "getloadavg") else "-"
    return "\n".join(
        (
            f"Hostname: {socket.gethostname()}",
            f"Platform: {platform.platform()}",
            f"Python: {platform.python_version()}",
            f"Uptime: {uptime}",
            f"Load average: {loadavg}",
        )
    )


def _self_update() -> str:
    import subprocess
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = subprocess.run(
        ["git", "-C", repo_root, "pull"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        raise RuntimeError(f"git pull gagal (exit {result.returncode}):\n{output}")
    return output or "Already up to date."


def _natural_query(query: str, cwd: str | None) -> str:
    import subprocess

    if not query:
        raise RuntimeError("Query tidak boleh kosong.")

    try:
        schema = _sqlite_schema(cwd)
    except Exception as exc:
        schema = f"(schema tidak tersedia: {exc})"

    try:
        db_path = _resolve_sqlite_path(cwd)
    except Exception:
        db_path = "(tidak ditemukan)"

    prompt = (
        f"Kamu adalah asisten analis data bisnis.\n"
        f"Database SQLite tersedia di: {db_path}\n\n"
        f"Schema database:\n{schema}\n\n"
        f"Pertanyaan: {query}\n\n"
        f"Gunakan Bash untuk menjalankan query SQL ke database tersebut, "
        f"kemudian berikan jawaban dalam Bahasa Indonesia yang jelas dan ringkas. "
        f"Jangan tampilkan SQL mentah dalam jawaban akhir."
    )

    work_dir = cwd if cwd and os.path.isdir(cwd) else None
    result = subprocess.run(
        ["claude", "--print", "--allowedTools", "Bash"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=180,
        cwd=work_dir,
        encoding="utf-8",
    )

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(f"claude CLI gagal (exit {result.returncode}): {stderr[:400]}")

    return result.stdout.strip() or "(tidak ada jawaban)"


def _repo_readonly_query(query: str, cwd: str | None) -> str:
    import subprocess

    if not query:
        raise RuntimeError("Query tidak boleh kosong.")
    if not cwd or not os.path.isdir(cwd):
        raise RuntimeError("Repo context device belum diset atau folder repo tidak valid.")

    repo_snapshot = _repo_readonly_snapshot(cwd)
    try:
        schema = _sqlite_schema(cwd)
    except Exception as exc:
        schema = f"(schema SQLite tidak tersedia: {exc})"
    try:
        db_path = _resolve_sqlite_path(cwd)
    except Exception:
        db_path = "(tidak ditemukan)"

    prompt = (
        "Kamu adalah read-only analyst agent untuk repo dashboard HR di device remote.\n"
        "Tugasmu menjawab pertanyaan user dengan membaca repo dan database secara aman.\n\n"
        "Aturan wajib:\n"
        "- Jangan mengubah file apa pun.\n"
        "- Jangan menjalankan command write/destructive seperti rm, mv, cp, chmod, git commit, npm install, migration, deploy, restart, atau redirect output ke file.\n"
        "- Jangan menampilkan secret/token/password dari file konfigurasi. Kalau perlu, sebutkan hanya nama key yang relevan.\n"
        "- Query database hanya boleh SELECT/WITH/read-only dan batasi hasil seperlunya.\n"
        "- Jika data tidak ditemukan, jelaskan data/sumber apa yang kurang.\n"
        "- Jawab dalam Bahasa Indonesia yang jelas dan ringkas.\n\n"
        f"Repo aktif: {cwd}\n"
        f"Database SQLite terdeteksi: {db_path}\n\n"
        f"Ringkasan file repo:\n{repo_snapshot}\n\n"
        f"Schema SQLite jika tersedia:\n{schema}\n\n"
        f"Pertanyaan user:\n{query}\n\n"
        "Silakan inspeksi repo dengan command read-only seperti pwd, find, rg, sed -n, head, tail, dan sqlite3 SELECT jika tersedia. "
        "Akhiri dengan summary final untuk Telegram."
    )

    result = subprocess.run(
        ["claude", "--print", "--allowedTools", "Bash"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=240,
        cwd=cwd,
        encoding="utf-8",
    )

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(f"claude CLI gagal (exit {result.returncode}): {stderr[:400]}")

    return result.stdout.strip() or "(tidak ada jawaban)"


def _read_uptime() -> str:
    try:
        seconds = int(float(open("/proc/uptime", "r", encoding="utf-8").read().split()[0]))
    except Exception:
        return "-"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    return f"{days}d {hours}h {minutes}m"


def _sqlite_schema(cwd: str | None = None) -> str:
    db_path = _resolve_sqlite_path(cwd)
    lines = [f"SQLite: {db_path}"]
    conn = _connect_sqlite_readonly(db_path)
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        if not tables:
            return "\n".join((str(db_path), "Tidak ada tabel user-defined."))
        for (table_name,) in tables:
            columns = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
            column_text = ", ".join(f"{column[1]} {column[2]}".strip() for column in columns[:12])
            if len(columns) > 12:
                column_text += f", +{len(columns) - 12} kolom"
            lines.append(f"- {table_name}: {column_text or '-'}")
    finally:
        conn.close()
    return "\n".join(lines)


def _sqlite_query(sql: str, cwd: str | None = None) -> str:
    if not _is_readonly_sql(sql):
        raise RuntimeError("Remote SQLite hanya menerima SELECT/WITH.")
    db_path = _resolve_sqlite_path(cwd)
    conn = _connect_sqlite_readonly(db_path)
    cursor = None
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql)
        columns = [description[0] for description in cursor.description or []]
        rows = [dict(row) for row in cursor.fetchmany(21)]
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()
    if not columns:
        return "Query selesai tanpa hasil tabular."
    if not rows:
        return "Tidak ada baris hasil."
    lines = [f"SQLite: {db_path}", f"SQL: {sql}", f"Hasil: {min(len(rows), 20)} baris", ""]
    for row_index, row in enumerate(rows[:20], start=1):
        values = []
        for column in columns[:8]:
            values.append(f"{column}={_shorten_cell(row[column])}")
        if len(columns) > 8:
            values.append(f"+{len(columns) - 8} kolom")
        lines.append(f"{row_index}. " + " | ".join(values))
    if len(rows) > 20:
        lines.append("... hasil dipotong ke 20 baris pertama.")
    return "\n".join(lines)


def _late_this_month(cwd: str | None = None) -> str:
    db_path = _resolve_sqlite_path(cwd)
    sql = """
        SELECT
            user_id,
            user_name,
            COUNT(*) AS late_days,
            MIN(attendance_date) AS first_late,
            MAX(attendance_date) AS last_late
        FROM attendance
        WHERE date(attendance_date) >= date('now', 'localtime', 'start of month')
          AND date(attendance_date) < date('now', 'localtime', 'start of month', '+1 month')
          AND (
            upper(coalesce(status, '')) LIKE '%LATE%'
            OR upper(coalesce(status, '')) LIKE '%TERLAMBAT%'
            OR upper(coalesce(status, '')) LIKE '%TELAT%'
            OR time(check_in_time) > '09:00:59'
          )
        GROUP BY user_id, user_name
        ORDER BY late_days DESC, user_name COLLATE NOCASE
    """
    conn = _connect_sqlite_readonly(db_path)
    cursor = None
    try:
        cursor = conn.execute(sql)
        rows = [dict(zip([item[0] for item in cursor.description or []], row)) for row in cursor.fetchall()]
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()

    if not rows:
        return (
            f"SQLite: {db_path}\n"
            "Tidak ada karyawan telat bulan ini."
        )

    total_late_days = sum(int(row["late_days"] or 0) for row in rows)
    lines = [
        f"SQLite: {db_path}",
        "Periode: bulan berjalan",
        "Definisi telat: status berisi LATE/TERLAMBAT/TELAT atau jam masuk > 09:00:59.",
        f"Jumlah karyawan telat: {len(rows)}",
        f"Total kejadian telat: {total_late_days}",
        "",
    ]
    for index, row in enumerate(rows[:50], start=1):
        lines.append(
            f"{index}. {row['user_name']} "
            f"({row['late_days']} hari; {row['first_late']} s.d. {row['last_late']})"
        )
    if len(rows) > 50:
        lines.append(f"... +{len(rows) - 50} karyawan lain.")
    return "\n".join(lines)


def _resolve_sqlite_path(cwd: str | None = None) -> str:
    raw_paths = os.getenv("CODI_BUSINESS_DATABASE_PATHS") or os.getenv("BUSINESS_DATABASE_PATHS") or ""
    for raw_path in raw_paths.split(","):
        candidate = raw_path.strip()
        if candidate and os.path.isfile(candidate):
            return candidate
    if cwd:
        discovered = _discover_sqlite_path(cwd)
        if discovered:
            return discovered
    raise RuntimeError("CODI_BUSINESS_DATABASE_PATHS atau BUSINESS_DATABASE_PATHS belum menunjuk file SQLite yang valid, dan repo context tidak punya file SQLite.")


def _discover_sqlite_path(cwd: str) -> str | None:
    if not os.path.isdir(cwd):
        return None
    skip_dirs = {".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__"}
    for dirpath, dirnames, filenames in os.walk(cwd):
        dirnames[:] = sorted(dirname for dirname in dirnames if dirname not in skip_dirs)
        for filename in sorted(filenames):
            if filename.lower().endswith((".db", ".sqlite", ".sqlite3")):
                return os.path.join(dirpath, filename)
    return None


def _repo_readonly_snapshot(cwd: str) -> str:
    root = Path(cwd)
    skip_dirs = {
        ".git",
        ".next",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
        "coverage",
        "__pycache__",
    }
    interesting_suffixes = {
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".json",
        ".prisma",
        ".sql",
        ".py",
        ".php",
        ".env",
        ".example",
        ".md",
    }
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(cwd):
        rel_dir = os.path.relpath(dirpath, cwd)
        depth = 0 if rel_dir == "." else rel_dir.count(os.sep) + 1
        if depth >= 4:
            dirnames[:] = []
        else:
            dirnames[:] = sorted(dirname for dirname in dirnames if dirname not in skip_dirs)
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            rel_path = path.relative_to(root).as_posix()
            if len(files) >= 160:
                files.append("... daftar file dipotong.")
                return "\n".join(files)
            if filename in {"package.json", "prisma.schema"} or path.suffix.lower() in interesting_suffixes:
                files.append(f"- {rel_path}")
    return "\n".join(files) if files else "(tidak ada file relevan yang terdeteksi)"


def _payload_cwd(payload: dict[str, object]) -> str | None:
    cwd = str(payload.get("cwd") or "").strip()
    return cwd or None


def _connect_sqlite_readonly(db_path: str) -> sqlite3.Connection:
    db_uri = Path(db_path).resolve().as_uri()
    return sqlite3.connect(f"{db_uri}?mode=ro", uri=True)


def _is_readonly_sql(sql: str) -> bool:
    if not sql or ";" in sql.rstrip(";"):
        return False
    if re.search(
        r"\b(?:insert|update|delete|drop|alter|create|replace|truncate|attach|detach|vacuum|reindex)\b",
        sql,
        re.IGNORECASE,
    ):
        return False
    return sql.lower().lstrip().startswith(("select", "with"))


def _shorten_cell(value) -> str:
    if value is None:
        return "NULL"
    text = str(value).replace("\n", " ")
    return text if len(text) <= 120 else text[:119] + "..."


def _default_device_type() -> str:
    if platform.system().lower() == "linux" and os.getenv("DISPLAY"):
        return "desktop"
    return "server"


def _default_capabilities(device_type: str) -> str:
    capabilities = ["system_activity", "business_readonly"]
    if shutil.which("claude"):
        capabilities.append("natural_query")
        capabilities.append("repo_readonly")
    return ",".join(capabilities)


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
