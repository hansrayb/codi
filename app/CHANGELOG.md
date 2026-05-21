# Changelog

Semua perubahan user-facing dicatat di sini. Format: [Keep a Changelog](https://keepachangelog.com/),
versioning [SemVer](https://semver.org/).

## [Unreleased]

### Changed

- **Brand color**: gold → biru-cyan (sesuai logo aplikasi). Token `gold*`
  dipertahankan namanya (legacy) tapi nilainya kini biru.
- **Theme**: dark-only → **light & dark** (ikut sistem). `AppColors` jadi
  ThemeExtension `AppPalette`, diakses via `context.colors.X` (resolve
  per theme). 29 file widget dimigrasi. Override brief (`02-SPEC.md`
  dark-only Phase 1) atas permintaan user.

### Added

- Scaffolding Fase 0: struktur project Flutter, dependencies (`pubspec.yaml`),
  lint strict (`analysis_options.yaml`), folder structure feature-first
  sesuai `docs/05-ARCHITECTURE.md`, skeleton `main.dart` + `app.dart`.
- Fase 1 Foundation: design system (`lib/theme/` — colors, typography,
  spacing, radius, elevation, `AppTheme.darkTheme` dark-only) sesuai
  `docs/03-DESIGN-SYSTEM.md`.
- Common widgets (`lib/widgets/`): `EmasCard`, `EmasElevatedCard`,
  `EmasButton` (primary/secondary/ghost), `EmasInput`, `EmasAvatar`,
  `EmasAlert`, `EmasSkeleton`/`EmasLoadingCard`, `EmasErrorView`,
  `EmasEmptyView` — masing-masing dengan widget test.
- Galeri widget dev-only (`lib/dev/widget_gallery.dart`) untuk verifikasi
  visual via `flutter run` (sementara, diganti Login di Fase 1 Minggu 2).
- Dashboard (Beranda) — layout match mockup `docs/emas-berlian-insight.html`:
  greeting header, period selector, hero summary card (sparkline fl_chart +
  live dot blink), stats row (delta color logic), AI summary card, chart
  card (bar chart fl_chart retail/rotasi), highlight list. Pull-to-refresh,
  shimmer loading, error state. Bottom nav + FAB Codi (visual only).
  Mock data via `DashboardController` (backend belum ada).
- Formatter `CurrencyFormatter` (Rp titik ribuan + compact jt/M) &
  `DateFormatter` (locale id_ID) + unit test.
- Chat screen — layout match mockup `docs/emas-berlian-insight.html`:
  header (Codi avatar SVG + status), message bubble (user navy / bot
  bgCard), rich card (badge + rows trend-colored + inline sparkline +
  action buttons), suggestion chips, chat input (pill + mic + send).
  Mock conversation + canned reply (backend belum ada). Dashboard FAB
  Codi → Chat. Token baru `AppRadius.r24`, `AppSpacing.s10`.
