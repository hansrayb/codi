# ai-agent-telegram — Claude Code Guidelines

## Workflow: Plan First, Execute After Approval

Sebelum mengeksekusi perubahan apapun, selalu:
1. Presentasikan rencana lengkap (file apa yang diubah, bagian mana, apa efeknya)
2. Tunggu user bilang "lanjut", "go", "ok execute", atau sejenisnya
3. Baru eksekusi semua perubahan sekaligus tanpa interrupt di tengah jalan

Jangan minta approval per-file saat eksekusi berlangsung. Approval dilakukan sekali di awal.

## Konfirmasi

- Jika butuh konfirmasi → tanya langsung dalam teks di conversation, bukan referensi ke tombol/GUI/interface eksternal
- Jangan sebut "klik Allow" atau instruksi berbasis UI yang mungkin tidak ada

## Stack

- Python, python-telegram-bot
- Backend AI: Claude (Anthropic) dan/atau Codex (OpenAI)
- Dijalankan sebagai systemd service (`codi.service`)

## Struktur Direktori

- `handlers/` — Telegram command & message handlers
- `core/` — Session management, orchestrator
- `agent/` — AI backend integration
- `models/` — Data models
- `utils/` — Utilities
- `config.py` — Konfigurasi utama
