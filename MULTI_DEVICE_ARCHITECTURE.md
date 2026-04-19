# Multi-Device Architecture Codi

Dokumen ini menjadi panduan pengembangan versi ideal Codi:
`1 bot Telegram pusat` yang berjalan stabil, bisa mendeteksi banyak device, lalu mengeksekusi task sesuai `device session` yang benar.

Fokus dokumen ini sengaja dibuat konservatif.
Tujuannya bukan langsung membuat sistem distributed yang kompleks, tetapi membangun fondasi yang aman dan bertahap agar pengembangan tidak penuh bug sejak awal.

## Tujuan

Target akhir yang ingin dicapai:

- Codi hanya punya `satu bot Telegram pusat`
- bot pusat bisa melihat daftar device yang online
- user bisa mengarahkan task ke device tertentu
- session kerja, repo aktif, dan approval tetap konsisten per device
- capability tiap device bisa berbeda, misalnya:
  - laptop: screenshot, desktop action, aplikasi aktif
  - VPS: service, deploy, repo, log
  - PC lain: repo lokal, shell, screenshot bila ada GUI

## Masalah Arsitektur Saat Ini

Arsitektur sekarang belum cocok untuk multi-device aktif bersamaan karena:

- bot Telegram masih memakai `long polling`
- state penting masih `in-memory` per proses
- belum ada `device registry`
- belum ada `shared storage` untuk session, case, approval, dan routing

Akibatnya, kalau satu token bot dijalankan di beberapa mesin sekaligus:

- instance akan bentrok `getUpdates`
- state user bisa pecah antar mesin
- approval atau context repo bisa tertukar
- tidak ada cara aman untuk tahu task harus dijalankan di device mana

## Prinsip Desain

- `Single Telegram ingress`
  Hanya bot pusat yang terhubung ke Telegram.
- `Many device agents`
  Setiap laptop, VPS, atau PC lain menjalankan agent lokal.
- `Explicit routing first`
  Fase awal harus mengutamakan target device yang eksplisit.
- `Shared state`
  Session, case, approval, dan audit tidak boleh bergantung pada memori proses tunggal.
- `Capability-based execution`
  Setiap device mendeklarasikan apa yang bisa dia lakukan.
- `Safety before convenience`
  Auto-routing baru ditambahkan setelah routing eksplisit stabil.

## Keputusan Utama

1. Bot Telegram pusat berjalan di VPS.
2. Token bot Telegram hanya dipakai oleh bot pusat.
3. Device lain tidak berbicara langsung ke Telegram.
4. Semua device lain berbicara ke pusat sebagai `agent`.
5. Semua state kerja penting dipindahkan ke storage bersama.

## Komponen Sistem

### 1. Central Bot

Komponen ini menerima semua pesan Telegram dan bertugas untuk:

- autentikasi user
- memahami intent
- memilih device target
- membuat task untuk agent
- menyimpan session per device
- menampilkan status device
- menjaga approval dan audit trail

Central bot adalah satu-satunya komponen yang memakai:

- `TELEGRAM_BOT_TOKEN`

### 2. Device Agent

Agent adalah proses kecil yang berjalan di setiap host.

Tugas agent:

- register ke pusat saat start
- kirim heartbeat berkala
- lapor capability host
- mengambil task yang ditujukan ke device itu
- menjalankan task secara lokal
- mengirim hasil kembali ke pusat

Contoh capability:

- `shell`
- `repo`
- `systemd`
- `desktop`
- `screenshot`
- `system_activity`
- `self_hosted_gui`

### 3. Shared State Store

State yang sebelumnya in-memory harus dipindahkan ke storage bersama.

Minimal yang perlu disimpan:

- `devices`
- `device_heartbeats`
- `device_capabilities`
- `user_active_device`
- `device_sessions`
- `cases`
- `pending_approvals`
- `repo_watches`
- `audit_events`
- `task_runs`

Untuk fase awal, database relasional sederhana seperti PostgreSQL paling cocok.

## Device Identity

Setiap agent harus punya identitas yang stabil:

- `device_id`
- `device_label`
- `device_type`
- `hostname`
- `platform`

Contoh:

- `device_id=laptop-kerja`
- `device_id=vps-hestia`
- `device_id=pc-rumah`

`device_id` harus tetap sama meski agent restart.
Jadi device ini bukan sekadar session sementara, tetapi identitas host yang nyata.

## Device Session

Konsep penting yang harus dipakai adalah `device session`.

Artinya:

- user bisa punya context berbeda di tiap device
- repo aktif di laptop tidak otomatis sama dengan repo aktif di VPS
- approval sensitif harus terkait ke device tertentu
- shell command harus dicatat dengan `user + device + session`

Contoh:

- di `laptop-kerja`, repo aktif = `AI-Agent-Telegram`
- di `vps-hestia`, repo aktif = `web-dashboard-payroll`

Dua context ini harus bisa hidup bersamaan tanpa saling menimpa.

## Rekomendasi Routing Tahap Awal

Tahap awal jangan langsung pakai auto-routing pintar.

Mulai dari `explicit target` seperti:

- `di device laptop-kerja, screenshot sekarang`
- `di device vps-hestia, cek service nginx`
- `di pc-rumah, pull repo ini`

Setelah itu baru ditambah helper seperti:

- `device aktif saya apa`
- `pakai device laptop-kerja`
- `ganti device aktif ke vps-hestia`
- `device yang online apa saja`

Dengan pendekatan ini:

- bug routing lebih kecil
- user bisa paham ke mana task dikirim
- debugging jauh lebih mudah

## Auto-Routing

Auto-routing sebaiknya baru datang setelah fase eksplisit stabil.

Contoh aturan nanti:

- kalau prompt butuh `screenshot`, pilih device dengan capability `screenshot`
- kalau prompt butuh `desktop action`, pilih device GUI
- kalau prompt butuh `service/deploy`, pilih device server

Tapi untuk fase awal, auto-routing cukup sebatas:

- memberi saran device yang cocok
- bukan langsung eksekusi tanpa target

## Transport Agent ke Pusat

Supaya aman dan mudah dideploy, agent sebaiknya memakai koneksi `outbound` ke pusat.

Model yang direkomendasikan:

- agent melakukan `heartbeat` periodik
- agent melakukan `task polling` ke pusat
- pusat tidak perlu membuka koneksi inbound ke laptop/PC user

Keuntungan model ini:

- lebih mudah melewati NAT/router rumah
- lebih aman untuk laptop pribadi
- implementasi awal lebih sederhana

## Fase Implementasi Aman

### Fase 0: Dokumen dan batas scope

Target:

- arsitektur disepakati
- istilah `central bot`, `device agent`, dan `device session` dibakukan
- out-of-scope fase awal ditulis jelas

Status:

- fase ini dilakukan lewat dokumen ini

### Fase 1: Device Registry dan Heartbeat

Target:

- bot pusat tahu device apa saja yang online
- tiap agent bisa register dan heartbeat
- user bisa melihat daftar device

Command yang ingin didukung:

- `device yang online apa saja`
- `status semua device`
- `detail device laptop-kerja`

Belum perlu:

- eksekusi task lintas device

### Fase 2: Explicit Device Targeting

Target:

- user bisa memilih device target secara eksplisit
- pusat bisa mengirim task sederhana ke agent yang benar

Task awal yang direkomendasikan:

- `status host`
- `shell read-only`
- `screenshot`

Belum perlu:

- edit repo
- self-update
- approval kompleks lintas device

Status repo saat ini:

- task queue JSON lokal untuk central bot sudah tersedia
- agent melakukan polling outbound ke pusat
- task awal yang didukung:
  - `status host`
  - schema SQLite bisnis read-only
  - query SQLite `SELECT/WITH` read-only
- hasil task dicek manual dari Telegram dengan `hasil task dt-xxxxxxxx`

### Fase 3: Device Session dan Context

Target:

- session aktif tersimpan per `user + device`
- repo aktif tersimpan per device
- case aktif tersimpan per device

Baru setelah ini, fitur repo lintas device mulai aman dibangun.

Status repo saat ini:

- active device tersimpan per user
- active repo tersimpan per `user + device`
- prompt awal yang didukung:
  - `pakai device absen-server`
  - `device aktif apa`
  - `di device absen-server, pakai repo /srv/absen`
  - `pakai repo /srv/absen`
  - `konteks device absen-server`
- task SQLite remote menerima repo context sebagai `cwd` dan agent bisa auto-discover SQLite di repo itu

Belum selesai:

- Codex session/case penuh belum dipindahkan ke storage device-aware
- approval sensitif lintas device belum device-aware

### Fase 4: Safety Layer Multi-Device

Target:

- approval sensitif menyebut device target
- audit log menyimpan `user`, `device`, `action`, `time`, `result`
- mode `aman/ops/admin` bisa berlaku per device session atau per user

### Fase 5: Capability Routing

Target:

- pusat bisa menyarankan device otomatis
- beberapa task bisa diarahkan berdasar capability host

Masih jangan dulu:

- free auto-routing untuk semua task write

## Yang Tidak Dikerjakan di Fase Awal

Sengaja ditunda dulu:

- dua bot Telegram aktif untuk satu sistem
- satu token bot dipakai banyak poller
- browser automation lintas device
- distributed edit approval yang sangat kompleks
- resume Codex thread lintas host
- sinkronisasi live desktop state antar host

## Risiko Utama

### 1. Wrong-device execution

Task bisa jalan di host yang salah.

Mitigasi:

- explicit target dulu
- balasan selalu menyebut device target
- approval write selalu menyebut device

### 2. Offline device di tengah task

Device bisa hilang saat task sedang berjalan.

Mitigasi:

- task status: `queued`, `running`, `failed`, `expired`
- heartbeat timeout
- retry policy sederhana

### 3. Context tertukar antar device

Repo aktif atau case aktif bisa tabrakan.

Mitigasi:

- session key harus mengandung `device_id`
- active repo harus disimpan per device

### 4. Capability mismatch

Pusat meminta screenshot ke VPS tanpa GUI.

Mitigasi:

- capability registry wajib
- validasi capability sebelum task dibuat

### 5. Approval ambiguity

User membalas `lanjutkan aksi`, tapi belum jelas aksi itu milik device mana.

Mitigasi:

- approval harus menyimpan `approval_id + device_id`
- balasan approval selalu menampilkan device target

## Skema Data Minimum

Tabel atau koleksi minimum yang perlu ada:

- `devices`
- `device_capabilities`
- `device_presence`
- `user_device_context`
- `cases`
- `sessions`
- `task_queue`
- `task_results`
- `pending_approvals`
- `audit_events`

## Contoh UX Fase Aman

Contoh flow yang sehat:

1. User kirim: `device yang online apa saja`
2. Codi balas: `laptop-kerja online, vps-hestia online, pc-rumah offline`
3. User kirim: `pakai device vps-hestia`
4. Codi balas: `device aktif sekarang vps-hestia`
5. User kirim: `cek health service nginx`
6. Codi balas hasil dengan label device: `Dieksekusi di vps-hestia`

Contoh write flow:

1. User kirim: `di device laptop-kerja, restart codi`
2. Codi balas preview + device target
3. User balas: `lanjutkan aksi`
4. Codi eksekusi hanya di `laptop-kerja`

## Urutan Kerja yang Direkomendasikan

Urutan implementasi yang paling aman:

1. buat dokumen arsitektur
2. tambah konsep `device_id`
3. buat registry dan heartbeat agent
4. tambah command status device
5. tambah explicit device targeting
6. pindahkan session dan case ke storage bersama
7. pindahkan safety approval ke storage bersama
8. baru tambahkan task execution lintas device
9. baru setelah stabil, tambahkan auto-routing ringan

## Acceptance Criteria Fase Aman

Fase aman dianggap berhasil jika:

- hanya ada satu bot Telegram pusat
- daftar device online terlihat dari Telegram
- user bisa memilih device target dengan jelas
- task read-only sederhana bisa dijalankan di device yang tepat
- context kerja tidak tertukar antar device
- approval sensitif menyebut device yang dituju
- audit log menyimpan siapa melakukan apa di device mana

## Rekomendasi Implementasi di Repo Ini

Kalau pengembangan dilanjutkan di repo ini, urutan file/module baru yang paling masuk akal:

- `core/device_registry.py`
- `core/device_router.py`
- `core/device_queue.py`
- `core/device_context.py`
- `core/agent_protocol.py`
- `agent/main.py`
- `agent/heartbeat.py`
- `agent/executor.py`
- `agent/capabilities.py`

Lalu fitur lama yang perlu diekstrak bertahap:

- `session_manager`
- `case_manager`
- `repo_watch`
- `safety`
- `edit_approval`

## Ringkasan Keputusan

Ringkasnya:

- versi ideal tetap sangat layak dibangun
- tetapi harus dimulai dari `single central bot`
- device lain harus menjadi `agent`, bukan bot Telegram tambahan
- fase awal harus `explicit device targeting`
- auto-routing dan kecerdasan routing baru masuk setelah fondasi stabil
