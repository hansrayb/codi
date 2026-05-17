# Changelog

Semua perubahan user-facing dicatat di sini. Format: [Keep a Changelog](https://keepachangelog.com/),
versioning [SemVer](https://semver.org/).

## [Unreleased]

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
