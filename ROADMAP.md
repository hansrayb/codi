# Roadmap Codi

Dokumen ini menjadi panduan arah pengembangan Codi ke depan.
Fokus utama saat ini adalah membuat pengalaman `Telegram end-to-end` benar-benar matang, stabil, dan cukup kuat untuk dipakai bekerja tanpa harus membuka laptop atau IDE.

## Visi

Codi dibangun dengan dua channel utama:

1. `Telegram assistant`
   Tujuan: menjadi remote working assistant untuk coding, review, debugging, observability, dan self-maintenance dari chat.
2. `Dashboard assistant`
   Tujuan: muncul sebagai AI chat di aplikasi tertentu, memahami konteks halaman aktif, lalu membantu menjalankan aksi bisnis atau CRUD yang aman.

Urutan pengerjaan:

1. Selesaikan `Telegram end-to-end`.
2. Ekstrak capability inti Codi agar reusable.
3. Tambahkan channel baru untuk dashboard.

## Keputusan Produk Saat Ini

Keputusan utama untuk fase sekarang:

- Telegram adalah channel utama.
- Semua flow penting harus bisa selesai dari chat Telegram.
- Edit kode harus tetap aman lewat approval `lanjutkan` atau `batal`.
- Self-update Codi harus bisa dilakukan dari Telegram.
- Fitur dashboard assistant belum menjadi fokus implementasi utama.

## Kondisi Saat Ini

Capability yang sudah ada:

- Routing role otomatis: `builder`, `reviewer`, `debugger`, `ops`, `general`
- Resolusi repo dari path, nama repo, atau konteks kerja aktif
- Session dan case persistence
- Draft edit dengan approval sebelum apply
- Self-update workflow untuk repo Codi sendiri
- Observability host: aplikasi aktif, background process, log runtime
- Repo watch
- Bantuan commit message dan PR summary berbasis repo lokal
- Desktop action dasar untuk buka aplikasi GUI tertentu

Capability yang belum ada:

- In-app chat widget di dashboard
- Browser automation atau kontrol halaman web live
- Structured business actions untuk CRUD data aplikasi
- Action-level authorization untuk operasi bisnis di dashboard
- Audit log khusus untuk aksi AI di dashboard

## Fokus Fase 1: Telegram End-to-End

Tujuan fase ini:

- Pengguna bisa bekerja dari Telegram tanpa membuka VS Code.
- Codi bisa memahami repo target dengan minim gesekan.
- Flow edit, review, debug, dan self-update terasa natural.
- Reliability bot cukup tinggi untuk dipakai sehari-hari.

### Hasil yang ingin dicapai

Pengguna bisa melakukan hal-hal berikut hanya dari Telegram:

- meminta Codi mengubah repo tertentu
- meminta review atau debugging untuk repo tertentu
- melihat status laptop atau log Codi
- meminta Codi merevisi dirinya sendiri
- menyetujui atau membatalkan perubahan
- melanjutkan konteks kerja yang tadi tanpa kehilangan arah

### Prioritas implementasi

1. Kejelasan prompt dan respons Telegram
   Balasan harus ringkas, natural, dan tidak terlalu teknis.
2. Repo targeting yang kuat
   Pengguna harus mudah mengarahkan Codi ke repo yang benar.
3. Approval UX
   Preview perubahan harus jelas sebelum `lanjutkan`.
4. Reliability runtime
   Bot harus mudah start, restart, dan recover.
5. Self-update yang aman
   Setelah apply ke repo Codi, verifikasi dan restart harus konsisten.
6. Observability yang berguna
   Jawaban status host harus fokus ke informasi yang benar-benar membantu.

### Acceptance criteria fase 1

Fase Telegram dianggap cukup matang jika:

- edit repo biasa bisa dilakukan end-to-end dari Telegram
- edit repo Codi sendiri bisa dilakukan end-to-end dari Telegram
- approval flow stabil dan mudah dipahami
- repo aktif atau repo target jarang salah
- bot restart tidak membingungkan pengguna
- error message membantu, bukan sekadar teknis
- dokumentasi operasional cukup untuk start, stop, dan recovery

## Backlog yang Direkomendasikan untuk Telegram

Urutan backlog yang disarankan:

1. Perjelas prompt template untuk edit repo dan self-update
2. Rapikan copywriting approval agar lebih mudah dipahami user non-teknis
3. Tambahkan command atau flow untuk cek repo aktif saat ini
4. Tambahkan command atau flow untuk memilih repo aktif dengan lebih eksplisit
5. Perbaiki service management agar Codi mudah dijalankan sebagai service yang stabil
6. Tambahkan logging runtime yang lebih mudah dibaca saat startup gagal
7. Tambahkan dokumentasi contoh prompt Telegram yang efektif
8. Tambahkan proteksi untuk kasus self-update gagal verifikasi

## Yang Sengaja Ditunda

Hal-hal berikut sengaja tidak menjadi fokus sekarang:

- membuat assistant langsung muncul di dashboard
- automation klik browser
- CRUD data live ke aplikasi bisnis
- multi-user dashboard agent dengan role bisnis yang kompleks
- integrasi approval bisnis berbasis UI dashboard

Alasannya:

- Telegram core masih lebih penting untuk dimatangkan
- channel dashboard akan jauh lebih mudah dibangun jika core Codi sudah stabil
- action bisnis live membawa risiko yang lebih tinggi dibanding edit repo

## Arah Fase 2: Dashboard Assistant

Setelah Telegram matang, Codi bisa diperluas menjadi assistant di dashboard seperti `web-dashboard-payroll`.

Tujuan fase ini:

- Codi muncul sebagai chat panel di dalam dashboard
- Codi memahami halaman aktif dan konteks user
- Codi membantu CRUD tertentu dengan approval yang jelas

### Prinsip desain fase dashboard

- Jangan mengandalkan klik browser bebas sebagai fondasi utama.
- Gunakan action atau API yang eksplisit dan di-whitelist.
- Bedakan jelas antara `ubah kode aplikasi` dan `ubah data live`.
- Semua aksi mutasi harus punya preview atau konfirmasi.
- Semua aksi penting harus tercatat di audit log.

### Arsitektur yang disarankan

1. `Codi Core`
   Berisi orchestration, approval, context, dan policy yang reusable.
2. `Telegram Channel`
   Tetap dipertahankan sebagai remote operator interface.
3. `Dashboard Channel`
   Frontend chat widget + backend API yang mengirim konteks halaman ke Codi Core.
4. `Business Action Layer`
   Sekumpulan aksi aman seperti create, update, delete untuk domain tertentu.

### Contoh use case fase dashboard

- `Buat employee baru`
- `Ubah payroll period`
- `Hapus draft payroll`
- `Tampilkan siapa saja employee yang belum punya rekening`

Semua use case di atas sebaiknya tidak dijalankan lewat browser automation mentah, tetapi lewat action backend yang jelas.

## Prinsip Pengembangan

- Utamakan flow yang benar-benar dipakai sehari-hari.
- Tambah capability sedikit demi sedikit, jangan lompat ke sistem yang terlalu besar.
- Hindari fitur yang terlihat canggih tapi sulit dioperasikan dari sudut pandang user.
- Simpan approval sebagai pengaman utama untuk semua aksi write.
- Pisahkan `observasi`, `usulan perubahan`, dan `apply perubahan`.
- Buat semua channel baru tetap memakai core yang sama, bukan logika terpisah.

## Definisi Selesai untuk Fase Telegram

Fase ini bisa dianggap selesai jika Codi sudah terasa seperti:

- asisten kerja jarak jauh yang stabil
- bisa mengubah dirinya sendiri dari Telegram
- bisa bekerja lintas repo tanpa sering salah target
- punya respons yang nyaman untuk user non-teknis
- tidak mengharuskan user kembali ke IDE untuk task-task rutin

## Catatan Implementasi Selanjutnya

Saat mengembangkan fitur baru, evaluasi dulu:

1. Apakah ini memperkuat flow Telegram end-to-end?
2. Apakah ini lebih cocok sebagai capability core atau capability channel?
3. Apakah ini termasuk edit kode, observasi, atau aksi bisnis live?
4. Apakah approval dan audit trail-nya sudah jelas?
5. Apakah user bisa memahami hasilnya tanpa bahasa yang terlalu teknis?

## Ringkasan Keputusan

Ringkasan arah kerja:

- sekarang: fokus `Telegram end-to-end`
- setelah matang: ekstrak `Codi Core`
- berikutnya: bangun `dashboard assistant` untuk use case CRUD yang aman dan terstruktur

