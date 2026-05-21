# 02 — SPEC.md

Spesifikasi fungsional lengkap untuk **Emas Berlian Insight**.

---

## Tujuan Produk

Memberikan akses cepat & ringkas ke informasi operasional kantor Lumbung Emas kepada Direktur Utama, kapanpun & dimanapun, tanpa harus membuka dashboard web atau bertanya ke tim.

### Goal yang Terukur

- **TTI (Time to Insight)**: < 5 detik dari buka app sampai melihat ringkasan kondisi hari ini
- **Refresh latency**: data dashboard < 2 detik dari tap refresh
- **Chat response**: Codi balas < 3 detik untuk pertanyaan sederhana, < 10 detik untuk analisis kompleks
- **Offline graceful**: data terakhir tetap bisa dilihat saat offline

### Bukan Tujuan

- ❌ Aplikasi untuk operasional harian (Marketing, Kemitraan, HRGA) — itu role lain
- ❌ Aplikasi customer-facing — itu produk berbeda
- ❌ Replacement untuk dashboard web admin (yang masih dipake operasional)
- ❌ Approval/decision flow (write actions) — semua aksi tetap via channel resmi (Telegram → tim operasional → eksekusi)

---

## User Persona

### Primary User: Bapak Leo Sastra C.W.

- **Role**: Direktur Utama Lumbung Emas
- **Usia**: 45–55 tahun
- **Tech comfort**: Medium — pakai iPhone, familiar WhatsApp & Telegram, tidak buka VS Code
- **Konteks penggunaan**: Saat meeting, di mobil, di rumah, pagi sebelum kerja
- **Kebutuhan utama**:
  1. Tahu kondisi operasional terkini (omzet, pertumbuhan, anomali)
  2. Lihat ringkasan tanpa interpretasi angka manual
  3. Tanya ad-hoc ke Codi untuk dive deeper
  4. Akses cepat tanpa friction (biometric, no password)

### Secondary User: (Future) Owner / Komisaris

- Mungkin pakai app yang sama di masa depan
- Untuk sekarang fokus ke 1 user, scope creep dihindari

---

## Feature List

### Phase 1 (MVP) — 4 Screen Utama

#### F1.1 — Login Screen

- Logo + brand name "Emas Berlian Insight"
- Biometric authentication (Face ID iOS / Fingerprint Android)
- Token JWT dari Codi tersimpan di flutter_secure_storage
- Auto-login jika token belum expired
- Tagline: "Executive Business Intelligence"
- Footer: "Akses Khusus Direksi · v1.0.0"

**State**:
- `initial` — baru buka app
- `authenticating` — biometric prompt aktif
- `authenticated` — sukses, navigate ke dashboard
- `failed` — gagal, show error + retry button
- `locked` — terlalu banyak failed attempt, locked 5 menit

#### F1.2 — Dashboard (Beranda)

Konten:
1. **Top nav**: Greeting + avatar
2. **Period selector**: Hari / Minggu / Bulan Ini / Tahun
3. **Hero summary card**: Omzet + sparkline + trend MoM
4. **Quick stats row**: 3 stat (Order, Conv. Rate, Beban)
5. **AI Summary card**: Codi summary 2-3 paragraf
6. **Chart 7 hari terakhir**: Bar chart retail vs rotasi
7. **Sorotan section**: 3-5 highlight item dengan color-coded severity
8. **Bottom nav**: 5 item dengan FAB Codi di tengah

**Data refresh**:
- Auto-refresh saat app foreground (jika terakhir refresh > 5 menit)
- Pull-to-refresh manual
- Show "diperbarui X menit lalu" timestamp

#### F1.3 — Chat dengan Codi

Konten:
1. **Header**: Avatar Codi + status (Aktif/Sibuk) + response time avg
2. **Messages list**: Conversation history
3. **Rich card support**: Codi bisa kirim card dengan tabel + chart inline
4. **Suggestions chips**: 3-4 follow-up question yang relevan
5. **Input bar**: Text input + voice button + send button

**Behavior**:
- Streaming response (token by token, kalau backend support)
- History tersimpan local + sync ke backend
- Search dalam history (Phase 2)
- Voice input via speech-to-text native (Phase 2)

#### F1.4 — Insight (Analisis Mendalam)

Konten:
1. **Hero**: Period label + Live indicator
2. **KPI grid**: 4 cell (Omzet, Order, Avg Ticket, Potensi Hilang)
3. **Donut chart**: Komposisi omzet (retail vs rotasi)
4. **AI Analysis**: Codi summary 3 paragraf — Sehat / Perhatian / Catatan

**Behavior**:
- Period sync dengan Dashboard
- Tap "Tanya Codi →" navigate ke Chat dengan pre-filled context

### Phase 2 — Enhancement

- F2.1 — Laporan: PDF report generation (harian/mingguan/bulanan)
- F2.2 — Profil & Settings: Theme override, language, notification prefs
- F2.3 — Notifikasi: Daily summary push, anomaly alerts
- F2.4 — Export: Share insight via WhatsApp/Email
- F2.5 — Search di chat history

---

## State Management — Required States

Setiap screen yang load data harus handle 3 state minimal:

### Loading State

- Skeleton screen (bukan spinner kosong)
- Match layout final screen
- Animate dengan shimmer effect

### Success State

- Render data
- Show "diperbarui X menit lalu"
- Pull-to-refresh available

### Error State

- Friendly message (jangan tampilkan stack trace)
- Tombol "Coba lagi"
- Fallback: tampilkan data cache terakhir + banner "Menampilkan data terakhir karena offline"

### Empty State (jika applicable)

- Illustration sederhana
- Pesan jelas: "Belum ada data untuk periode ini"
- Suggest action

---

## Error Handling

### Network Errors

| Error | UX |
|---|---|
| Timeout (>30s) | "Sambungan lambat, sedang mencoba ulang..." + auto-retry 1x |
| No internet | Banner "Tidak ada koneksi internet" + tampilkan data cache |
| Server 5xx | "Layanan sedang tidak tersedia. Tim teknis sudah diberitahu." + retry button |
| Auth 401 | Auto logout + navigate ke Login dengan message "Sesi habis, silakan login ulang" |
| Server 4xx (lainnya) | Tampilkan error message dari API kalau aman, atau generic |

### Biometric Errors

| Error | UX |
|---|---|
| Cancelled by user | Stay di Login screen, no error |
| No biometric enrolled | "Aktifkan Face ID/Fingerprint di settings device" |
| Too many failed | Lock 5 menit, countdown timer di Login |
| Hardware unavailable | Fallback message + contact admin |

### Data Errors

| Error | UX |
|---|---|
| Data corrupted | Skip item yang corrupt, log error, render rest |
| Field hilang | Show "—" atau "N/A" |
| Decimal/format aneh | Default ke 0 atau "—" |

---

## Internationalization

- **Bahasa**: Indonesia (default & only untuk Phase 1)
- **Locale**: `id_ID`
- **Currency**: IDR dengan format `Rp 1.000.000,00`
- **Date**: `17 Mei 2026` (long) atau `17/05/2026` (short)
- **Time**: 24-hour, `14:30`

Struktur file string di `lib/l10n/`. Hardcoded string di widget = code smell, pakai key dari l10n.

Phase 2: dukungan English jika diperlukan.

---

## Accessibility

Untuk MVP:

- **Touch target**: minimum 44x44pt (iOS HIG)
- **Color contrast**: minimum AA (4.5:1 untuk text)
- **Semantic labels**: setiap interactive widget punya semantic label
- **Font scaling**: support sampai 200% tanpa break layout

Tidak diprioritaskan di MVP tapi tidak boleh dirusak: VoiceOver/TalkBack support.

---

## Performance Budget

| Metric | Target |
|---|---|
| Cold start | < 2 detik (sampai login screen visible) |
| Login → Dashboard | < 1.5 detik |
| Dashboard data load | < 2 detik |
| Chat send → first token | < 1 detik |
| Chat send → full response | < 5 detik (avg) |
| App size (APK) | < 30 MB |
| Memory usage steady | < 200 MB |

Jika ada feature yang melanggar budget, **redesign** sebelum ship.

---

## Privacy & Security

### Data sensitif

App ini menampilkan:
- Omzet & data keuangan (high sensitivity)
- Data karyawan (medium-high sensitivity)
- Conversation dengan Codi (medium sensitivity)

### Yang harus ada

- ✅ Biometric lock setiap buka app (no remember-me untuk login)
- ✅ Auto-lock setelah 5 menit idle di foreground
- ✅ Token JWT disimpan di `flutter_secure_storage` (Keychain iOS / Keystore Android)
- ✅ HTTPS only ke backend Codi
- ✅ Tidak ada logging data sensitif ke crash reporter
- ✅ Screen recording protection (block screenshot di iOS preview, FLAG_SECURE di Android)
- ✅ Remote wipe capability — kalau token revoked di backend, app logout

### Yang tidak boleh

- ❌ Cache angka sensitif tanpa encryption
- ❌ Kirim data ke third-party analytics (untuk Phase 1)
- ❌ Hardcode endpoint atau secret di code
- ❌ Allow root/jailbreak detection bypass

---

## Observability

App perlu kirim ke backend:

- **Crash report**: nama event, stack trace (Sentry atau Firebase Crashlytics)
- **Performance metric**: cold start time, screen load time
- **Custom event**: login_success, login_failed, chat_sent, screen_viewed (anonymous, no PII)

Tidak kirim:
- Content pertanyaan ke Codi (privacy)
- Angka spesifik dari dashboard
- Nama user

---

## Acceptance Criteria (untuk Phase 1 selesai)

App dianggap MVP-complete jika:

1. ✅ 4 screen utama berfungsi sesuai spec
2. ✅ Biometric login berhasil di iOS + Android device test
3. ✅ Dashboard load data dari Codi backend dengan benar
4. ✅ Chat dengan Codi berfungsi end-to-end (kirim, terima, render)
5. ✅ Offline mode menampilkan cache + indicator
6. ✅ Semua test pass: `flutter test`
7. ✅ Zero warning: `flutter analyze`
8. ✅ App size < 30 MB
9. ✅ Performance budget terpenuhi
10. ✅ Distribusi via TestFlight (iOS) + Firebase App Distribution (Android) berhasil ke Bapak Leo
