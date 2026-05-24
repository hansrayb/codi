# Emas Berlian Insight

Aplikasi Flutter mobile eksekutif untuk Direktur Utama Lumbung Emas — client
**read-only** yang konsumsi REST API backend Codi (`hansrayb/codi`).

## Status

Fase 0 — scaffolding (struktur project, deps, skeleton). Belum ada fitur.
Lihat `docs/07-ROADMAP.md`.

## Dokumentasi

Sumber kebenaran ada di `docs/` — baca `docs/01-CLAUDE.md` lebih dulu.

| File | Isi |
|---|---|
| `docs/01-CLAUDE.md` | Instruksi entry-point |
| `docs/02-SPEC.md` | Spesifikasi fungsional |
| `docs/03-DESIGN-SYSTEM.md` | Color/typography/spacing tokens |
| `docs/04-API-CONTRACT.md` | Endpoint backend Codi |
| `docs/05-ARCHITECTURE.md` | Folder structure + state management |
| `docs/06-SCREENS.md` | Detail per-screen |
| `docs/07-ROADMAP.md` | Fase & milestone |
| `docs/08-TESTING.md` | Strategi test |

## Stack

Flutter 3.41+ · Dart 3.11+ · Riverpod 2 · go_router · dio · freezed · fl_chart ·
local_auth · flutter_secure_storage.

## Setup

```bash
cd app
flutter pub get
flutter analyze
flutter test
```

## Flavor (Android)

Setelah flavor di-setup, `flutter run`/`build` **wajib** `--flavor`:

```bash
# dev (app id .dev, label "EBI Dev")
flutter run --flavor dev --dart-define=ENV=dev

# tes ke backend lokal di HP (IP LAN laptop)
flutter run --flavor dev \
  --dart-define=API_BASE_URL=http://<ip-laptop>:8787/api/v1 \
  --dart-define=CODI_SHARED_TOKEN=<token>

# build prod
flutter build apk --release --flavor prod --dart-define=ENV=prod
```

dev/staging/prod terpasang berdampingan (suffix application id berbeda).
iOS flavor butuh setup scheme di Xcode (belum dikonfigurasi).
Base URL & env: `lib/config/env.dart`.
