# SPEC: Telegram Bot — Orchestrated Codex Agent

## Overview

Bot Telegram yang menjadi antarmuka aman dan minimalis untuk berinteraksi dengan **OpenAI Codex CLI** dari mana saja.

User tidak perlu menghafal banyak command. Cukup kirim pesan biasa dalam bahasa natural, lalu **orchestrator internal** akan:

- memahami intent prompt
- memilih **role/agent** yang paling cocok
- menentukan apakah perlu memakai session yang sedang aktif atau membuat session baru
- menjalankan Codex di session yang sesuai
- mengirim hasil kembali ke Telegram

Blueprint ini sengaja menggeser kompleksitas dari UI bot ke backend orchestration. Hasilnya:

- command Telegram tetap sedikit
- sistem bisa menjalankan beberapa session fokus berbeda di belakang layar
- user tetap bisa memakai bot seperti sedang chat biasa

-----

## Prinsip Produk

1. **Minimal commands**
   Bot hanya punya command yang penting dan signifikan.
1. **Natural-language first**
   Semua pesan teks biasa dianggap sebagai task, kecuali command Telegram.
1. **Hidden orchestration**
   User tidak perlu memilih agent secara manual setiap saat.
1. **Focused sessions**
   Sistem boleh menjalankan beberapa session internal dengan fokus berbeda.
1. **Safe by default**
   Auth, timeout, allowlist directory, dan pembatasan role harus aktif sejak awal.

-----

## Tujuan

- Menjadikan Telegram sebagai front-end ringan untuk Codex agent.
- Mendukung beberapa session internal secara paralel tanpa membuat UI bot jadi ramai.
- Membiarkan orchestrator memilih role yang tepat berdasarkan prompt user.
- Menjaga akses tetap aman untuk user yang terotorisasi saja.

## Non-goals (v1)

- Tidak menampilkan banyak command untuk mengatur session satu per satu.
- Tidak menyediakan panel admin kompleks di Telegram.
- Tidak mewajibkan user memilih role secara manual di setiap request.
- Tidak menyimpan state session secara persisten lintas restart proses.

-----

## Stack

| Komponen | Teknologi |
|----------|-----------|
| Runtime | Python 3.11+ |
| Bot Framework | `python-telegram-bot` v20+ (async) |
| Orchestration | Python async service layer |
| Executor | `asyncio.create_subprocess_exec` |
| Config | `.env` via `python-dotenv` |
| Logging | `logging` (Python stdlib) |
| Monitoring | `psutil` |
| OS Target | Fedora Linux (systemd compatible) |

Catatan implementasi:

- Di level produk, sistem mengenal istilah **session terminal**.
- Di level implementasi, session boleh dimulai sebagai **logical session** yang dibungkus `SessionManager`.
- Jika nanti Codex CLI lebih cocok dijalankan sebagai PTY/terminal persisten, perubahan itu cukup terjadi di layer executor, tanpa mengubah kontrak Telegram bot.

-----

## Arsitektur Tingkat Tinggi

```text
Telegram User
   |
   v
Telegram Bot Handler
   |
   v
Auth Layer
   |
   v
Orchestrator
   |---- Intent Router
   |---- Role Policy
   |---- Session Manager
   |
   v
Codex Executor
   |
   v
Codex CLI
```

### Komponen Utama

| Komponen | Tanggung jawab |
|----------|----------------|
| Telegram Handler | Menerima command penting dan pesan teks biasa |
| Auth Layer | Memastikan hanya user terotorisasi yang diproses |
| Orchestrator | Pusat keputusan: route, reuse session, policy, result |
| Intent Router | Menentukan role yang paling cocok dari prompt |
| Session Manager | Mengelola session aktif, status, idle TTL, queue |
| Role Policy | Aturan izin untuk tiap role |
| Executor | Menjalankan Codex CLI dengan timeout dan capture output |
| Formatter | Mengubah hasil agar aman dan nyaman dikirim ke Telegram |

-----

## Struktur Direktori

```text
telegram-codex-agent/
├── main.py                    # Entry point, inisialisasi bot
├── config.py                  # Load env & validasi konfigurasi
├── handlers/
│   ├── __init__.py
│   ├── auth.py                # Middleware whitelist user
│   ├── messages.py            # Handler semua pesan teks non-command
│   ├── system.py              # Handler /start, /help, /reset
│   └── status.py              # Handler /status
├── core/
│   ├── __init__.py
│   ├── orchestrator.py        # Koordinasi route, session, execution
│   ├── router.py              # Intent classification dan role selection
│   ├── session_manager.py     # Session registry, lifecycle, queue
│   ├── role_policy.py         # Mapping role -> capability
│   └── prompts.py             # Default system prompt per role
├── models/
│   ├── __init__.py
│   ├── session.py             # Data model session
│   └── result.py              # Data model execution result
├── utils/
│   ├── __init__.py
│   ├── executor.py            # Wrapper subprocess Codex
│   ├── formatter.py           # Format output untuk Telegram
│   └── logger.py              # Setup logging
├── .env.example
├── requirements.txt
├── codex-agent.service
└── README.md
```

-----

## Konsep Session

### Definisi

Session adalah konteks eksekusi internal yang diperlakukan seperti **terminal fokus**.

Setiap session punya:

- `session_id`
- `owner_user_id`
- `role`
- `status` (`idle`, `busy`, `queued`, `stopped`)
- `cwd`
- `created_at`
- `last_activity_at`
- `summary`
- `message_count`

### Sifat Session

- Satu session hanya memproses **satu task aktif** pada satu waktu.
- Satu user boleh punya beberapa session aktif, selama belum melewati limit.
- Session disembunyikan dari user biasa; user berinteraksi lewat chat natural.
- Session boleh di-reuse jika prompt baru terlihat sebagai lanjutan dari konteks sebelumnya.
- Session idle akan dihentikan otomatis setelah melewati TTL.

### Catatan Implementasi

Untuk v1, session tidak wajib berupa terminal interaktif persisten. Yang penting, di level arsitektur:

- session punya identitas dan fokus
- orchestrator dapat memilih dan me-reuse session
- layer executor menyembunyikan detail apakah implementasinya subprocess baru per task atau worker persisten

-----

## Role Internal

Role dipilih otomatis oleh orchestrator. User tidak perlu memanggil command khusus untuk memilih role.

| Role | Fokus | Contoh task | Policy umum |
|------|-------|-------------|-------------|
| `builder` | implementasi dan perubahan kode | buat fitur, refactor, tambah test | boleh write di workdir yang diizinkan |
| `reviewer` | review dan audit | review file, cari bug, cek risiko | read-only |
| `debugger` | diagnosis dan perbaikan issue | traceback, crash, service gagal start | read mostly, write terbatas sesuai policy |
| `ops` | operasional dan sistem | status, log, service, resource host | tidak untuk perubahan kode aplikasi |
| `general` | fallback role | prompt ambigu atau campuran | policy aman paling konservatif |

### Override Ringan

User tetap boleh memberi arahan eksplisit di prompt tanpa menambah command baru. Contoh:

- `pakai reviewer untuk cek auth middleware ini`
- `anggap ini task builder`
- `fokus sebagai debugger: kenapa unit test ini flaky`

Jika ada override eksplisit seperti ini, orchestrator harus memprioritaskannya selama tidak melanggar policy.

-----

## Command yang Didukung

### `/start`

Menampilkan pesan selamat datang dan cara pakai singkat.

**Response:**

```text
Codex Agent aktif.

Kirim pesan biasa untuk menjalankan task.
Contoh:
- review auth middleware ini
- buat endpoint login FastAPI
- kenapa service systemd gagal start

Commands:
/status - cek status bot dan sistem
/reset - reset konteks session aktif kamu
/help - tampilkan bantuan
```

### `/help`

Alias `/start`.

### `/status`

Menampilkan ringkasan status bot, session, dan workload host.

**Output format:**

```text
Status Bot - 2026-04-05 00:34

Active sessions : 2 / 4
Your active role: reviewer
Queued tasks    : 1
Bot uptime      : 2 jam 15 menit

Host:
CPU  : 23% (4 core)
RAM  : 3.2 GB / 8 GB (40%)
Disk : 45 GB / 256 GB (18%) - /
```

### `/reset`

Menghapus mapping session aktif milik user saat ini dan menandai konteks percakapan berikutnya sebagai task baru.

Command ini penting karena:

- user kadang ingin memulai konteks baru
- routing otomatis kadang bisa salah
- session yang terlalu panjang bisa menjadi tidak relevan

### Pesan Teks Biasa

Semua pesan non-command dianggap sebagai task input.

Contoh:

```text
review file auth.py ini
```

```text
buatkan fungsi validasi nomor telepon Indonesia
```

```text
lanjutkan yang tadi, tapi tambahkan test
```

-----

## Flow Pesan Masuk

1. Validasi user ID melalui auth middleware.
1. Jika pesan adalah command:
   `/start`, `/help`, `/status`, atau `/reset`.
1. Jika pesan adalah teks biasa:
   teruskan ke `Orchestrator.handle_message(...)`.
1. Orchestrator melakukan:
   - normalisasi prompt
   - cek apakah ada override role eksplisit
   - deteksi apakah ini lanjutan dari session aktif
   - klasifikasi intent
   - pilih role
   - pilih atau buat session
   - jalankan task lewat executor
1. Bot mengirim ack singkat:
   `Diproses oleh reviewer (session s-02)`
1. Setelah selesai, bot mengirim hasil.
1. Jika output terlalu panjang, kirim sebagai file `.txt`.

-----

## Routing & Orchestration

### Tanggung Jawab Orchestrator

`core/orchestrator.py` adalah pusat keputusan.

Ia bertanggung jawab untuk:

- memilih role internal
- menentukan reuse session vs create session baru
- menjaga limit concurrency
- mengelola queue jika session target sedang sibuk
- mencatat metadata hasil eksekusi
- mengembalikan respons yang ramah ke Telegram

### Strategi Routing Awal

Gunakan pendekatan **rule-based** terlebih dahulu. Tidak perlu LLM router di v1.

Contoh heuristik:

- prompt mengandung `review`, `audit`, `cek bug`, `risk` -> `reviewer`
- prompt mengandung `buat`, `implement`, `refactor`, `tambahkan test` -> `builder`
- prompt mengandung `error`, `traceback`, `kenapa gagal`, `debug` -> `debugger`
- prompt mengandung `status`, `service`, `log`, `deploy`, `uptime` -> `ops`
- jika tidak yakin -> `general`

### Aturan Reuse Session

Session aktif milik user sebaiknya di-reuse jika:

- prompt mengandung kata lanjutan seperti `lanjutkan`, `yang tadi`, `perbaiki lagi`
- prompt masih jelas membahas topik terakhir
- role yang dipilih masih sama

Session baru sebaiknya dibuat jika:

- intent berubah drastis
- role yang dibutuhkan berbeda
- session sebelumnya sedang sibuk dan queue policy tidak mengizinkan penumpukan
- orchestrator menilai prompt adalah task terpisah

### Fallback Aman

Jika confidence routing rendah:

- gunakan role `general`
- kirim label role yang dipakai ke user
- biarkan user mengoreksi lewat prompt berikutnya tanpa command tambahan

-----

## Session Manager

### Tanggung Jawab

`core/session_manager.py` mengelola:

- registry session aktif
- lookup session per user
- status `idle` / `busy`
- idle timeout
- queue task per session
- penghentian session saat crash atau shutdown

### Policy Awal

- Maksimal `MAX_ACTIVE_SESSIONS` session global
- Maksimal `MAX_SESSIONS_PER_USER` session per user
- Satu session hanya satu task aktif
- FIFO queue per session, opsional maksimal 1-2 task tertunda
- Session idle lebih lama dari `SESSION_IDLE_TTL_MINUTES` dihentikan otomatis

### Persistensi

Untuk v1:

- registry session cukup in-memory
- setelah proses bot restart, session dianggap hilang
- `/reset` dan TTL cukup untuk menjaga kebersihan state

-----

## Executor (`utils/executor.py`)

Gunakan executor yang menyembunyikan detail bagaimana Codex dijalankan.

### Interface yang diharapkan

```python
async def run_codex_task(
    prompt: str,
    role: str,
    cwd: str,
    timeout: int,
    session_id: str | None = None,
) -> tuple[int, str, str]:
    """
    Returns: (exit_code, stdout, stderr)
    Raises: asyncio.TimeoutError jika melebihi timeout
    """
```

### Aturan Implementasi

- Gunakan `asyncio.create_subprocess_exec(...)`
- Jangan gunakan `shell=True`
- Prompt diteruskan sebagai argumen aman, bukan string shell mentah
- Role diterjemahkan menjadi instruction/system prompt tambahan
- Capture stdout dan stderr terpisah
- Decode output dengan `utf-8`, fallback `latin-1`
- Enforce timeout via `asyncio.wait_for`
- Kill subprocess jika timeout atau shutdown

### Catatan Arsitektural

`session_id` ada agar layer executor siap jika nanti implementasi berubah menjadi worker persisten/PTY. Untuk v1, parameter ini boleh hanya dipakai untuk logging dan korelasi.

-----

## Formatter (`utils/formatter.py`)

Fungsi untuk memformat output agar sesuai dengan limit Telegram:

- Telegram max message: 4096 karakter
- Gunakan `MAX_OUTPUT_LENGTH` agar ada margin aman
- Jika output melebihi batas -> kirim file `.txt`
- Escape markdown jika perlu
- Jangan rusak karena triple backtick dari output mentah
- Jika output kosong -> balas dengan ringkasan sukses

Contoh:

```text
Selesai oleh builder (session s-03)

[ringkasan output]
```

Jika perlu:

```text
Output terlalu panjang, saya kirim sebagai file.
```

-----

## Environment Variables (`.env`)

```env
# REQUIRED
TELEGRAM_BOT_TOKEN=your_bot_token_here
ALLOWED_USER_IDS=123456789,987654321

# Codex
CODEX_BIN=codex
CODEX_TIMEOUT=180
CODEX_WORK_DIR=/home/hans/projects
ALLOWED_WORK_DIRS=/home/hans/projects,/home/hans/sandbox

# Sessions
DEFAULT_ROLE=general
MAX_ACTIVE_SESSIONS=4
MAX_SESSIONS_PER_USER=3
SESSION_IDLE_TTL_MINUTES=60
MAX_QUEUE_PER_SESSION=1

# Output
MAX_OUTPUT_LENGTH=3000

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/codex-agent.log

# Safety
MAX_REQUESTS_PER_MINUTE=5
```

### Validasi Startup

Saat aplikasi start:

- `TELEGRAM_BOT_TOKEN` wajib ada
- `ALLOWED_USER_IDS` wajib valid integer list
- `CODEX_WORK_DIR` wajib ada dan masuk dalam `ALLOWED_WORK_DIRS`
- semua limit numerik harus lebih besar dari 0
- app harus fail fast jika config tidak valid

-----

## Security

### Auth Middleware (`handlers/auth.py`)

Setiap handler wajib melewati middleware ini.

```python
def require_auth(handler_func):
    async def wrapper(update, context):
        user_id = update.effective_user.id
        if user_id not in ALLOWED_USER_IDS:
            await update.message.reply_text("Akses ditolak.")
            logger.warning("unauthorized access", extra={"user_id": user_id})
            return
        return await handler_func(update, context)
    return wrapper
```

### Aturan Keamanan

| Rule | Detail |
|------|--------|
| Whitelist user | Hanya user ID dalam `ALLOWED_USER_IDS` yang diproses |
| No shell | Gunakan `create_subprocess_exec`, bukan `shell=True` |
| Allowlist workdir | Session hanya boleh berjalan di direktori yang diizinkan |
| Role policy | Role tertentu bisa read-only atau tidak boleh menulis kode |
| Timeout wajib | Setiap task Codex punya timeout |
| No root | Bot tidak boleh dijalankan sebagai root |
| Rate limiting | Batasi request per user per menit |
| Log semua akses | Catat user, role, session, durasi, hasil |
| Redaksi prompt sensitif | Jika memungkinkan, potong atau mask token sensitif di log |
| Kill on shutdown | Saat service berhenti, child process harus ikut dihentikan |

### Role Policy Minimum

| Role | Policy minimum |
|------|----------------|
| `reviewer` | read-only |
| `ops` | tidak untuk write source code |
| `builder` | write hanya di workdir yang diizinkan |
| `general` | policy konservatif, tidak lebih longgar dari `builder` |

-----

## Logging (`utils/logger.py`)

Format log:

```text
2026-04-05 00:34:12 | INFO | user_id=123456789 | session=s-02 | role=reviewer | action=dispatch | prompt="review auth middleware"
2026-04-05 00:34:15 | INFO | user_id=123456789 | session=s-02 | role=reviewer | exit_code=0 | duration=3.2s
```

Log minimal harus mencatat:

- `user_id`
- `session_id`
- `role`
- `command` atau `message_type`
- durasi
- exit code
- apakah session di-reuse atau baru dibuat

Log ke:

- stdout
- file jika `LOG_FILE` di-set

-----

## Status Sistem (`/status`)

Data yang diambil:

- CPU usage: `psutil.cpu_percent(interval=1)`
- RAM: `psutil.virtual_memory()`
- Disk: `psutil.disk_usage('/')`
- Uptime host: parse `/proc/uptime`
- Session count: dari `SessionManager`
- Queue count: dari `SessionManager`
- Bot uptime: waktu sejak proses start

`/status` harus menampilkan dua lapisan:

1. Status internal bot
1. Status host Linux

-----

## Systemd Service (`codex-agent.service`)

```ini
[Unit]
Description=Telegram Orchestrated Codex Agent Bot
After=network.target

[Service]
Type=simple
User=hans
WorkingDirectory=/home/hans/telegram-codex-agent
EnvironmentFile=/home/hans/telegram-codex-agent/.env
ExecStart=/usr/bin/python3 main.py
Restart=on-failure
RestartSec=10
KillMode=control-group
TimeoutStopSec=15
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

`KillMode=control-group` penting agar child process Codex ikut dihentikan saat service stop/restart.

-----

## Requirements (`requirements.txt`)

```text
python-telegram-bot==20.7
python-dotenv==1.0.0
psutil==5.9.8
```

Jika nanti implementasi session benar-benar membutuhkan PTY persisten, dependency tambahan boleh dipertimbangkan di fase berikutnya, tetapi tidak wajib untuk blueprint v1 ini.

-----

## Setup & Cara Pakai

### 1. Clone & install dependencies

```bash
git clone <repo>
cd telegram-codex-agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Konfigurasi

```bash
cp .env.example .env
nano .env
```

Isi minimal:

- `TELEGRAM_BOT_TOKEN`
- `ALLOWED_USER_IDS`
- `CODEX_WORK_DIR`

### 3. Cara dapat Telegram User ID

Kirim pesan ke `@userinfobot` di Telegram, lalu catat user ID kamu.

### 4. Jalankan

```bash
python3 main.py
```

### 5. (Opsional) Install sebagai service systemd

```bash
sudo cp codex-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now codex-agent
```

-----

## Error Handling Matrix

| Kondisi | Response ke User | Log Level |
|---------|------------------|-----------|
| User tidak terotorisasi | `Akses ditolak.` | WARNING |
| Prompt kosong | `Kirim task dalam bentuk pesan teks.` | INFO |
| Codex tidak ditemukan | `Codex CLI tidak ditemukan di sistem.` | ERROR |
| Timeout | `Task timeout setelah X detik.` | WARNING |
| Exit code != 0 | `Task gagal dijalankan. Ringkasan error dikirim.` | WARNING |
| Semua session penuh | `Semua agent sedang sibuk. Coba lagi sebentar.` | WARNING |
| Queue session penuh | `Session terkait sedang penuh. Coba ulang atau /reset.` | INFO |
| Routing confidence rendah | `Prompt diproses oleh general.` | INFO |
| Exception tak terduga | `Terjadi kesalahan internal.` | ERROR |

-----

## Pengembangan Lanjutan

| Fitur | Deskripsi |
|-------|-----------|
| Session summary yang lebih pintar | Ringkas konteks lama sebelum reuse |
| Router berbasis model | Ganti rule-based jika task makin kompleks |
| Persisted session registry | Menyimpan metadata session ke disk/DB |
| Manual session inspect | Lihat daftar session aktif untuk admin |
| `/cancel` | Batalkan task yang sedang berjalan |
| Role policy lebih granular | Misalnya allowlist command/tool per role |
| Webhook mode | Alternatif polling untuk deployment produksi |

Catatan:

`/cancel` sengaja masuk future, tetapi tetap kandidat kuat untuk naik ke MVP jika penggunaan harian menunjukkan task sering panjang atau salah route.

-----

## Catatan untuk Codex

Saat generate kode dari spec ini, pastikan:

1. Semua handler memakai decorator `@require_auth`
1. Semua I/O bersifat async
1. Tidak ada `shell=True`
1. Semua variabel sensitif diambil dari `.env`
1. Setiap file punya docstring singkat di bagian atas
1. Gunakan `logger`, bukan `print`
1. Orchestrator menjadi pusat keputusan, bukan handler Telegram
1. Routing role dimulai dari rule-based yang mudah diuji
1. Session disembunyikan dari UI Telegram, kecuali info ringkas di `/status` atau ack hasil
