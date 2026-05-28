# Prompt Claude CLI — Aktifkan Backend Auth Fase B di Server

Copy-paste prompt di bawah ini ke `claude -p "<prompt>"` di **mesin server** tempat Codi running (atau via Telegram ke Codi dengan role `ops`).

---

## Prompt

```
Aktifkan modul auth + RBAC backend Fase B di service Codi (hansrayb/codi).
Commit terakhir: 14ce7af "feat(codi): mobile auth + RBAC backend (Fase B)".

Lakukan dengan urutan persis ini, JANGAN skip step, dan STOP minta konfirmasi
kalau ada error:

1) Cek working directory adalah /home/hans/AI-Agent-Telegram (atau lokasi
   service Codi). Jalankan `git status` dulu — kalau ada uncommitted
   changes yang bukan punya saya, STOP dan laporkan; jangan overwrite.

2) Pull update dari main:
   git fetch origin
   git log --oneline HEAD..origin/main
   git pull --ff-only origin main
   Pastikan commit 14ce7af ada di HEAD.

3) Aktifkan venv yang Codi pakai (cek dengan `systemctl cat codi.service`
   untuk lihat ExecStart-nya). Install deps baru:
   pip install -r backend/requirements.txt
   Verifikasi: `python -c "import bcrypt, jwt; print(bcrypt.__version__, jwt.__version__)"`
   harus print "4.2.0 2.9.0".

4) Edit .env (BUKAN .env.example). Tambahkan baris berikut kalau belum
   ada. Untuk CODI_JWT_SECRET pakai secret yang sudah ada di .env kalau
   sudah pernah di-set; kalau belum, generate baru:
   
       python -c "import secrets; print(secrets.token_hex(32))"
   
   Variabel yang wajib:
       CODI_JWT_SECRET=<hasil token_hex>
       CODI_JWT_ACCESS_TTL_MINUTES=10080
       CODI_JWT_REFRESH_TTL_DAYS=30
       AUTH_DB_PATH=/home/hans/AI-Agent-Telegram/backend/data/codi-auth.db
       SUPERADMIN_EMAIL=hans@emasberlian.com
       SUPERADMIN_PASSWORD=<minta user input lewat prompt interaktif; min 8 char;
                            JANGAN print/log password ini ke output>
       SUPERADMIN_NAME=Hans
       SUPERADMIN_TITLE=Super Admin
       ALLOW_BOOTSTRAP_TOKEN=true
   
   Catatan keamanan: kalau .env sudah ter-version-control (cek
   `git check-ignore .env`) — STOP, jangan lanjut. .env wajib gitignored.

5) Bikin direktori data + jalankan seed superadmin:
       mkdir -p /home/hans/AI-Agent-Telegram/backend/data
       cd /home/hans/AI-Agent-Telegram/backend
       python -m scripts.seed_auth
   
   Output harus print:
       [ok] Schema siap di .../codi-auth.db
       [ok] Seed roles: ['admin', 'director', 'superadmin', 'viewer']
       [ok] Superadmin dibuat: id=acc_..., email=hans@emasberlian.com, role=superadmin
   
   Kalau "[skip] Superadmin sudah ada" — itu OK, lanjut. Kalau error,
   STOP dan tunjukkan stderr lengkap.

6) Jalankan smoke test backend dari folder backend/:
       python -m pytest tests/test_auth.py tests/test_mobile_api.py -q
   Harus 55 pass (36 auth + 19 mobile_api). Kalau ada fail, STOP.

7) Restart service Codi:
       sudo systemctl restart codi.service
       sleep 2
       sudo systemctl status codi.service --no-pager | head -20
   
   Status harus "active (running)". Cek log startup:
       journalctl -u codi.service -n 60 --no-pager | grep -E "auth_service_ready|action=device_api_started|ERROR"
   
   Cari baris "action=auth_service_ready" — itu konfirmasi AuthService
   sudah live. Kalau ada ERROR atau auth_service_ready tidak muncul,
   STOP dan paste error-nya.

8) End-to-end smoke test pakai curl (ganti <port> sesuai
   DEVICE_API_PORT di .env, default 8787; ganti <pw> dengan password
   superadmin tanpa quote):

   # Login email superadmin
   curl -sS -X POST http://127.0.0.1:<port>/api/v1/auth/login \
        -H 'Content-Type: application/json' \
        -d '{"email":"hans@emasberlian.com","password":"<pw>"}' | python -m json.tool
   
   Harus return access_token + refresh_token + user.role="superadmin" +
   scopes mengandung "accounts:create".
   
   # Ambil access_token dari output, lalu list accounts:
   TOKEN=<paste access_token>
   curl -sS http://127.0.0.1:<port>/api/v1/accounts \
        -H "Authorization: Bearer $TOKEN" | python -m json.tool
   
   Harus return list dengan minimal 1 akun (hans).

9) Laporkan ringkasan:
   - Commit aktif di server (sha + subject)
   - Versi deps yang ter-install
   - Status systemd codi.service
   - Hasil pytest (X passed)
   - Verifikasi login HTTP OK / fail
   - Lokasi file codi-auth.db + ukuran

Jangan modify file di luar .env + buat folder data/. Jangan push commit
apapun. Kalau ada step gagal, kembalikan output mentahnya, jangan
ngarang fix tanpa konfirmasi user.
```

---

## Catatan untuk user

1. Pastikan **superadmin password** disiapkan dulu (min 8 char, kuat). Akan diminta interaktif oleh Claude saat step 4.
2. Kalau `.env` belum gitignored di server, **tolak step 4** — fix `.gitignore` dulu sebelum lanjut.
3. Setelah selesai, mobile app legacy (Fase A1) yang masih pakai `CODI_SHARED_TOKEN` masih jalan (read-only). Fase C (mobile UI login email + S7) belum di-build di app/lib — jadwalkan session terpisah.
