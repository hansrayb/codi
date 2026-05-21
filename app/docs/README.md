# Emas Berlian Insight — Project Brief

Aplikasi Flutter mobile untuk Direktur & Owner, menampilkan ringkasan operasional kantor dan asisten percakapan **Codi**. App ini adalah **client read-only** yang terhubung ke backend Codi (`hansrayb/codi`) via REST API.

## Status

- Stage: **Concept → Implementation**
- Target user: 1 orang (Bapak Leo Sastra C.W., Direktur Utama)
- Cakupan: 1 kantor operasional
- Platform: Flutter (iOS + Android), distribusi internal

## Struktur Folder Dokumentasi

```
docs/emas-berlian-insight/
├── README.md                       # File ini
├── 01-CLAUDE.md                    # Instruksi untuk Claude Code (entry point)
├── 02-SPEC.md                      # Spesifikasi fungsional lengkap
├── 03-DESIGN-SYSTEM.md             # Palette, typography, spacing, components
├── 04-API-CONTRACT.md              # Endpoint backend Codi yang dipanggil
├── 05-ARCHITECTURE.md              # Struktur folder Flutter & state management
├── 06-SCREENS.md                   # Detail per-screen (4 screen utama)
├── 07-ROADMAP.md                   # Fase pengerjaan & milestone
└── 08-TESTING.md                   # Strategi test & quality gate
```

## Cara Pakai Dokumen Ini dengan Claude Code

### Setup pertama kali

1. Buka VSCode di repo `codi-main`
2. Buat folder baru: `apps/emas-berlian-insight/`
3. Copy semua file `.md` ini ke `apps/emas-berlian-insight/docs/`
4. Buka Claude Code (Cmd/Ctrl + L atau via Claude Code extension)
5. Mulai dengan prompt:

   ```
   Baca semua file di docs/ folder ini. Mulai dari 01-CLAUDE.md.
   Setelah paham konteks, konfirmasi pemahaman Anda sebelum mulai code.
   ```

### Workflow yang disarankan

**Phase 1 — Setup project**
```
"Setup Flutter project sesuai 05-ARCHITECTURE.md. Buat folder structure,
pubspec.yaml dengan dependencies yang disebut, dan main.dart skeleton.
Belum perlu logic apapun, hanya scaffolding."
```

**Phase 2 — Design system**
```
"Implement design system dari 03-DESIGN-SYSTEM.md sebagai theme/tokens
di lib/theme/. Buat ThemeData lengkap dengan color, typography, dan
common widget styles."
```

**Phase 3 — Per-screen implementation** (1 screen per session)
```
"Implement Login screen sesuai 06-SCREENS.md bagian Login.
Ikuti pattern di 05-ARCHITECTURE.md untuk state management."
```

**Phase 4 — API integration**
```
"Integrate ApiClient dengan endpoint di 04-API-CONTRACT.md.
Implement error handling sesuai 02-SPEC.md bagian Error States."
```

**Phase 5 — Testing**
```
"Tulis test sesuai 08-TESTING.md untuk Login screen, dashboard,
dan ApiClient."
```

### Tips

- **Jangan kasih Claude Code semua dokumen sekaligus** untuk implementasi. Berikan per phase.
- **Selalu reference dokumen** di prompt: "sesuai 03-DESIGN-SYSTEM.md section X"
- **Konfirmasi pemahaman dulu** sebelum minta Claude tulis code besar
- **Gunakan agen Builder/Reviewer** di Codi jika sudah set up — agen reviewer akan baca code yang ditulis Builder
- Untuk **refactor**, selalu sertakan reference ke architecture document

## Backend Dependency

App ini **tidak bisa berjalan tanpa Codi backend**. Sebelum implementasi mobile dimulai:

1. Pastikan Codi backend (`hansrayb/codi`) sudah expose REST API endpoints
2. Endpoint yang dibutuhkan ada di `04-API-CONTRACT.md`
3. Authentication via JWT yang di-issue oleh Codi

Bila endpoint belum ada, prioritaskan menambahkan endpoint dulu di Codi sebelum mulai Flutter app.

## Kontak & Pemilik

- **Project owner**: Hans Raynanda (`@hansrayb`)
- **End user**: Bapak Leo Sastra C.W. (Direktur Utama)
- **Backend repo**: `hansrayb/codi`
- **Versi dokumen**: 1.0 — Mei 2026
