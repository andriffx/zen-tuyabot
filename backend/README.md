# Zen Tuyabot — Backend

Backend untuk mengontrol perangkat Tuya (lampu, smart plug) lewat **bot Telegram** dan **REST API** untuk dashboard web. Satu proses menjalankan uvicorn, bot-bot Telegram, dan scheduler.

Frontend (SvelteKit) ada di `../frontend` dalam monorepo yang sama.

---

## Fitur

| Fitur | Keterangan |
|-------|-----------|
| Bot Telegram dinamis | Banyak bot sekaligus, token diatur dari UI, aktif/nonaktif per bot |
| Login multi-user | Akun web dengan password, sesi HttpOnly + CSRF, role diatur di UI |
| Role dinamis | Permission dicentang per role; Superadmin dilindungi |
| User web ≠ user Telegram | Dua entitas terpisah, berbagi role yang sama |
| Perangkat dinamis | Tambah/ubah/hapus dari API, pemetaan DPS per perangkat |
| Scan LAN | Temukan perangkat Tuya di jaringan lokal |
| Konfigurasi di database | `.env` hanya 4 kunci bootstrap |
| Backup & restore | `VACUUM INTO` otomatis + restore atomik dengan maintenance mode |
| Audit log | Siapa mengubah apa, kapan, hasilnya |
| Log & telemetri | Aktivitas, konsumsi daya, error aplikasi |

---

## Mulai cepat

### Tanpa Docker

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # Linux/macOS

pip install -r requirements-dev.txt
PYTHONPATH=src python -m tuyabot.main
```

Buka `http://127.0.0.1:8080/api/setup/status`. Instance baru menjawab:

```json
{"required": true, "steps_done": {"admin": false}}
```

### Dengan Docker

```bash
cd backend
mkdir -p data logs backup
docker compose up -d --build
curl http://127.0.0.1:8080/healthz
```

### Wizard pertama kali

1. `POST /api/setup` dengan `{"username": "...", "password": "..."}` — membuat akun Superadmin pertama. Hanya bisa sekali.
2. Login (`POST /api/auth/login`) lalu tambah bot Telegram (`POST /api/bots`) dan perangkat (`POST /api/devices`).

Sebelum setup selesai, semua endpoint `/api/*` selain setup/health/auth mengembalikan `409 setup_required`.

---

## Konfigurasi

`.env` **hanya** berisi empat kunci, semuanya opsional:

| Variabel | Default | Keterangan |
|----------|---------|-----------|
| `DATA_DIR` | `./data` | Database, secret sesi, dan backup |
| `API_HOST` | `127.0.0.1` | Alamat bind API |
| `API_PORT` | `8080` | Port API |
| `TZ` | `Asia/Makassar` | Zona waktu timestamp |

Semua konfigurasi lain — interval monitoring, retensi log, timeout Tuya, jam sesi, perilaku maintenance, tema UI — disimpan di tabel `app_settings` dan diubah lewat `GET/PATCH /api/settings`.

Token bot disimpan per baris di `telegram_bots` (bukan setting), dan hanya bisa ditulis, tidak pernah dibaca kembali lewat API.

---

## Perintah Telegram

| Perintah | Izin |
|----------|------|
| `/start`, `/help`, `/whoami` | publik |
| `/devices`, `/status` | `devices.view` |
| `/on <nama>`, `/off <nama>` | `devices.control` |
| `/logs` | `logs.view` |
| `/users`, `/adduser`, `/removeuser` | `telegram_users.view/manage` |

User Telegram yang tidak terdaftar hanya mendapat `/start` dan `/help`. Pendaftaran dilakukan dari dashboard atau oleh user dengan `telegram_users.manage`.

---

## Endpoint API

Dokumentasi lengkap ada di `../docs/superpowers/specs/2026-11-17-tuyabot-rebuild-design.md` §8.15. Ringkasnya:

| Grup | Path |
|------|------|
| Setup & auth | `/api/setup`, `/api/auth/*` |
| Role & permission | `/api/roles`, `/api/roles/permissions` |
| User web | `/api/web-users` |
| User Telegram | `/api/telegram-users` |
| Bot | `/api/bots` |
| Perangkat | `/api/devices`, `/api/devices/scan` |
| Log | `/api/logs/activities`, `/api/logs/power`, `/api/logs/errors` |
| Setting | `/api/settings` |
| Backup | `/api/backup` |
| Sistem | `/api/stats`, `/api/health`, `/api/audit`, `/api/maintenance` |
| Real-time | `/api/stream` (SSE) |

Autentikasi: cookie sesi `HttpOnly` untuk web (mutasi wajib `X-CSRF-Token`), atau header `X-API-Key` untuk skrip.

---

## Backup, restore, pindah mesin

Backup otomatis berjalan tiap `backup.interval_hours` (default 24 jam) ke `data/backups/`, dengan retensi `backup.retention_days`.

```bash
# manual
curl -X POST http://127.0.0.1:8080/api/backup -H "X-API-Key: ..."

# daftar
curl http://127.0.0.1:8080/api/backup -H "X-API-Key: ..."
```

**Restore** (`POST /api/backup/restore`) memerlukan izin `system.restore`, password ulang, dan konfirmasi teks `RESTORE`. Urutannya:

1. maintenance mode aktif;
2. `PRAGMA integrity_check` pada file yang diunggah;
3. backup versi lebih baru ditolak; versi lama dimigrasi pada salinannya;
4. backup `pre_restore` dibuat;
5. file database ditukar secara atomik, koneksi dibuka ulang;
6. cache di-reset dan bot dibangun ulang.

Jika ada langkah yang gagal, database lama tetap utuh dan maintenance tetap aktif.

**Pindah mesin:** unduh backup (`GET /api/backup/{id}/download`), jalankan instance baru, restore. File `secret.key` tidak ikut — sesi lama otomatis tidak berlaku.

---

## Pengembangan

```bash
pytest -q
ruff check .
```

Struktur:

```
src/tuyabot/
  main.py          # entry point
  config.py        # bootstrap env
  bootstrap.py     # data dir, secret, migrasi
  settings/        # registry + service
  storage/         # db.py, migrate.py, repos/, migrations/
  access/          # permissions, roles, passwords, sessions, rate_limit
  devices/         # dps, controller, service, registry
  telegram/        # manager, handlers, guards, watchdog
  web/             # app, deps, security, routes/
  infra/           # scheduler, state_cache, asyncdb
  backup/          # backup & restore
  maintenance/     # maintenance mode
```

Aturan yang dijaga test:

- tidak ada `sqlite3` di `web/` atau `telegram/` (`tests/test_no_sync_db.py`);
- route selalu async dan memakai `run_db`;
- secret tidak pernah muncul di respons API.

---

## Troubleshooting

**Perangkat offline.** Status mengembalikan `success: false` tanpa error 500. Periksa IP, `local_key`, dan versi protokol (3.1–3.5). `POST /api/devices/{id}/test` menampilkan DPS mentah.

**Bot error `Conflict: terminated by other getUpdates`.** Token yang sama aktif di dua tempat. Hentikan instance lama, atau pakai token berbeda untuk bot uji.

**Login tampak gagal setelah mengaktifkan `security.cookie_secure`.** Cookie `Secure` tidak dikirim lewat `http://`. Pakai HTTPS atau matikan setting itu untuk akses lokal.

**Dashboard selalu `409 setup_required`.** Setup belum selesai, atau database dipulihkan dari backup yang dibuat sebelum setup.
