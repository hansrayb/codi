# Codi
Bot Telegram minimalis bernama Codi untuk menjalankan task Codex melalui chat biasa, dengan orchestrator internal yang memilih role, mengelola session, dan menjaga pembatasan keamanan dasar.

## Fitur

- Command minimal: `/start`, `/help`, `/status`, `/devices`, `/done`, `/reset`
- Semua pesan biasa diperlakukan sebagai task
- Routing role otomatis: `builder`, `reviewer`, `debugger`, `ops`, `general`
- Case manager v1: satu konteks kerja aktif per user, konteks repo bertahan lintas prompt sampai `/done`
- Session logis per user dengan TTL idle dan queue kecil
- Eksekusi Codex non-interaktif via `codex exec`, dengan resume native untuk session yang stabil
- Repo resolver v1: path absolut, nama repo, fuzzy hint ringan, dan reuse workspace aktif
- Edit with approval: builder/debugger menyiapkan diff dulu, lalu draft edit per konteks kerja tetap dipakai sampai `/done`
- Self-update workflow: jika repo aktif adalah repo Codi sendiri, Codi akan compile, test, lalu restart otomatis setelah apply bila verifikasi lolos
- Desktop action aman untuk intent eksplisit seperti membuka aplikasi GUI yang terpasang
- Repo watch: Codi bisa memantau repo Git dan mengirim notifikasi saat branch, HEAD, atau status kerja berubah
- Observability host langsung: Codi bisa merangkum aplikasi desktop aktif, background process penting, dan log runtime terbaru
- Bantuan workflow Git ringan: Codi bisa bantu ringkas diff lokal, menyusun commit message, judul PR, dan deskripsi PR berbasis perubahan yang benar-benar ada
- Fase 1 multi-device: bot pusat bisa menyimpan registry device, menerima heartbeat agent, dan menampilkan device online/offline dari Telegram
- Auth whitelist dan rate limiting sederhana

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Isi `.env` minimal:

- `TELEGRAM_BOT_TOKEN`
- `ALLOWED_USER_IDS`
- `CODEX_WORK_DIR`

Opsi yang disarankan untuk UX Telegram:

- `CODEX_REASONING_EFFORT=medium`

Opsi tambahan untuk fase 1 multi-device:

- `ENABLE_DEVICE_REGISTRY=true`
- `DEVICE_API_SHARED_TOKEN=...`
- `DEVICE_API_HOST=0.0.0.0` jika bot pusat perlu menerima heartbeat dari host lain
- `DEVICE_API_PORT=8787`

Dokumen lanjutan:

- roadmap produk: [ROADMAP.md](./ROADMAP.md)
- arsitektur multi-device yang aman: [MULTI_DEVICE_ARCHITECTURE.md](./MULTI_DEVICE_ARCHITECTURE.md)

## Desktop Action

Saat ini Codi mendukung aksi desktop eksplisit untuk membuka aplikasi GUI langsung dari nama app, dengan profile khusus untuk aplikasi tertentu seperti `LibreOffice Writer` dan `Firefox`.

Contoh prompt:

- `buka libreoffice writer`
- `buka firefox`
- `buka mozilla`
- `buka telegram` jika Telegram memang terpasang di desktop ini
- `jalankan writer`
- `open libreoffice writer`
- `tutup libreoffice writer`
- `Codi laptop ku sedang menjalankan aplikasi apa`
- `tampilkan log Codi terbaru`
- `kirim screenshot laptop sekarang`
- `kirim screenshot laptop sekarang dan ringkas isi layar`
- `kirim screenshot monitor aktif`
- `kirim screenshot jendela aktif sekarang`
- `device yang online apa saja`
- `status semua device`
- `detail device laptop-kerja`
- `mode saya apa`
- `mode aman`
- `mode ops`
- `mode admin`
- `lanjutkan aksi`
- `batal aksi`
- `restart codi`
- `ubah codex timeout jadi 600`
- `ubah local shell timeout jadi 600`
- `shell: systemctl --user status codex-agent.service`
- `bash: git status --short`
- `pwsh: Get-Process | Select-Object -First 5`
- `pull repo ini`
- `cek branch repo ini`
- `buat branch fitur/login di repo ini`
- `switch ke branch main di repo ini`
- `merge branch staging ke main di repo ini`
- `hapus branch fitur/login di repo ini`
- `rebase branch fitur/login ke main di repo ini`
- `commit repo ini dengan pesan "Update payroll flow"`
- `commit semua perubahan di repo ini dengan pesan "Update payroll flow"`
- `cherry-pick commit a1b2c3d di repo ini`
- `rollback commit terakhir di repo ini`
- `rollback ke tag v1.2.3 di repo ini`
- `buat tag v1.2.3 di repo ini`
- `cek health service codex-agent`
- `cek health semua service penting`
- `status service codex-agent`
- `start service payroll`
- `stop service payroll`
- `restart service payroll`
- `lihat log service payroll`
- `publish build frontend payroll`
- `deploy frontend payroll`
- `publish backend payroll`
- `deploy backend payroll`
- `test backend payroll`
- `build frontend payroll`
- `test repo web-dashboard-payroll`

Catatan:

- Fitur ini melewati Codex dan memakai profile app atau desktop entry lokal yang tersedia.
- Firefox/Mozilla memakai profile `new window`, jadi lebih cepat dan lebih konsisten saat browser sudah aktif.
- Aksi `tutup` hanya berlaku untuk instance aplikasi yang berhasil dilacak Codi pada runtime yang sama.
- Codi perlu berjalan dalam sesi desktop Linux aktif agar aplikasi GUI benar-benar muncul.
- `shell:` dan kawan-kawannya menjalankan perintah lokal langsung di mesin host, bukan lewat sandbox Codex, jadi sebaiknya dipakai dengan prefix yang sengaja dan oleh user yang memang dipercaya.
- Shortcut natural seperti `pull repo ini` atau `build frontend payroll` juga diarahkan ke shell lokal, dengan target repo yang dicoba ditebak dari konteks aktif atau nama repo di prompt.
- Codi sekarang punya safety layer untuk aksi host yang sensitif: mode `aman`/`ops`/`admin`, allowlist command, konfirmasi 2 langkah lewat `lanjutkan aksi` atau `batal aksi`, dan audit log lokal di `codi-audit.log`.
- Untuk pengaturan yang sangat spesifik seperti `ubah codex timeout jadi 600` atau `ubah local shell timeout jadi 600`, Codi sekarang bisa mengubah `.env` lokal langsung tanpa perlu masuk ke flow Codex builder.
- Shortcut `status/start/stop/restart/log/health service ...` saat ini menarget `systemd --user`, jadi paling cocok untuk service yang memang dijalankan di level user.
- `cek health semua service penting` akan membaca daftar dari `IMPORTANT_SERVICES` di `.env`.
- Shortcut backend akan mencoba script `package.json`, target `Makefile`, atau tooling Python yang umum seperti `uv`, `poetry`, dan `pytest`.
- `rollback ke tag ...` memakai `git revert`, jadi lebih aman karena tidak mereset history branch secara destruktif.

## Multi-Device Phase 1

Yang sudah ada di fase ini:

- bot pusat bisa menerima `register` dan `heartbeat` dari agent device
- registry device disimpan di file lokal `codi-devices.json`
- Telegram bisa menampilkan daftar device online/offline
- query natural yang didukung:
  - `device yang online apa saja`
  - `status semua device`
  - `detail device laptop-kerja`
  - `/devices`

Cara menjalankan agent sederhana di device lain:

```bash
export CODI_CENTER_URL=http://IP-ATAU-DOMAIN-BOT-PUSAT:8787
export CODI_DEVICE_API_TOKEN=replace_with_shared_secret
export CODI_DEVICE_ID=laptop-kerja
export CODI_DEVICE_LABEL="Laptop Kerja"
export CODI_DEVICE_TYPE=desktop
export CODI_DEVICE_CAPABILITIES=shell,repo,system_activity,screenshot,desktop

python -m agent.main
```

Catatan:

- fase ini baru mencakup `registry + heartbeat`, belum task routing lintas device
- untuk host lain, port `DEVICE_API_PORT` harus bisa diakses dari agent
- gunakan secret yang kuat pada `DEVICE_API_SHARED_TOKEN`

## Commit / PR Assistant

Contoh prompt:

- `buat commit message untuk perubahan repo ini`
- `ringkas diff ini jadi deskripsi PR`
- `siapkan judul PR dan body PR untuk repo web-dashboard-payroll`
- `review diff lokal ini sebelum saya commit`

Catatan:

- V1 berbasis repo lokal yang bisa diakses Codi.
- Codi bisa membaca diff/status Git lokal lalu merangkum perubahan dalam bahasa manusia.
- Capability ini belum berarti Codi akan `git push` atau membuka PR remote otomatis.

## Repo Watch

Contoh prompt:

- `pantau repo ini`
- `pantau repo web-dashboard-payroll`
- `stop pantau repo ini`
- `repo yang dipantau apa`
- `di repo ini, perbaiki Codi agar /help lebih jelas`

Perilaku v1:

- Codi hanya memantau repo Git yang valid.
- Notifikasi dikirim saat branch berubah, HEAD berubah, atau status kerja lokal berubah.
- Polling berjalan di background lokal dan tidak memakai token Codex.

## Session Persistence

Session Codex sekarang dipertahankan untuk jalur kerja normal, jadi follow-up prompt terasa lebih dekat dengan pengalaman agent di IDE.

Catatan:

- Task edit sekarang memakai draft workspace yang hidup per konteks kerja, jadi revisi lanjutan tidak selalu mulai dari copy baru.
- Approval `lanjutkan` berfungsi sebagai checkpoint apply; setelah itu draft edit dan thread Codex untuk jalur write tetap dipertahankan.
- Balasan `batal` akan membuang revisi terakhir dan menyinkronkan draft kembali ke kondisi repo saat ini.
- Untuk repo Codi sendiri, setelah `lanjutkan`, Codi akan menjalankan `compileall` dan `unittest` lokal lebih dulu.
- Jika verifikasi lolos, Codi akan restart dirinya sendiri setelah mengirim respons final ke Telegram.

## Menjalankan Bot

```bash
source .venv/bin/activate
python main.py
```

## Menjalankan Test

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
```

## Struktur Ringkas

- `main.py`: bootstrap aplikasi Telegram
- `config.py`: load dan validasi environment
- `handlers/`: command dan message handlers
- `core/`: orchestration, routing, session management
- `models/`: data model session dan payload
- `utils/`: executor, formatter, logger
