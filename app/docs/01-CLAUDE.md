# 01 — CLAUDE.md

Instruksi entry-point untuk Claude Code saat bekerja di project **Emas Berlian Insight**.

---

## Kamu sedang bekerja di mana

Kamu adalah **Claude Code** yang ditugaskan membangun aplikasi Flutter `emas-berlian-insight` — sebuah mobile app eksekutif untuk Direktur Utama Lumbung Emas (Bapak Leo Sastra C.W.).

App ini **sub-project di dalam repo `hansrayb/codi`**, ditempatkan di folder `apps/emas-berlian-insight/`.

Backend tetap Codi (Python, Telegram bot + REST API). App ini adalah **client baru** yang konsumsi API yang sama.

---

## Prinsip Kerja

### 1. Plan first, code second

Untuk setiap task non-trivial:
1. Baca dokumen yang relevan di `docs/` terlebih dahulu
2. Jelaskan rencana: file mana yang dibuat/diedit, dependencies, urutan kerja
3. Tunggu konfirmasi user ("lanjut", "ok", "go")
4. Eksekusi tanpa interrupt

### 2. Documentation is the source of truth

- Spesifikasi: `02-SPEC.md`
- Design tokens: `03-DESIGN-SYSTEM.md` — **jangan invent warna/spacing baru**
- API endpoint: `04-API-CONTRACT.md` — **jangan invent endpoint, tanya kalau kurang**
- Folder structure: `05-ARCHITECTURE.md` — **ikuti, jangan reorganize**
- Screen detail: `06-SCREENS.md`

Jika ada konflik antar dokumen, **tanya user**. Jangan asumsi.

### 3. Read-only first

App ini **read-only by design**. Tidak ada tombol "Approve", "Submit", "Delete", "Create" untuk data bisnis. Jika user (developer atau end-user) minta fitur write, **konfirmasi dulu** — kemungkinan itu fitur untuk role lain, bukan untuk Direktur.

### 4. Formal tone in UI

- Bahasa Indonesia, formal
- Sapaan: "Bapak Leo Sastra C.W." atau "Bapak"
- Hindari emoji di body text
- Hindari informal/gen-z language
- Numeric format: titik ribuan (`Rp 5.000.000`)
- Date format: `17 Mei 2026` atau `17/05/2026`, konsisten

### 5. Quality bar

- **Setiap widget custom** harus punya `Widget` test minimal
- **Setiap screen** harus handle 3 state: loading, success, error
- **Setiap API call** harus punya timeout dan error message yang user-friendly
- **Setiap warna/spacing** harus pakai design tokens, bukan magic number

---

## Stack Teknis

| Komponen | Pilihan |
|---|---|
| Framework | Flutter 3.24+ |
| Dart SDK | 3.5+ |
| State management | Riverpod 2.x |
| Routing | go_router |
| HTTP client | dio |
| Local storage | flutter_secure_storage (token), shared_preferences (cache) |
| Biometric | local_auth |
| Charts | fl_chart |
| Date/time | intl |
| Lint | flutter_lints + custom analysis_options.yaml |

Detail dependencies di `05-ARCHITECTURE.md`.

---

## Yang TIDAK Boleh Dilakukan

### Fitur

- ❌ Tambah fitur write/action tanpa konfirmasi (approve, submit, delete)
- ❌ Hardcode credential atau secret di code
- ❌ Pakai library di luar list di `05-ARCHITECTURE.md` tanpa diskusi
- ❌ Pakai warna/font/spacing di luar `03-DESIGN-SYSTEM.md`
- ❌ Implement custom auth (gunakan biometric + JWT dari Codi)
- ❌ Buat folder `assets/` dengan asset yang sembarangan — minta confirmation untuk asset

### Code

- ❌ Pakai `dynamic` type (selalu strong-typed)
- ❌ Pakai `print()` di production code — gunakan logger
- ❌ Skip `null` check untuk data dari API
- ❌ Mutate state tanpa lewat Riverpod
- ❌ Inline styles di widget — pakai theme/tokens

### Git

- ❌ Commit langsung ke `main` — selalu via PR
- ❌ Commit file `.env` atau secret apapun
- ❌ Push tanpa konfirmasi user

---

## Yang HARUS Dilakukan

### Sebelum mulai code

- ✅ Baca dokumen yang relevan
- ✅ Konfirmasi pemahaman tugas
- ✅ Identifikasi dependencies & file yang akan disentuh

### Saat code

- ✅ Strong typing untuk semua variable
- ✅ Error handling di setiap API call
- ✅ Loading state di setiap async UI
- ✅ Pakai design tokens dari `03-DESIGN-SYSTEM.md`
- ✅ Tulis dartdoc comment untuk public API
- ✅ Buat widget test minimum untuk widget custom

### Setelah code

- ✅ Jalankan `flutter analyze` — harus zero warning
- ✅ Jalankan `flutter test` — harus pass
- ✅ Format dengan `dart format .`
- ✅ Update CHANGELOG jika ada perubahan user-facing

---

## Workflow per Task

```
1. User kasih task ("implement login screen")
2. Claude baca dokumen relevan (01-CLAUDE.md, 06-SCREENS.md, 03-DESIGN-SYSTEM.md)
3. Claude buat plan:
   - File yang dibuat: lib/features/auth/presentation/login_screen.dart
   - File yang diedit: lib/router.dart (add route), lib/main.dart
   - Dependencies: local_auth (sudah di pubspec)
   - Test: test/features/auth/login_screen_test.dart
4. Claude minta konfirmasi user
5. User konfirmasi: "lanjut"
6. Claude code semua sekaligus
7. Claude jalankan flutter analyze + test
8. Claude report: "selesai, semua test pass, ada 0 warning"
```

---

## Konteks Bisnis (Penting untuk Codi-related features)

Lumbung Emas adalah perusahaan jual-beli emas fisik & sistem rotasi investor:

- **Produk emas**: EMSC, DINAR DKR, DINAR HARAMAIN, EMAS MILI, THR, CUSTOM SERIES, GIFT SERIES
- **Sistem rotasi**: Investor titip emas 1000g, diputar ke pembeli tiap siklus, komisi Rp 35.000/bulan/unit
- **Tier mitra**: CUSTOMER → MITRA_BINAAN → MITRA_UTAMA → MITRA_PRIORITAS
- **Transaksi**: BELI_EMAS_REGULER, BELI_EMAS_DAFTAR, BUYBACK, ROTASI
- **Status**: LUNAS, PENDING, EXPIRED, DIBATALKAN

Saat menampilkan data di UI, gunakan terminology di atas. Jangan terjemahkan ke generic ("buying gold" / "investment program") — gunakan term aslinya.

---

## Saat Stuck / Tidak Yakin

Jangan asumsi. Pilih salah satu:

1. **Tanya user** dengan pertanyaan yang spesifik
2. **Baca ulang dokumen** yang relevan
3. **Cari pattern serupa** di code yang sudah ada
4. **Tawarkan opsi** kalau ada beberapa cara: "saya bisa lakukan A atau B, A lebih cepat tapi B lebih maintainable, pilih mana?"

Tidak ada yang lebih buruk daripada code yang **kelihatan benar tapi sebenarnya salah arsitektur**. Slow is smooth, smooth is fast.

---

## File Reference Map

| Pertanyaan | Buka file |
|---|---|
| Apa yang harus dibuat? | `02-SPEC.md` |
| Warna apa untuk button primary? | `03-DESIGN-SYSTEM.md` |
| Endpoint mana untuk login? | `04-API-CONTRACT.md` |
| File ditaruh di folder mana? | `05-ARCHITECTURE.md` |
| Layout screen Login seperti apa? | `06-SCREENS.md` |
| Apa yang dikerjakan minggu ini? | `07-ROADMAP.md` |
| Bagaimana cara test fitur ini? | `08-TESTING.md` |
