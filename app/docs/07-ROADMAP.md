# 07 — ROADMAP.md

Fase pengerjaan, milestone, dan urutan implementasi untuk Emas Berlian Insight.

---

## Timeline Overview

| Fase | Durasi | Tujuan |
|---|---|---|
| **Fase 0** | 1 minggu | Backend prep + project setup |
| **Fase 1** | 2 minggu | Foundation + Login + Dashboard |
| **Fase 2** | 2 minggu | Chat + Insight |
| **Fase 3** | 1 minggu | Polish + Testing + Pilot |
| **Fase 4** | Ongoing | Iteration based on usage |

Total estimasi: **~6 minggu** untuk MVP siap di tangan Bapak Leo.

---

## Fase 0 — Persiapan (1 minggu)

### Backend (Codi) Prep

Sebelum mulai Flutter, pastikan Codi backend siap:

#### Endpoint yang harus ada

- [ ] `POST /api/v1/auth/login` — device-based authentication
- [ ] `POST /api/v1/auth/refresh` — token refresh
- [ ] `POST /api/v1/auth/logout`
- [ ] `GET /api/v1/me` — current user info
- [ ] `GET /api/v1/dashboard/summary?period=...` — dashboard data
- [ ] `GET /api/v1/dashboard/insight?period=...` — detail insight
- [ ] `POST /api/v1/chat/messages` — send to Codi (with SSE option)
- [ ] `GET /api/v1/chat/conversations` — list
- [ ] `GET /api/v1/chat/conversations/{id}/messages` — history

#### Device Enrollment Flow

- [ ] Admin panel atau script untuk enroll device baru
- [ ] Generate device fingerprint hash
- [ ] Whitelist Bapak Leo's iPhone (atau device test)

#### Auth & Security

- [ ] JWT issuer setup (HS256 or RS256)
- [ ] Token TTL configuration (7 hari)
- [ ] Refresh token rotation
- [ ] Rate limiting per device

#### Pre-existing functionality yang harus tetap kerja

- [ ] Telegram bot tetap berfungsi (jangan break)
- [ ] HR/business data masih bisa diakses
- [ ] Service watch & alerts tetap jalan

### Flutter Project Setup

- [ ] Buat folder `apps/emas-berlian-insight/` di repo codi
- [ ] `flutter create` dengan org `id.lumbungemas`
- [ ] Setup flavor: dev, staging, prod
- [ ] Configure `analysis_options.yaml` sesuai `05-ARCHITECTURE.md`
- [ ] Add dependencies di pubspec sesuai list
- [ ] Setup folder structure sesuai `05-ARCHITECTURE.md`
- [ ] Setup `.gitignore` untuk Flutter
- [ ] Add `CHANGELOG.md`

### CI/CD Setup

- [ ] `.github/workflows/flutter-ci.yml` — lint + test
- [ ] `.github/workflows/flutter-build.yml` — build APK + IPA
- [ ] Codemagic atau Fastlane setup untuk TestFlight distribution
- [ ] Firebase App Distribution setup untuk Android

### Acceptance Criteria Fase 0

- ✅ Codi backend mengembalikan response sample untuk semua endpoint
- ✅ Flutter project compile dan run di iOS simulator + Android emulator
- ✅ CI workflow pass untuk dummy commit

---

## Fase 1 — Foundation + Login + Dashboard (2 minggu)

### Minggu 1: Foundation

#### Day 1-2: Theme & Design System

- [ ] Implement `lib/theme/app_colors.dart` — semua color token
- [ ] Implement `lib/theme/app_typography.dart` — semua text style
- [ ] Implement `lib/theme/app_spacing.dart`, `app_radius.dart`, `app_elevation.dart`
- [ ] Compose `lib/theme/app_theme.dart` — `ThemeData darkTheme`
- [ ] Setup `google_fonts` (Inter, Fraunces, JetBrains Mono)
- [ ] Test theme di test app

**Definition of done**: tap-able test screen render dengan theme.

#### Day 3-4: Common Widgets

- [ ] `EmasCard`
- [ ] `EmasButton` (3 variants)
- [ ] `EmasInput`
- [ ] `EmasAvatar`
- [ ] `EmasAlert`
- [ ] `EmasLoading` (shimmer)
- [ ] `EmasErrorView`
- [ ] `EmasEmptyView`

**Definition of done**: widget test untuk setiap widget pass. Visual review di storybook (kalau ada) atau test app.

#### Day 5: API Layer

- [ ] `lib/config/env.dart`
- [ ] `lib/api/api_client.dart` — Dio setup
- [ ] Interceptors: auth, logging, retry
- [ ] `lib/api/api_exception.dart`
- [ ] Provider setup di `lib/providers/api_client_provider.dart`

**Definition of done**: API client bisa fetch ke endpoint dummy & handle error.

### Minggu 2: Login + Dashboard

#### Day 1-2: Login Screen

- [ ] Model: `User`, `AuthState`, `LoginRequest`, `LoginResponse`
- [ ] Repository: `AuthRepository`
- [ ] Controller: `AuthController` (Riverpod)
- [ ] Screen: `LoginScreen` dengan biometric flow
- [ ] Widgets: `BiometricButton`, `LoginLogo` (custom SVG)
- [ ] Secure storage integration
- [ ] Error handling lengkap

**Acceptance**:
- Biometric prompt muncul saat tap
- Sukses biometric + API mock = navigate ke dashboard
- Token tersimpan di secure storage
- Auto-login saat app re-open (token belum expired)

#### Day 3-5: Dashboard Screen

- [ ] Models: `DashboardSummary`, `QuickStats`, `AiSummary`, `Highlight`, `ChartData`
- [ ] Repository: `DashboardRepository`
- [ ] Controller: `DashboardController`
- [ ] Screen: `DashboardScreen`
- [ ] Widgets:
  - [ ] `GreetingHeader`
  - [ ] `PeriodSelector`
  - [ ] `SummaryCard` (hero with sparkline)
  - [ ] `StatsRow`
  - [ ] `AiSummaryCard`
  - [ ] `DailyChart` (fl_chart bar chart)
  - [ ] `HighlightList`
- [ ] Pull-to-refresh
- [ ] Shimmer loading state
- [ ] Error state + retry

**Acceptance**:
- Dashboard load data dari mock API
- Pull-to-refresh works
- Period change → reload
- Loading → success → error transition smooth
- Visual match dengan mockup

### Acceptance Criteria Fase 1

- ✅ Login screen berfungsi end-to-end (biometric → token → navigate)
- ✅ Dashboard menampilkan data real dari Codi backend
- ✅ Period filter berfungsi
- ✅ Pull-to-refresh, loading state, error state semuanya works
- ✅ `flutter analyze` zero warning
- ✅ `flutter test` semua pass
- ✅ Visual match dengan mockup minimal 90%

---

## Fase 2 — Chat + Insight (2 minggu)

### Minggu 3: Chat Screen

#### Day 1-2: Chat Models & API

- [ ] Models: `ChatMessage`, `Conversation`, `RichCard`, `RichRow`, `InlineChart`, `RichAction`
- [ ] Repository: `ChatRepository`
- [ ] SSE streaming support di Dio
- [ ] Controller: `ChatController`
- [ ] Conversation list provider

#### Day 3-5: Chat UI

- [ ] Screen: `ChatScreen`
- [ ] Widgets:
  - [ ] `MessageBubble` (user + bot variant)
  - [ ] `RichCardWidget` (with chart inline)
  - [ ] `SuggestionChips`
  - [ ] `ChatInput`
  - [ ] `CodiAvatar` (custom SVG)
- [ ] Streaming response handler
- [ ] History scroll & pagination
- [ ] Keyboard handling (avoid overlap)

**Acceptance**:
- Kirim pesan → terima response (streaming or non-streaming)
- Rich card render dengan benar
- Suggestion chips clickable
- History scrollable

### Minggu 4: Insight Screen + Polish

#### Day 1-2: Insight Screen

- [ ] Models: `InsightData`, `Kpi`, `Composition`, `AnalysisSection`
- [ ] Repository method `getInsight`
- [ ] Controller: `InsightController`
- [ ] Screen: `InsightScreen`
- [ ] Widgets:
  - [ ] `KpiGrid`
  - [ ] `CompositionDonut` (fl_chart pie)
  - [ ] `AnalysisCard`
- [ ] Share/export button (placeholder Phase 2)
- [ ] Deep link from chat ("Tanya Codi →")

#### Day 3-4: Bottom Nav Shell

- [ ] `ShellScaffold` dengan persistent bottom nav
- [ ] `EmasBottomNav` widget
- [ ] `EmasFab` (Codi)
- [ ] Route configuration di `go_router`
- [ ] Transition animation between tabs

#### Day 5: Cross-feature polish

- [ ] Deep linking
- [ ] Pull-to-refresh consistency
- [ ] Empty states semua screen
- [ ] Error states semua screen

### Acceptance Criteria Fase 2

- ✅ Chat berfungsi end-to-end dengan Codi backend
- ✅ Rich card render konsisten dengan response server
- ✅ Streaming response smooth (jika SSE enabled)
- ✅ Insight screen menampilkan data lengkap
- ✅ Navigation antar screen via bottom nav works
- ✅ Deep link dari card "Lihat Detail" navigate dengan benar
- ✅ `flutter test` pass
- ✅ `flutter analyze` zero warning

---

## Fase 3 — Polish + Testing + Pilot (1 minggu)

### Day 1-2: QA & Bug Fix

- [ ] Manual testing semua flow di iOS device real
- [ ] Manual testing semua flow di Android device real
- [ ] Fix bug yang muncul
- [ ] Performance profiling — startup time, memory, jank

### Day 3: Final Polish

- [ ] App icon (iOS + Android) via `flutter_launcher_icons`
- [ ] Splash screen via `flutter_native_splash`
- [ ] Onboarding hints (Phase 2 — bisa skip kalau time-constrained)
- [ ] Final review dengan checklist `02-SPEC.md`

### Day 4: Distribution Setup

- [ ] Build IPA, upload ke TestFlight
- [ ] Build APK, upload ke Firebase App Distribution
- [ ] Setup beta tester: Bapak Leo (+ Bapak/Ibu Komisaris jika perlu)
- [ ] Kirim install link via WhatsApp (Android) atau email TestFlight (iOS)

### Day 5: Pilot Launch

- [ ] Session onboarding 30 menit dengan Bapak Leo
- [ ] Live walkthrough setiap screen
- [ ] Tunjukkan biometric setup, pull-to-refresh, chat dengan Codi
- [ ] Setup feedback channel (WhatsApp / dedicated Codi conversation)

### Acceptance Criteria Fase 3

- ✅ App installable di iPhone Bapak Leo via TestFlight
- ✅ App installable di Android device test via Firebase
- ✅ Onboarding session berhasil — Bapak Leo bisa pakai mandiri setelahnya
- ✅ Performance budget terpenuhi (cold start <2s, dashboard <2s)
- ✅ Zero crash di pilot session

---

## Fase 4 — Iteration (Ongoing)

### Weekly cadence

Setiap minggu (atau 2 minggu) di awal pilot:

1. **Review feedback** dari Bapak Leo (text, voice, atau langsung tanya)
2. **Monitor crash report** dari Sentry/Firebase
3. **Identify** 1-3 improvement priority
4. **Ship** improvement dalam batch kecil
5. **Communicate** changelog ke user

### Phase 2 Feature Backlog (after MVP)

Priority akan ditentukan based on usage data + Bapak Leo's feedback:

| Feature | Priority | Estimasi |
|---|---|---|
| Push notification (daily summary, anomaly) | High | 1 minggu |
| Reports screen (PDF generation, share) | High | 2 minggu |
| Profile & settings | Medium | 1 minggu |
| Search dalam chat history | Medium | 3 hari |
| Voice input | Medium | 1 minggu |
| English language toggle | Low | 3 hari |
| Light mode | Low | 1 minggu |
| Onboarding screens (first time) | Low | 3 hari |
| Widget homescreen (iOS) | Low | 1 minggu |
| Offline mode improvement | Medium | 1 minggu |
| Analytics dashboard (PostHog/Mixpanel) | Medium | 3 hari |

---

## Risk Register

Hal-hal yang bisa nge-slow-down progress:

| Risk | Impact | Mitigation |
|---|---|---|
| Backend endpoint belum siap | High | Pre-build endpoint di Fase 0, jangan tunda |
| Biometric flow issue di device tertentu | Medium | Test early di multiple device, fallback PIN (Phase 2) |
| Streaming response complexity | Medium | Implement non-streaming first, streaming sebagai enhancement |
| iOS distribution complexity (Apple Dev Account) | High | Setup developer account hari pertama Fase 0 |
| Codi backend response slow (>5s) | Medium | Add caching aggressive, optimize backend separately |
| Bapak Leo's feedback radical change UX | Medium | Build modular biar mudah refactor |
| Solo developer bottleneck | High | Document everything, jangan rely on hidden knowledge |

---

## Definition of Success

App ini dianggap berhasil jika setelah 1 bulan pilot:

1. ✅ Bapak Leo membuka app **minimal 5x per minggu**
2. ✅ **>50% interaksi** via chat dengan Codi (mengindikasikan organic adoption)
3. ✅ **Zero blocker bug** dilaporkan
4. ✅ Response time Codi **stay <3 detik avg**
5. ✅ Feedback Bapak Leo: "Lebih nyaman dari Telegram"

Jika tidak terpenuhi, lakukan **post-mortem** dan iterate based on data, bukan asumsi.

---

## Communication Plan

### Dengan Bapak Leo (User)

- **Onboarding day**: 30 menit walkthrough live
- **Week 1**: Cek setiap 2 hari "Apakah ada kendala?"
- **Week 2-4**: Cek mingguan
- **Channel**: WhatsApp atau dedicated Codi conversation

### Dengan Internal Team (jika ada)

- **Daily standup** kalau ada team — atau journal kalau solo
- **Weekly demo** — tunjukkan progress visible
- **Sprint review** setiap 2 minggu

### Dengan Anthropic / Claude Code

- Jaga dokumentasi `docs/` always up to date — itu yang akan dibaca Claude saat next session
- Setelah selesai milestone besar, update `CHANGELOG.md` + summary di `07-ROADMAP.md`

---

## Tracking & Visibility

Pakai issue tracker (GitHub Issues atau Linear):

- Label: `app:flutter`, `phase:N`, `priority:high/med/low`
- Milestone per Fase
- Project board: To Do → In Progress → Review → Done

Tidak perlu over-engineer process. **Yang penting: setiap task punya owner, deadline, dan definition of done.**
