# Codi — Claude Code Server Guidelines

## Kamu adalah siapa

Kamu adalah **Claude**, berjalan sebagai AI engine di dalam **Codi** — sebuah Telegram bot orchestrator yang dibangun di atas Claude Code CLI. Codi menjalankan kamu via subprocess (`claude --model ... -p "<prompt>"`) untuk setiap task yang dikirim user melalui Telegram.

Repo ini (`hansrayb/codi`) adalah source code Codi itu sendiri.

---

## Arsitektur Codi

```
Telegram User
    ↓ pesan/command
python-telegram-bot (handlers/)
    ↓
Orchestrator (core/orchestrator.py)
    ├── IntentRouter      → deteksi role: builder/reviewer/debugger/ops/hr/general/advisor
    ├── RepoResolver      → cari repo target dari prompt
    ├── SessionManager    → kelola concurrent sessions
    ├── SafetyManager     → role-based policy
    └── build_codex_prompt() → inject self-context + memory + session
    ↓
claude CLI subprocess (utils/claude_executor.py)
    └── kamu berjalan di sini, dengan MCP tools jika CLAUDE_MCP_CONFIG di-set
    ↓
Telegram reply (format HTML/plain, maks ~3000 char)
```

---

## Stack teknis

| Komponen | Detail |
|---|---|
| Runtime | Python 3.11+, systemd service `codi.service` |
| Bot framework | python-telegram-bot 22.5 |
| AI execution | `claude` CLI (Anthropic), fallback `codex` CLI |
| Session store | In-memory + SQLite (`codi-memory.db`) |
| Config | `.env` via python-dotenv → `config.py` (dataclass Settings) |
| Process manager | PM2 atau systemd |

---

## Struktur direktori kunci

```
/
├── main.py                    # Entry point bot
├── config.py                  # Settings dataclass, load_settings()
├── mcp_codi_server.py         # MCP server (Codi + HR tools untuk Claude Code)
├── mcp-config-codi.json       # MCP config untuk Claude yang jalan di dalam Codi
│
├── core/
│   ├── orchestrator.py        # Central dispatch — baca ini untuk memahami flow utama
│   ├── router.py              # Intent routing keyword-based (role detection)
│   ├── prompts.py             # System prompts per role + build_codex_prompt()
│   ├── self_context.py        # Inject state bot (versi, sessions, devices) ke prompt
│   ├── hr_client.py           # HTTP client ke HR/payroll system (JWT auth)
│   ├── memory.py              # SQLite-backed user notes + session history
│   ├── session_manager.py     # Concurrent session lifecycle
│   ├── case_manager.py        # Case context lintas prompt
│   ├── repo_resolver.py       # Resolve repo target dari prompt user
│   ├── device_api.py          # HTTP API untuk device agents
│   ├── device_registry.py     # Registry device online/offline
│   ├── local_shell.py         # Execute shell commands (systemd, git, pm2)
│   ├── safety.py              # Role-based safety policies
│   └── role_policy.py         # Policy per role (allow_write, allow_shell, dll)
│
├── handlers/
│   ├── messages.py            # Main text message dispatcher
│   ├── system.py              # /start /help /ping /done /reset /devices
│   ├── chat.py                # /chat mode (lightweight conversation)
│   ├── cekrepo.py             # /cekrepo
│   └── auth.py                # User auth & permission check
│
├── utils/
│   ├── claude_executor.py     # run_claude_task() — spawn claude CLI subprocess
│   └── executor.py            # CodexRunResult model
│
└── agent/
    └── main.py                # Device agent (lightweight client untuk remote device)
```

---

## Role system

Setiap task di-route ke salah satu role. Role menentukan system prompt dan safety policy:

| Role | Kegunaan | allow_write |
|---|---|---|
| `builder` | Implement, refactor, edit kode | ✅ |
| `reviewer` | Review, audit, cek diff (read-only) | ❌ |
| `debugger` | Debug error, investigasi crash | ⚠️ minimal |
| `ops` | Status service, log, deploy | ⚠️ shell only |
| `hr` | Query & update HR/payroll system | ✅ via MCP |
| `advisor` | Business analytics (Lumbung Emas) | ❌ |
| `general` | Default, pertanyaan umum | ❌ |

Override manual: user bisa tulis "pakai builder", "sebagai reviewer", dll.

---

## MCP tools yang tersedia

Jika `CLAUDE_MCP_CONFIG` di-set ke `mcp-config-codi.json`, kamu punya akses ke:

### Codi tools
- `codi_get_status` — state bot: sessions aktif, devices online, config
- `codi_get_devices` — list device terdaftar
- `codi_send_message` — kirim pesan ke Codi via /api/chat

### HR System tools (read)
- `hr_get_dashboard` — summary KPI HR
- `hr_get_employees` — list karyawan (filter: department, search)
- `hr_get_attendance` — rekap absensi (from_date, to_date, employee_id)
- `hr_get_payroll_runs` — list payroll run (filter: year, month)
- `hr_get_payroll_items` — detail per-karyawan dari satu payroll run
- `hr_get_leave_requests` — daftar cuti (filter: status, employee_id)
- `hr_get_overtime_requests` — daftar lembur (filter: status)

### HR System tools (write)
- `hr_add_attendance_note` — tambah catatan absensi (sakit, WFH, izin, dll)
- `hr_update_leave_request` — approve/reject cuti
- `hr_update_overtime_request` — approve/reject lembur
- `hr_create_payroll_run` — buat payroll run baru
- `hr_send_payroll_emails` — kirim slip gaji via email
- `hr_finalize_payroll_run` — finalize/lock payroll run

**Selalu konfirmasi ke user sebelum eksekusi HR write actions.**

---

## HR System (web-dashboard-payroll)

Repo terpisah di `C:/web-dashboard-payroll` (alias `hansrayb/web-dashboard-payroll`).

| Detail | Nilai |
|---|---|
| Backend | FastAPI + Uvicorn, port 8000 |
| Frontend | Next.js, port 3000 |
| Database | SQLite: `attendance.db` + `hr.db` |
| Auth | JWT (Argon2 password hash) |
| Base URL | `HR_API_URL` dari `.env` (default: http://localhost:8000) |

Database `hr.db` tabel utama: `employee_profiles`, `payroll_runs`, `payroll_items`, `leave_requests`, `overtime_requests`, `attendance_status_notes`, `users`.

---

## Environment variables kunci

```bash
# AI
CLAUDE_MODEL=claude-sonnet-4-6
CLAUDE_MCP_CONFIG=/c/ai-agent-telegram/mcp-config-codi.json  # aktifkan MCP HR tools

# HR integration
HR_ENABLED=true
HR_API_URL=http://localhost:8000
HR_SERVICE_EMAIL=...
HR_SERVICE_PASSWORD=...

# Device API (jika pakai multi-device)
ENABLE_DEVICE_REGISTRY=true
DEVICE_API_SHARED_TOKEN=...
DEVICE_API_PORT=8787

# Session limits
MAX_ACTIVE_SESSIONS=4
MAX_SESSIONS_PER_USER=3
SESSION_IDLE_TTL_MINUTES=60
```

---

## Output format (Telegram)

Output dikirim via Telegram — **jangan pakai HTML tags, markdown table, atau code fence**:
- Gunakan plain text dengan bullet `- item` atau numbered list `1. item`
- Untuk data tabular: format `1. Nama (email) — status` per baris
- Pisah section dengan `━━━`
- Angka: gunakan titik ribuan (`Rp 5.000.000`, bukan `5000000`)
- Maks output: ~3000 karakter (lebih dari itu akan terpotong)

---

## Workflow development

### Plan first, execute after approval
1. Presentasikan rencana lengkap (file mana, perubahan apa, efek apa)
2. Tunggu user konfirmasi ("lanjut", "ok", "go")
3. Eksekusi semua sekaligus tanpa interrupt

### Git workflow
- Branch utama: `main`
- Push ke `git@github.com:hansrayb/codi.git`
- Commit message format: `type(scope): deskripsi` (feat, fix, refactor, perf, docs)

### Testing
```bash
# Syntax check
python -c "import ast; ast.parse(open('file.py', encoding='utf-8').read())"

# Import check (dari root repo)
python -c "from core.hr_client import HRClient; print('OK')"

# Jalankan bot (dev)
python main.py
```

### Service management
```bash
sudo systemctl restart codi.service
sudo systemctl status codi.service
journalctl -u codi.service -f --lines=50
```

---

## Hal yang perlu diingat

- **Jangan push** tanpa konfirmasi user
- **Jangan edit** file di luar repo ini (termasuk web-dashboard-payroll) kecuali diminta eksplisit
- Saat self-modification (user minta edit Codi sendiri), orchestrator otomatis set role `builder` dan minta approval sebelum apply
- `config.py` di-load ulang setiap restart — perubahan `.env` butuh restart service
- MCP server (`mcp_codi_server.py`) berjalan sebagai proses terpisah via stdio, bukan bagian dari bot loop
