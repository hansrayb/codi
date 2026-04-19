# CI/CD Codi

Dokumen ini menjelaskan alur agar pembaruan Codi dari sisi agent maupun pusat otomatis diverifikasi dan bisa dideploy dari repository `ai-agent-telegram`.

## Alur yang Dipakai

1. Agent atau pusat membuat perubahan kode/data lalu push ke GitHub.
2. Workflow `Codi CI` otomatis berjalan untuk compile dan unit test.
3. Jika push masuk ke branch `main`, CI sukses, dan variable `CODI_DEPLOY_ENABLED=true`, workflow `Codi Deploy` menjalankan deployment ke host pusat lewat SSH.
4. Host pusat melakukan `git pull --ff-only`, install dependency, compile, test ulang, lalu restart service Codi.

## File Workflow

- `.github/workflows/codi-ci.yml`
  Menjalankan validasi pada `push`, `pull_request`, dan trigger manual.

- `.github/workflows/codi-deploy.yml`
  Menjalankan deploy setelah workflow `Codi CI` sukses pada push ke `main`, atau manual lewat `workflow_dispatch`.

## Secrets GitHub

Tambahkan repository variable berikut di GitHub repository:

- `CODI_DEPLOY_ENABLED`
  Isi `true` jika deploy otomatis sudah siap diaktifkan.

Tambahkan secrets berikut di GitHub repository:

- `CODI_DEPLOY_HOST`
  Host/IP server Codi pusat.

- `CODI_DEPLOY_USER`
  User SSH di server.

- `CODI_DEPLOY_SSH_KEY`
  Private key SSH yang punya akses ke server dan repository.

- `CODI_DEPLOY_PORT`
  Port SSH. Isi `22` jika memakai default.

- `CODI_APP_DIR`
  Path repo di server, misalnya `/home/odc/ai-agent-telegram`.

- `CODI_SERVICE_NAME`
  Nama systemd user service, misalnya `codi.service`.

## Syarat di Host Pusat

Host pusat harus sudah punya:

- Clone repo `ai-agent-telegram`.
- Virtual environment `.venv`.
- File `.env` lokal, tidak masuk Git.
- Remote Git yang bisa diakses oleh user deploy.
- Service systemd user yang bisa direstart dengan `systemctl --user restart`.

Contoh setup service:

```bash
systemctl --user daemon-reload
systemctl --user enable codi.service
systemctl --user start codi.service
```

## Branch Policy yang Disarankan

- Perubahan dari agent masuk ke branch fitur atau PR.
- `Codi CI` wajib sukses sebelum merge.
- Deploy otomatis hanya dari `main`.
- Data runtime seperti `.env`, `codi-devices.json`, log, dan audit log tetap lokal dan tidak dipush.

## Integrasi dengan Fitur Codi Saat Ini

Codi sudah punya self-update lokal: saat Codi mengubah repo dirinya sendiri, ia compile, test, lalu restart jika lolos. CI/CD ini melengkapi alur tersebut di level repository remote, sehingga perubahan dari device/agent lain tetap diverifikasi GitHub sebelum masuk deploy pusat.
