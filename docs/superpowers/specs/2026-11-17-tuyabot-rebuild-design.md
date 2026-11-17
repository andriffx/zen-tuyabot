# Desain — Rebuild Tuya Telegram Bot + Dashboard (Backend Python, Frontend Svelte)

Tanggal: 2026-11-17
Status: draft untuk persetujuan (revisi 3: role dinamis, bot token dinamis, user web & Telegram terpisah)

## 1. Intent dan kenapa

Proyek lama (`referensi/tuya-telegram-bot-main`, `referensi/tuya-telegram-bot-new-patch`)
mencampur bot Telegram dan dashboard web dalam satu aplikasi, dengan konfigurasi di `.env`
dan daftar perangkat di kode (`config.py`). Setiap perubahan kecil — tambah perangkat, ubah
threshold watchdog, ganti token bot — berakhir di edit file dan restart service.

Yang dibangun sekarang adalah **aplikasi baru dari nol**, bukan fork:

- satu monorepo `zen-tuyabot`: `backend/` (Python) dan `frontend/` (SvelteKit + shadcn-svelte),
- database baru, tanpa migrasi data atau kode lama,
- `.env` seminimal mungkin; semua konfigurasi operasional diatur dari UI dan disimpan di DB,
- fitur inti: login multi-user, **role dinamis dengan izin yang dicentang dari UI**,
  **bot Telegram dinamis (banyak token, bisa dipilih/diaktifkan)**, CRUD perangkat (termasuk
  scan LAN), settings editor, backup/restore/pindah DB, log & telemetri, status real-time.

Repo lama hanya dipakai sebagai pelajaran: lock I/O per perangkat, state cache dengan TTL dan
single-flight, SSE, scheduler tunggal, backup `VACUUM INTO`, dan test yang mengunci perilaku.

## 2. Goals

1. Menjalankan bot-bot Telegram dan REST API dalam **satu proses** sehingga satu pemilik lock
   perangkat Tuya.
2. Dashboard web yang bisa dipakai tanpa menyentuh server: login, tambah/ubah perangkat,
   kontrol, kelola role, **kelola user web dan user Telegram (dua entitas terpisah)**,
   kelola bot token, lihat log, ubah setting, backup dan restore.
3. Konfigurasi tersimpan di DB, dengan validasi tipe dan semantik di server; perubahan
   diterapkan sesuai mode "apply" masing-masing setting.
4. Skema DB dan kode siap tumbuh: migration runner bernomor, registry setting bertipe,
   registry device generik (tidak hardcode "air"/"lampu"), katalog permission tetap.
5. Deploy sederhana: dua container (backend + frontend statis), volume untuk data/log/backup,
   container backend non-root dan read-only.

## 3. Non-goals

- Migrasi data dari MySQL/SQLite lama, atau kompatibilitas nama tabel lama.
- Kontrol perangkat via Tuya Cloud; hanya protokol lokal (`tinytuya` 3.1–3.5).
- Multi-instansi / multi-rumah / HA cluster. Satu instance = satu rumah.
- Aplikasi mobile native, plugin pihak ketiga, atau marketplace integrasi.
- SSR dashboard. Frontend adalah SPA statis; tidak ada server Node di produksi.
- Enkripsi at-rest untuk secret di DB (lihat 8.6 untuk batasannya).
- Permission granular per field (mis. "boleh ubah device X tapi hanya field IP"). Izin
  berlaku per domain aksi, lihat 8.7.

## 4. Anti-goals

Build dianggap gagal walau "jalan" kalau:

- Dashboard dan bot membaca sumber konfigurasi berbeda sehingga status/izin bisa menyimpang.
- Menambah device atau mengganti bot token masih membutuhkan edit file atau restart container.
- Ada jalur yang memungkinkan pemilik role tanpa `users.manage` membuat/mengubah user.
- Ada jalur yang memungkinkan user memberi dirinya sendiri izin yang tidak ia miliki.
- Secret (token bot, local key) tampil penuh di UI atau tersimpan di `localStorage`.
- Restore backup bisa meninggalkan proses dengan koneksi DB setengah-tertutup atau data
  setengah-tertulis.

## 5. Konstrain

- Python 3.11+, `python-telegram-bot` 22.x, `tinytuya`, FastAPI, SQLite (stdlib `sqlite3`).
- Tidak ada broker eksternal, Redis, atau MySQL.
- Backend tetap satu proses: bot polling (bisa beberapa bot) + uvicorn + scheduler.
- Frontend: SvelteKit + Svelte 5, Tailwind, shadcn-svelte, adapter-static.
- Repo: monorepo `zen-tuyabot`; backend di `backend/`, frontend di `frontend/`.

## 6. Pendekatan yang dipertimbangkan

**A. Rebuild bersih, satu proses bot+API, config DB, role dinamis, FE terpisah — dipilih.**
Kode lama tidak diimpor. Bagian yang dulu hardcode digeneralisasi sejak awal, sehingga tidak
ada dua sumber kebenaran.

**B. Evolusi kode `new-patch` in-place + FE baru — dibuang.**
Membawa warisan hardcode (`air`/`lampu`, import-time config, role angka 0–3 yang kaku) ke
dalam aplikasi yang justru harus dinamis.

**C. Bot dan API dua service terpisah — dibuang.**
Dua proses berebut lock, koneksi, dan cache perangkat. Menuntut broker/owner. Tidak sepadan
untuk satu rumah.

Keputusan tambahan yang diambil bersamamu:

- Login: multi-user. **Hanya Superadmin yang dibuat saat setup**, akun web lain dibuat olehnya.
  Tidak ada self-registration.
- **User web dan user Telegram adalah dua entitas berbeda.** User web punya username/password
  dan login ke dashboard; user Telegram dikenali lewat `telegram_id` dan hanya berinteraksi
  dengan bot. Keduanya memakai katalog role/izin yang sama, tetapi disimpan di tabel berbeda
  dan tidak bisa saling login.
- Role **tidak lagi angka tetap**: role didefinisikan di DB dengan izin yang dicentang dari
  UI. Role seed disediakan agar dashboard langsung bisa dipakai.
- Bot token dinamis: banyak bot bisa disimpan; satu atau beberapa bisa aktif bersamaan.
- Wizard first-run: ya. Sebelum setup selesai, API hanya melayani endpoint setup dan health.
- Seed perangkat: tidak ada. Device ditambahkan lewat UI atau hasil scan.

## 7. Arsitektur

```
Browser ──> nginx (tuyabot-fe, SPA) ──/api──> FastAPI ──> SQLite (data/tuyabot.db)
                                                       ├─> Telegram Bot A (Application)
                                                       ├─> Telegram Bot B (Application)  [opsional, mis. bot uji]
                                                       └─> Scheduler (cache, power, backup, housekeeping)
                                                             └─> tinytuya ──> perangkat lokal
```

- FE dan BE adalah repo/container berbeda; nginx memproxy `/api` ke backend sehingga cookie
  sesi same-origin dan **tidak perlu CORS** di produksi.
- Dev: Vite dev server memproxy `/api` ke `http://127.0.0.1:8080`.

### 7.1 Struktur backend

```
backend/
  pyproject.toml, requirements.txt, requirements-dev.txt
  Dockerfile, entrypoint.sh, docker-compose.yml
  .env.example
  src/tuyabot/
    main.py                 # satu proses: bootstrap → DB → API → bots → scheduler
    config.py               # HANYA bootstrap env (8.1)
    bootstrap.py            # DATA_DIR, secret sesi, buka DB, jalankan migrasi
    settings/
      registry.py           # definisi setting bertipe (8.5)
      service.py            # baca/tulis, cache, validasi, event perubahan
      secrets.py            # masking nilai sensitif untuk API
    storage/
      db.py                 # koneksi per thread + generation counter (restore)
      migrations/0001_init.sql, ...
      repos/                # web_users, telegram_users, roles, sessions, api_keys,
                            # bots, devices, device_settings, logs, backups, settings
    access/
      permissions.py        # katalog izin (kode) + aturan evaluasi
      roles.py              # role dari DB, cache, guard hierarki
      passwords.py, sessions.py, rate_limit.py
    devices/
      registry.py, service.py, controller.py, dps.py
    telegram/
      manager.py            # start/stop/rebuild per bot, banyak Application
      app.py                # membangun Application dari baris telegram_bots
      handlers/             # start, help, devices, control, admin, callback
    web/
      app.py, deps.py
      routes/               # setup, auth, roles, users, bots, devices, settings,
                            # logs, backup, stats, stream, api_keys, health
    infra/
      scheduler.py, state_cache.py, asyncdb.py, events.py
  tests/
```

### 7.2 Struktur frontend (`../tuyabot-fe`)

```
src/
  routes/
    +layout.svelte, +layout.ts        # auth guard (client), toast host
    setup/+page.svelte                 # wizard first-run
    login/+page.svelte
    (app)/
      +layout.svelte                   # shell: sidebar/topbar, SSE store
      devices/+page.svelte
      devices/[id]/+page.svelte
      logs/power|activity|error/+page.svelte
      settings/+page.svelte
      users/+page.svelte                # akun web
      telegram-users/+page.svelte       # user Telegram (entitas terpisah)
      roles/+page.svelte, roles/[id]/+page.svelte   # editor izin (checkbox)
      bots/+page.svelte                # daftar/ganti/uji token bot
      backup/+page.svelte
      system/+page.svelte               # kesehatan, maintenance, audit
      +page.svelte                      # overview dashboard
  lib/
    api/client.ts                      # fetch wrapper, error normalisasi, 401/409
    stores/{auth,devices,settings,sse,permissions}.svelte.ts
    components/                        # shadcn-svelte + komponen domain
    schemas.ts                         # tipe dari OpenAPI (digenerate)
```

Komponen shadcn-svelte: `button`, `input`, `label`, `form`, `table`, `dialog`,
`alert-dialog`, `select`, `switch`, `checkbox`, `tabs`, `badge`, `card`, `sheet`, `sonner`,
`dropdown-menu`, `skeleton`, `separator`, `tooltip`, `chart` (layerchart) untuk tab daya.

## 8. Desain detail

### 8.1 Bootstrap `.env` (minimal, opsional)

| Variabel | Default | Bisa diubah dari UI? |
|---|---|---|
| `DATA_DIR` | `./data` | Tidak (butuh restart container) |
| `API_HOST` | `127.0.0.1` | Tidak |
| `API_PORT` | `8080` | Tidak |
| `TZ` | `Asia/Makassar` | Tidak |

Tidak ada variabel lain. Semuanya punya default sehingga `docker compose up` tanpa `.env`
tetap berjalan sampai wizard.

Secret sesi: bila `DATA_DIR/secret.key` belum ada, dibuat acak 32 byte saat start, permission
`0600`. File ini **tidak** ikut backup DB; restore di mesin lain membuat secret baru (semua
sesi lama otomatis tidak valid, yang diinginkan saat pindah mesin).

### 8.2 Skema database (v1)

Semua timestamp TEXT ISO lokal (`strftime('%Y-%m-%d %H:%M:%S','now','localtime')`).

| Tabel | Isi penting |
|---|---|
| `schema_migrations` | `version`, `name`, `checksum`, `applied_at` |
| `app_settings` | `key` PK, `value` JSON, `updated_at`, `updated_by` |
| `roles` | `id`, `slug` UNIQUE, `name`, `description`, `permissions` JSON (array kunci), `rate_limit_per_minute` NULL, `is_system` 0/1, `is_protected` 0/1, `created_at`, `updated_at` |
| `web_users` | `id`, `username` UNIQUE, `password_hash`, `role_id` FK, `is_active`, `created_by` FK NULL, `created_at`, `updated_at`, `last_login_at` |
| `web_sessions` | `token_hash` PK, `user_id` FK → `web_users`, `created_at`, `expires_at`, `ip`, `user_agent`, `revoked_at` |
| `telegram_users` | `telegram_id` PK (INTEGER), `label` NULL, `role_id` FK, `is_active`, `created_by_web_user_id` NULL, `created_by_telegram_id` NULL, `created_at`, `updated_at`, `last_seen_at` |
| `api_keys` | `id`, `name`, `key_hash`, `role_id` FK, `created_by`, `last_used_at`, `is_active` |
| `telegram_bots` | `id`, `label`, `token` (secret), `token_sha256` UNIQUE, `enabled` 0/1, `created_by`, `created_at`, `updated_at`, `last_ok_at`, `last_error`, `bot_username` |
| `devices` | `id`, `name` UNIQUE (slug), `label`, `tuya_id` UNIQUE, `local_key`, `ip`, `version` REAL, `type`, `dps` JSON, `features` JSON, `access_roles` JSON (array role_id; kosong = semua role berizin), `is_active`, `sort_order`, `created_at`, `updated_at`, `last_seen_at`, `last_error` |
| `device_settings` | `device_id` FK, `key`, `value` JSON, PK(`device_id`,`key`) |
| `device_activity_logs` | `id`, `device_id` FK, `user_id` NULL, `actor` (`ui`/`bot`/`api`/`system`), `bot_id` NULL, `action`, `status`, `message`, `created_at` |
| `device_power_logs` | `id`, `device_id` FK, `power_w`, `voltage_v`, `current_a`, `switch_state`, `source`, `created_at` |
| `app_error_logs` | `id`, `level`, `logger_name`, `message`, `exception_trace`, `file_name`, `line_number`, `created_at` |
| `backup_runs` | `id`, `filename`, `size_bytes`, `kind` (`auto`/`manual`/`pre_restore`), `created_at`, `note` |
| `audit_logs` | `id`, `at`, `actor_kind` (`web`/`telegram`/`api_key`/`system`), `actor_id` NULL, `actor_label`, `action`, `target_kind`, `target_id`, `result` (`ok`/`denied`/`error`), `ip`, `details` JSON, `request_id` |
| `app_state` | `key` PK, `value` JSON — status runtime persisten (`maintenance`, `restore_in_progress`, versi yang terakhir berhasil start) |

Catatan model:

- `roles.permissions` adalah array kunci izin dari katalog di kode (8.7). Menambah izin baru
  di kode tidak memerlukan migrasi; role lama otomatis tidak memilikinya sampai dicentang.
- `roles.is_protected` menandai role Superadmin: tidak bisa dihapus, `slug` tidak bisa
  diubah, dan izin intinya (`roles.manage`, `users.manage`, `system.view`) tidak bisa
  dicabut lewat API. Izin lain pada Superadmin boleh diubah superadmin sendiri.
- `devices.dps` menyimpan pemetaan semantik → indeks DP, mis.
  `{"switch":1,"power":19,"current":18,"voltage":20}`. Endpoint status dan power logging
  membaca peta ini; tidak ada kode yang menganggap DP daya selalu 1/18/19/20.
- `devices.features` mis. `{"power_logging":true,"watchdog":true}`.
- `devices.access_roles` kosong berarti "semua role yang punya izin `devices.view` /
  `devices.control`". Bila berisi, role di luar daftar tidak boleh melihat/mengontrol device
  itu (404 untuk view, 403 untuk kontrol — supaya keberadaan device tidak bocor).
- `device_settings` menampung knob per perangkat (threshold watchdog, role pemicu, interval
  logging opsional), dipisah dari `devices` agar fitur baru tidak menambah kolom.

Index: `(device_id, created_at)` di kedua tabel log, `created_at` pada `app_error_logs`,
`expires_at` pada `web_sessions`, `role_id` pada `web_users`, `role_id` pada `telegram_users`,
`(at)` dan `(actor_kind, actor_id, at)` pada `audit_logs`.

Dua tabel user, bukan satu: akun web tidak pernah dikenali bot, dan user Telegram tidak punya
password maupun sesi web. Yang dibagi hanyalah `roles`, sehingga satu role bisa dipakai
sekaligus oleh akun web dan user Telegram.

### 8.3 Migration runner

- File `migrations/NNNN_nama.sql`, dijalankan berurutan, satu transaksi per file.
- Runner mencatat `version`, `name`, `checksum` (sha256 isi file). Saat start:
  - DB kosong → terapkan semua;
  - `schema_migrations` ada → verifikasi checksum file yang sudah diterapkan, tidak cocok =
    **gagal start** (file migrasi lama tidak boleh diedit);
  - versi DB > versi aplikasi → gagal start.
- `0001_init.sql`: skema 8.2 + seed role (`superadmin` protected, `admin`, `operator`,
  `viewer`) + setting default. Seed role punya `is_system=1` sehingga bisa di-reset ke
  default dari UI, tapi tetap bisa diubah.

### 8.4 Katalog permission (tetap di kode)

Izin adalah kunci string; daftar berikut adalah katalog v1 dan satu-satunya sumber untuk UI
checkbox. Kategori membantu UI menyusun grup.

| Kategori | Kunci | Arti |
|---|---|---|
| Device | `devices.view` | lihat daftar/status/daya device yang `access_roles`-nya mengizinkan |
| | `devices.control` | nyalakan/matikan |
| | `devices.manage` | tambah/ubah/hapus device, atur DPS, `access_roles`, fitur |
| | `devices.scan` | scan LAN & test koneksi |
| Log | `logs.view` | lihat log aktivitas/daya/error |
| | `logs.cleanup` | jalankan pembersihan log manual |
| Settings | `settings.view` | lihat setting (secret tersamarkan) |
| | `settings.edit` | ubah setting operasional |
| Users web | `users.view` | lihat daftar akun web |
| | `users.manage` | buat/ubah/nonaktifkan akun web, atur role-nya |
| Users Telegram | `telegram_users.view` | lihat daftar user Telegram dan role-nya |
| | `telegram_users.manage` | daftarkan/ubah/nonaktifkan user Telegram, atur role-nya |
| Roles | `roles.manage` | buat/ubah/hapus role dan centang izinnya |
| Bot | `bots.view` | lihat daftar bot (token tersamarkan) |
| | `bots.manage` | tambah/ubah/hapus bot, aktif/nonaktif, uji token |
| Backup | `backup.view` | lihat daftar backup |
| | `backup.create` | buat backup manual |
| | `backup.restore` | unduh backup & akses jalur restore (digabung dengan `system.restore` untuk eksekusi) |
| API key | `apikeys.manage` | kelola API key skrip |
| Sistem | `system.view` | statistik sistem, kesehatan, versi skema |
| | `audit.view` | lihat audit log |
| | `system.maintenance` | aktifkan/nonaktifkan maintenance mode |
| | `system.restore` | jalankan restore DB (memaksa maintenance) |

Aturan evaluasi:

- `access/permissions.py` satu-satunya tempat aturan; route dan handler bot memanggilnya.
- Setiap route mendeklarasikan `require("devices.manage")` dsb. Tidak ada pengecekan ad-hoc.
- Hierarki kepemilikan: user hanya bisa memberi role yang izinnya **subset** dari izinnya
  sendiri (`users.manage` untuk akun web, `telegram_users.manage` untuk user Telegram), dan
  hanya bisa mengedit role yang izinnya subset dari izinnya sendiri (`roles.manage`). Ini
  mencegah eskalasi lewat role baru.
- **Aturan sasaran**: memodifikasi, menonaktifkan, menghapus, atau mengganti role sebuah
  akun/user Telegram hanya boleh bila role **saat ini** milik sasaran juga subset izin
  pemanggil (dan role baru, bila ada, juga subset). Tanpa aturan ini, pemegang `users.manage`
  bisa menonaktifkan Superadmin atau menurunkan role-nya.
- Izin `users.manage`, `telegram_users.manage`, dan `roles.manage` tidak bisa diberikan oleh
  pemilik izin yang tidak memilikinya; Superadmin protected menjamin selalu ada pemegang
  ketiganya.
- Akun web **tidak pernah** dibuat oleh bot: endpoint user Telegram menolak `username`,
  endpoint user web menolak `telegram_id`.
- Referensi role: penghapusan role ditolak bila masih dipakai `web_users`,
  `telegram_users`, `api_keys`, atau `devices.access_roles`. UI menyediakan "baca pemakai
  role" agar admin bisa memindahkan dulu.

### 8.5 Settings registry

Setiap setting: `key`, `type` (`string|int|float|bool|json|secret`), `default`, `category`,
`label` (ID), `help`, `min/max` atau `enum`, `apply` (`live` | `telegram_restart`),
`secret`, `edit_permission` (default `settings.edit`).

| Kategori | Kunci | Apply |
|---|---|---|
| `telegram` | `enabled` (master switch semua bot) | `telegram_restart` |
| `monitoring` | `power_interval_minutes`, `cache_ttl_seconds`, `error_ttl_seconds`, `warm_interval_seconds` | `live` |
| `housekeeping` | `interval_hours`, `log_retention_days`, `audit_retention_days` | `live` |
| `backup` | `interval_hours`, `retention_days`, `auto_enabled` | `live` |
| `tuya` | `call_timeout_seconds`, `threads`, `scan_timeout_seconds` | `live` |
| `security` | `session_ttl_hours`, `session_idle_minutes`, `cookie_secure`, `login_max_attempts`, `login_ip_max_attempts`, `login_window_seconds`, `rate_limit_window_seconds` | `live` |
| `maintenance` | `auto_off_minutes`, `telegram_behavior` (`stay_silent`/`stop_bots`) | `live` |
| `ui` | `title`, `theme`, `power_chart_default_range` | `live` |
| `system` (read-only) | `setup_complete`, `schema_version`, `data_dir` | — |

Catatan: **token bot bukan setting** — ia milik baris `telegram_bots`, dengan izin
`bots.manage`. Rate limit per role disimpan di `roles.rate_limit_per_minute` (NULL = pakai
default `security`).

Perilaku:

- Dibaca lewat `settings.get("monitoring.power_interval_minutes")` dari cache; cache
  di-invalidasi saat PATCH lalu event diterbitkan.
- `apply=live` → konsumen (scheduler, cache, rate limiter) memakai nilai terbaru pada siklus
  berikutnya. Scheduler menghitung ulang interval setelah event.
- `apply=telegram_restart` → `telegram.manager` me-rebuild semua Application aktif di dalam
  proses; API, scheduler, SSE tetap hidup.
- PATCH bulk atomik; satu nilai tidak valid membatalkan semuanya dan mengembalikan field error.
- `GET /api/settings` → `{key, value|"***", default, type, category, help, apply, editable}`.

### 8.6 Penyimpanan secret

Token bot, local key, dan hash password tersimpan di file SQLite. Batas keamanan: permission
file `0600`, volume Docker tidak dibaca publik, proses non-root. UI hanya menampilkan secret
tertutup dan mengizinkan penggantian (write-only), bukan pembacaan.

Pelengkap yang wajib:

- `DATA_DIR` dibuat dengan mode `0700`; file DB dibuat `0600`; backup `0600`. Entrypoint
  menolak start bila permission longgar dan tidak bisa diperbaiki (`chmod` gagal = fatal,
  bukan warning).
- Secret **tidak pernah** masuk log: logger filter menolak field `token`, `password`,
  `local_key`, `api_key`, `secret`, `cookie` (dicocokkan pada nama argumen maupun substring
  nilai yang dikenal, mis. token bot aktif).
- Secret **tidak pernah** dikirim ke FE, termasuk dalam bentuk tersamar parsial (tidak ada
  `sk-…abcd`). Respons hanya `{has_value: true, updated_at}`. Ganti nilai = kirim nilai baru
  penuh; tidak ada pembacaan.
- Header respons `Cache-Control: no-store` pada semua route `/api/*` supaya browser/proxy
  tidak menyimpan body yang memuat data device atau konfigurasi.
- Export JSON membuang secret sepenuhnya; file export diberi header peringatan dan nama file
  berstempel waktu.
- Backup berisi secret (karena berisi DB). Karena itu download backup dibatasi `backup.restore`
  dan setiap download diaudit (8.20).
- Enkripsi at-rest dengan kunci dari env sengaja tidak dipakai pada v1: kunci di env hanya
  memindahkan masalah tanpa melindungi dari penyerang yang sudah punya akses file. Bila nanti
  dibutuhkan, `settings/secrets.py` adalah satu-satunya tempat yang perlu diubah.

### 8.7 Autentikasi, sesi, role dinamis

- Login: `POST /api/auth/login {username, password}`. Password `hashlib.scrypt`
  (N=2^14, r=8, p=1, salt 16 byte) format `scrypt$n$r$p$salt_b64$hash_b64`;
  verifikasi `hmac.compare_digest`.
- Sesi: token acak 32 byte, DB menyimpan `sha256(token)`. Cookie
  `HttpOnly; SameSite=Lax; Path=/; Secure` sesuai `security.cookie_secure`. TTL dari setting.
  Detail rotasi, pencabutan, dan CSRF ada di 8.18.
- `GET /api/auth/me` → `{id, username, role:{id,slug,name}, permissions:[...], bot_permissions}`.
- `POST /api/auth/logout`, `GET /api/auth/sessions` (self; pemegang `users.manage` melihat
  semua), `DELETE /api/auth/sessions/{id}`.
- API key skrip: `X-API-Key`, hash di `api_keys`, `role_id` menentukan izinnya.
- Anti brute force: `security.login_max_attempts` per (`ip`,`username`) dalam window;
  melewati batas → `429` + `Retry-After`. Counter in-memory, dibersihkan job kecil.
- `security.cookie_secure=true` hanya bisa dipakai di HTTPS. UI menampilkan peringatan bila
  diaktifkan sementara dashboard diakses lewat `http://` (cookie tidak akan terkirim dan
  login tampak gagal).

Manajemen role:

- `GET /api/roles`, `POST /api/roles`, `PATCH /api/roles/{id}`, `DELETE /api/roles/{id}`,
  `GET /api/permissions` (katalog untuk checkbox).
- `DELETE` ditolak bila role masih dipakai (`web_users` atau `telegram_users`), role
  `is_protected`, atau menghabiskan pemegang `users.manage`/`roles.manage` terakhir.
- `PATCH` tidak boleh menambah izin yang tidak dimiliki pemanggil; tidak boleh mencabut dua
  izin inti dari role protected.

Manajemen user web:

- `POST /api/web-users` `{username, password, role_id}`; hanya `users.manage`; role yang
  diberikan harus subset izin pemanggil.
- `PATCH /api/web-users/{id}` (`password`, `role_id`, `is_active`), `DELETE /api/web-users/{id}`.
- Superadmin tidak bisa menonaktifkan/menghapus dirinya bila itu menghabiskan akun web aktif
  terakhir yang memegang `users.manage`.
- Password yang ada tidak pernah dikembalikan API; reset berarti menulis password baru.

Manajemen user Telegram:

- `POST /api/telegram-users` `{telegram_id, label?, role_id}`; hanya
  `telegram_users.manage`; role harus subset izin pemanggil.
- `PATCH /api/telegram-users/{telegram_id}` (`role_id`, `label`, `is_active`),
  `DELETE /api/telegram-users/{telegram_id}`.
- `telegram_id` yang tidak terdaftar = publik (hanya `/start`, `/help`), tanpa baris otomatis.
- Akun web tidak otomatis menjadi user Telegram, dan sebaliknya. Seorang manusia bisa punya
  dua entitas dengan role berbeda, mis. akun web Admin dan user Telegram Viewer.

### 8.8 Setup wizard

- `GET /api/setup/status` → `{required, steps_done}`, publik.
- `POST /api/setup` → `{username, password}`; membuat user dengan role `superadmin` (seed
  protected). Bisa sekali; setelah sukses `system.setup_complete=true`.
- Selama `setup_complete=false`: semua `/api/*` selain `setup`, `health`, `auth/me`
  mengembalikan `409 {detail:"setup_required"}`; UI diarahkan ke `/setup`.
- Wizard FE: buat akun Superadmin → (opsional) tambah bot token → (opsional) tambah
  perangkat manual atau scan → selesai.
- Setelah setup, bot hanya berjalan bila `telegram.enabled` dan ada bot enabled dengan token
  valid. API tetap jalan tanpa bot.

### 8.9 Registry perangkat

- `devices/registry.py` menyimpan snapshot device aktif dari DB, di-reload saat perubahan
  (CRUD, restore). `list_for_role(role_id)`, `get(name)`, `get_by_id(id)` menerapkan
  `access_roles`.
- `controller.py` membuat `tinytuya.Device` **lazy** saat pertama dipakai dan menyimpan
  instance + `threading.Lock` per device. Perubahan IP/key/version menutup dan membuang entry
  lama sehingga berlaku tanpa restart.
- I/O lewat `run_tuya(fn, ..., timeout=setting)` di executor (jumlah thread dari setting).
- `dps.py`: template DPS per tipe untuk prefill form dan `extract(device, raw_dps)` yang
  hanya mengembalikan kunci yang dipetakan.
- Endpoint dan command bot generik: `POST /api/devices/{id}/on|off`, `/on <nama>`.
  Tidak ada `air_on`/`lampu_on`.
- Watchdog: satu task per device dengan `features.watchdog=true`. Diarmkan saat kontrol "on"
  oleh user yang role-nya sama dengan `device_settings.watchdog.trigger_role_id` (default
  role `operator`) atau lebih rendah. Task membaca daya lewat state cache `force=True`,
  memakai sampel & ambang dari `device_settings`, mematikan device bila idle melewati
  `idle_watt` atau durasi melewati `max_minutes`. Status watchdog masuk SSE (banner + tombol
  batal di UI).
- Power logging: job scheduler menulis satu baris `device_power_logs` per device dengan
  `features.power_logging=true`, memakai pemetaan DPS-nya.
- Kontrol dari UI/bot selalu mengecek: izin `devices.control` **dan** `access_roles` device.

### 8.10 Scan LAN dan test koneksi

- `POST /api/devices/scan` menjalankan `tinytuya.deviceScan` di thread, dibatasi
  `tuya.scan_timeout_seconds`; hanya satu scan bersamaan (job in-memory per user).
  `GET /api/devices/scan/{job_id}` → status + kandidat `{ip, id, version, product_key}`.
  Kandidat tidak otomatis ditambahkan; UI memprefill form (kecuali `local_key`).
- `POST /api/devices/{id}/test` memanggil `status()` sekali dengan timeout pendek dan
  mengembalikan DPS mentah untuk memverifikasi pemetaan DP.

### 8.11 Log dan telemetri

- `GET /api/logs/activities|power|errors` dengan `limit`, `offset`, filter `device_id`,
  rentang `from`/`to`, pencarian teks. Semua query lewat `asyncdb`.
- `GET /api/stats` merangkum device online, log terakhir, ukuran DB, backup terakhir.
- SSE `GET /api/stream`: snapshot dari `state_cache` tiap N detik (setting), per device
  `{online, switch_on, power_w, voltage_v, current_a, watchdog, ages}`; tidak memicu I/O.
  Hanya device yang boleh dilihat role pemanggil.

### 8.12 Backup, restore, pindah DB

- Backup: `VACUUM INTO <DATA_DIR>/backups/tuyabot-YYYYMMDD-HHMMSS.db`, dicatat di
  `backup_runs`, retensi dari setting. Job scheduler `backup`, `initial_delay` 15 menit.
- Manual: `POST /api/backup` (`backup.create`), `GET /api/backup` (`backup.view`),
  `GET /api/backup/{id}/download` (`backup.restore` — berisi seluruh data & secret).
- Restore: `POST /api/backup/restore` (`system.restore` + `backup.restore`, wajib ulang
  password + konfirmasi teks). Urutan lengkap dan keadaan gagal ada di 8.19.
- Restore dijalankan sebagai operasi eksklusif: job scheduler dijeda, request tulis ditolak
  selama proses (maintenance mode), dan hanya satu restore dalam satu waktu. Di Linux
  (container) `os.replace` aman meski file masih dipakai; di Windows untuk pengembangan,
  semua koneksi ditutup lebih dulu sebelum `os.replace` (batasan dev, didokumentasikan).
- Pindah mesin: unduh backup → pasang di instance baru → login dengan kredensial DB itu.
  `secret.key` tidak ikut; sesi lama otomatis tidak berlaku.
- Export JSON (tanpa secret) untuk dokumentasi/audit, **bukan** jalur restore utama.

### 8.13 Bot Telegram dinamis

Model: **banyak bot sekaligus**, masing-masing `Application` polling sendiri.

- Tabel `telegram_bots`. UI `bots/+page.svelte`: daftar bot, label, username bot (diambil
  dari `getMe`), status (aktif/berhenti/error), tombol Aktifkan/Nonaktifkan, Uji, Ganti token,
  Hapus.
- `POST /api/bots` `{label, token}` → validasi token via `getMe`, simpan, `enabled=false`
  sampai diaktifkan. `PATCH /api/bots/{id}` (token/label/enabled), `POST /api/bots/{id}/test`
  (getMe), `DELETE /api/bots/{id}`.
- **Satu token hanya boleh ada di satu baris** (`token_sha256` UNIQUE). Dua baris dengan token
  sama akan saling menendang `getUpdates`; penolakan dilakukan saat create/patch, bukan
  dibiarkan menjadi error runtime.
- `telegram/manager.py` memegang `dict[bot_id, Application]`, dengan `asyncio.Lock` global:
  - saat start, bangun Application untuk semua bot `enabled=1` bila `telegram.enabled`;
  - `POST /api/bots/{id}/enable|disable` memulai/menghentikan Application itu saja;
  - `PATCH` token memicu stop → bangun ulang → start untuk bot tersebut;
  - kegagalan satu bot (token salah, bentrok polling) dicatat di `last_error` dan **tidak**
    menjatuhkan bot lain atau API.
- Constraint PTB 22.x yang harus dipatuhi manager: `Application.builder()...build()` harus
  dipanggil **di dalam event loop yang sedang berjalan** (PTB mengikat loop saat build), jadi
  tidak boleh dibangun saat modul di-import atau di thread lain. Lifecycle manual
  (`initialize()` → `start()` → `updater.start_polling()`), dan shutdown sebaliknya
  (`updater.stop()` → `stop()` → `shutdown()`), masing-masing dibungkus `try/except` per bot.
- Rebuild dijalankan sebagai task pada loop utama dengan status `starting/stopping` yang
  dikembalikan ke UI, sehingga request PATCH tidak menunggu proses jaringan panjang.
- Konflik `Conflict: terminated by other getUpdates request` muncul bila token yang sama
  aktif di dua tempat (mis. salinan lama masih jalan). Pesan `last_error` diterjemahkan ke
  petunjuk ini; tidak ada retry agresif.
- Command v1: `/start`, `/help`, `/whoami`, `/status`, `/devices`, `/on <nama>`,
  `/off <nama>`, `/users`, `/adduser <telegram_id> <role-slug-or-name>`, `/removeuser`,
  `/logs`. Izin per command mengikuti permission role baris `telegram_users` pemanggil.
  `/adduser` dan `/removeuser` butuh `telegram_users.manage`; role yang diberikan harus
  subset izin pemberi.
- Identitas Telegram → `telegram_users.telegram_id`. User tanpa baris = publik (hanya
  `/start`, `/help`). Akun web tidak dipakai di jalur ini sama sekali.
- Setiap kontrol menulis `device_activity_logs` dengan `actor='bot'` dan `bot_id`; UI menulis
  `actor='ui'`; scheduler/API menulis `actor='system'`/`api`.
- Rate limit per user Telegram memakai `roles.rate_limit_per_minute` (NULL → default).

### 8.14 Scheduler

Satu `Scheduler` dengan job:

| Job | Interval | Isi |
|---|---|---|
| `cache-warm` | `monitoring.warm_interval_seconds` | baca status semua device aktif |
| `power-snapshot` | `monitoring.power_interval_minutes` | tulis `device_power_logs` |
| `housekeeping` | `housekeeping.interval_hours` | hapus log > retensi (termasuk audit sesuai `audit_retention_days`) |
| `backup` | `backup.interval_hours` | backup otomatis |
| `session-sweep` | 1 jam | hapus sesi kedaluwarsa + counter login |

Interval dihitung ulang saat settings berubah. Job opsional ditambah/dihapus mengikuti
kategori (`backup.auto_enabled`).

### 8.15 API (ringkas)

| Method | Path | Izin |
|---|---|---|
| GET | `/healthz` | publik |
| GET/POST | `/api/setup/status`, `/api/setup` | publik (sekali) |
| GET | `/api/auth/csrf` | publik (rate-limited) |
| POST | `/api/auth/login`, `/api/auth/logout` | publik / sesi |
| GET | `/api/auth/me` | sesi |
| POST | `/api/auth/password` | sesi |
| GET/DELETE | `/api/auth/sessions[/{id}]` | sesi (self; `users.manage` untuk semua) |
| GET | `/api/permissions` | sesi |
| GET/POST | `/api/roles` | `users.view` / `roles.manage` |
| PATCH/DELETE | `/api/roles/{id}` | `roles.manage` |
| GET/POST | `/api/web-users` | `users.view` / `users.manage` |
| PATCH/DELETE | `/api/web-users/{id}` | `users.manage` |
| GET/POST | `/api/telegram-users` | `telegram_users.view` / `telegram_users.manage` |
| PATCH/DELETE | `/api/telegram-users/{telegram_id}` | `telegram_users.manage` |
| GET/POST | `/api/bots` | `bots.view` / `bots.manage` |
| PATCH/DELETE | `/api/bots/{id}` | `bots.manage` |
| POST | `/api/bots/{id}/enable|disable|test` | `bots.manage` |
| GET/POST | `/api/devices` | `devices.view` (filtrasi `access_roles`) / `devices.manage` |
| PATCH/DELETE | `/api/devices/{id}` | `devices.manage` |
| POST | `/api/devices/{id}/on|off` | `devices.control` + `access_roles` |
| GET | `/api/devices/{id}/status|power` | `devices.view` + `access_roles` |
| POST | `/api/devices/scan`, `/api/devices/{id}/test` | `devices.scan` |
| GET/PATCH | `/api/settings` | `settings.view` / `settings.edit` |
| GET | `/api/settings/schema` | `settings.view` |
| GET | `/api/logs/{activities,power,errors}` | `logs.view` |
| GET/POST | `/api/backup` | `backup.view` / `backup.create` |
| POST | `/api/backup/restore`, download | `system.restore` + re-auth + CSRF |
| GET/DELETE | `/api/api-keys` | `apikeys.manage` |
| GET | `/api/stats` | `system.view` |
| GET | `/api/audit` | `audit.view` |
| GET/POST | `/api/maintenance` | `system.maintenance` |
| GET | `/api/stream` | sesi (`devices.view` + `access_roles`) |
| GET | `/api/health` | sesi |

FE membangkitkan `schemas.ts` dari `/openapi.json` saat dev/CI; OpenAPI dinonaktifkan di
produksi.

### 8.16 Frontend

- SvelteKit + Svelte 5 runes, Tailwind, shadcn-svelte, adapter-static (SPA fallback).
- Guard klien di `+layout.ts`: `/api/auth/me`; `401` → `/login`; `409 setup_required` →
  `/setup`; `503 maintenance` → layar maintenance dengan retry.
- CSRF: `lib/api/client.ts` membaca cookie `csrf_token` non-HttpOnly dan mengirim
  `X-CSRF-Token` pada setiap POST/PATCH/DELETE. Mutasi ditolak tanpa header ini, sehingga bug
  FE langsung terlihat di dev, bukan di produksi.
- Izin dikirim server di `/me`; UI menyembunyikan menu/aksi yang tidak diizinkan, tetapi
  server tetap memeriksa (UI bukan pagar keamanan).
- SSE singleton di store; reconnect dengan backoff; indikator "terputus" di topbar.
- Halaman role: daftar role + editor izin berupa checkbox bergrup per kategori dengan
  Select all per grup; menampilkan jumlah pemakai role (akun web + user Telegram terpisah);
  role protected diberi badge dan checkbox izin inti dinonaktifkan.
- Dua halaman user terpisah: `users/+page.svelte` (akun web: username, role, status login,
  reset password, nonaktifkan) dan `telegram-users/+page.svelte` (telegram_id, label, role,
  nonaktifkan). Tidak ada form yang mencampur keduanya.
- Halaman bot: kartu per bot dengan status, `@username`, last error; dialog "Ganti token"
  (write-only), switch Aktif/Nonaktif, tombol Uji.
- Form settings dibangkitkan dari `/api/settings/schema`, badge `live` / "restart bot".
- Device: kartu + tabel, form DPS dengan prefill per tipe, pilihan role yang boleh akses,
  dialog konfirmasi untuk device dengan watchdog.
- Backup: daftar, buat, unduh, restore dengan konfirmasi ganda.
- System: kartu kesehatan, versi skema, toggle maintenance (dengan `auto_off_minutes`),
  tabel audit dengan filter dan drawer detail. Halaman audit hanya muncul untuk pemegang
  `audit.view`.
- Aksesibilitas: fokus terlihat, `aria-live`, target >= 44px, layout sampai 360px,
  `prefers-reduced-motion`.

### 8.17 SQLite: konkurensi dan lifecycle koneksi

SQLite dipakai oleh satu proses dengan beberapa jenis pemakai: event loop (API, SSE),
executor Tuya (I/O perangkat), executor DB (`asyncdb`), scheduler, dan bot Telegram. All
writes go through `asyncdb`.

**Mode dan pragma** (dipasang pada setiap koneksi baru):

```sql
PRAGMA journal_mode=WAL;        -- pembaca tidak memblokir penulis
PRAGMA synchronous=NORMAL;      -- aman bersama WAL
PRAGMA busy_timeout=5000;       -- dari SQLITE_BUSY_TIMEOUT_MS
PRAGMA foreign_keys=ON;
PRAGMA wal_autocheckpoint=1000;
```

**Lifecycle koneksi** — `storage/db.py`:

- Satu koneksi per thread via `threading.local()`. Tidak ada `check_same_thread=False`, tidak
  ada pool manual. Alasan: `asyncio.to_thread` memakai thread yang tidak dapat diprediksi,
  dan SQLite tidak boleh berbagi satu `Connection` antar thread.
- `connection()` adalah context manager yang membuka koneksi lazy pada pemakaian pertama
  thread itu, menjalankan pragma, dan **tidak** menutupnya di akhir blok (hanya commit /
  rollback). Koneksi thread ditutup saat shutdown (`close_all()`), dan saat generation
  berubah.
- **Generation counter**: `db.generation` naik setiap kali file DB ditukar (restore).
  Setiap akses membandingkan angka yang tersimpan di `threading.local` dengan global; bila
  berbeda, koneksi thread itu ditutup lalu dibuka ulang. Ini juga menangani kasus WAL/SHM
  yang tertinggal dari file lama.
- Setelah restore, file `-wal` dan `-shm` lama **dihapus** sebelum koneksi baru dibuka;
  file DB baru sudah konsisten karena berasal dari `VACUUM INTO`.
- `close_all()` dipanggil pada shutdown dan sebelum restore di Windows (lihat 8.21).

**Aturan konkurensi yang ditegakkan di kode**:

- Semua requirement `async def` yang menyentuh DB memakai `run_db()` (executor DB, 4 thread,
  timeout 15 detik). Tidak ada `sqlite3` di jalur event loop. Ini aturan lint yang diuji
  (`tests/test_no_sync_db_in_routes.py` memeriksa AST route module).
- Transaksi tulis pendek: `BEGIN IMMEDIATE` untuk jalur baca-lalu-tulis (mis. pembuatan sesi,
  increment counter login, penomoran audit) agar tidak ada *lost update*; transaksi tidak
  pernah menunggu I/O jaringan di dalamnya.
- Satu operasi restore/backup adalah operasi eksklusif (`app_state.restore_in_progress`),
  hanya satu berjalan; selama itu semua request tulis dari API ditolak (8.21).
- Batch insert log (power snapshot per device) dikirim dalam satu transaksi; tidak ada
  autocommit per baris.
- `VACUUM`/`VACUUM INTO` dan housekeeping DELETE dijalankan di executor DB, tidak di loop.
- Batas ukuran hasil query (`limit` maksimal 200, pagination wajib untuk audit dan log) supaya
  satu request tidak menarik seluruh tabel.

**Perilaku saat `database is locked`**: di-retry maksimal 3 kali dengan backoff pendek
(50/150/400 ms) hanya untuk operasi tulis idempoten; selain itu dikembalikan sebagai `503`
dengan pesan yang bisa ditindaklanjuti. Kegagalan dibedakan dari error logika — tidak
ditangkap oleh `except Exception` yang menelan (kesalahan yang dulu membuat housekeeping diam
selama berbulan-bulan).

### 8.18 Sesi, rotasi, dan CSRF

**Token dan penyimpanan**

- Token sesi 32 byte dari `secrets.token_urlsafe(32)`. DB menyimpan `sha256(token)` saja
  (dengan pepper dari `secret.key`), jadi bocornya file DB tidak langsung memberi sesi aktif.
- Sesi membawa `user_id`, `created_at`, `expires_at`, `last_seen_at`, `ip`, `user_agent`,
  `revoked_at`. Idle timeout opsional (`security.session_idle_minutes`, default 60) di samping
  TTL absolut (`session_ttl_hours`, default 12). `last_seen_at` ditulis paling sering sekali
  per menit per sesi agar tidak menjadi beban tulis.
- Cookie: `HttpOnly`, `SameSite=Lax`, `Path=/`, `Secure` mengikuti setting, tanpa `Domain`.
  Nama cookie diberi prefix `__Host-` bila `cookie_secure=true` (memaksa Path=/ dan tanpa
  Domain), dan nama biasa bila diakses lewat HTTP lokal.

**CSRF**

- Karena cookie dikirim otomatis, semua mutasi (POST/PATCH/DELETE) dari sesi web wajib
  membawa token CSRF. Pola **double-submit cookie + header**:
  - `GET /api/auth/me` (dan `POST /api/auth/login`) menetapkan cookie `csrf_token` yang
    **tidak** `HttpOnly`, berisi nilai acak 32 byte, terikat ke sesi lewat HMAC
    (`hmac(secret, session_token_hash)`).
  - FE membaca cookie itu dan mengirimnya sebagai header `X-CSRF-Token` pada setiap mutasi.
  - Server memverifikasi header == cookie == HMAC untuk sesi tersebut. Cookie saja atau
    header saja ditolak.
- `SameSite=Lax` mencegah cookie ikut pada POST lintas-situs, sehingga CSPHT (cross-site)
  tidak bisa memuat cookie; CSRF-token tetap diwajibkan karena Lax masih mengizinkan
  navigasi GET dan tidak melindungi semua browser/proxy edge.
- `Origin`/`Referer` diperiksa untuk mutasi: bila header ada dan origin tidak cocok dengan
  host request, tolak `403`. Ini lapisan kedua, bukan satu-satunya.
- Login dan setup memakai `X-CSRF-Token` yang diterbitkan `GET /api/auth/csrf` (publik,
  rate-limited) karena belum ada sesi saat itu. Cookie csrf tetap `SameSite=Lax`.
- Autentikasi API key (`X-API-Key`) **tidak** memakai cookie, jadi tidak memerlukan CSRF,
  tetapi tetap diperiksa Origin agar tidak dapat dipakai sebagai pembawa cookie pada
  cross-site request.

**Rotasi dan pencabutan**

- Login baru: sesi lama untuk user tersebut **tidak** otomatis dicabut, tetapi UI menampilkan
  daftar sesi aktif dan tombol cabut. "Cabut semua sesi lain" tersedia saat ganti password.
- Ganti password → semua sesi user itu dicabut kecuali sesi yang melakukan perubahan, dan
  token CSRF lama otomatis tidak valid.
- Menonaktifkan user, mengganti role user, mengganti `secret.key`, atau restore DB →
  seluruh sesi terkait dicabut. `secret.key` baru berlaku pada start berikutnya.
- Logout mencabut sesi aktif (set `revoked_at`), menghapus cookie, dan tetap idempoten.
- Sesi kedaluwarsa dihapus oleh job `session-sweep`.

**Lain-lain**

- Header keamanan statis dari backend: `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: same-origin`, `X-Frame-Options: DENY`, dan CSP untuk respons API
  (`default-src 'none'`). CSP halaman HTML dilayani nginx (FE).
- Endpoint login dibatasi per (`ip`, `username`) dan per IP secara global
  (`security.login_max_attempts`, `security.login_ip_max_attempts`).
- Setelah 5 kegagalan berturut-turut untuk username yang sama, respons tetap identik
  ("kredensial salah") tanpa membocorkan apakah username ada, tetapi waktu respons ditambah
  delay kecil konstan untuk memperlambat enumerasi.

### 8.19 Maintenance mode

Maintenance adalah keadaan aplikasi, bukan setting biasa, dan bertahan melewati restart
(`app_state.maintenance`).

**Saat maintenance aktif:**

- `/healthz` tetap `200 {"status":"ok","maintenance":true}` — container tidak dianggap mati.
- `/api/health` melaporkan `maintenance`.
- Semua route selain `/api/auth/*`, `/api/maintenance/status`, `/healthz` mengembalikan
  `503 {detail:"maintenance", retry_after, message}` dengan header `Retry-After`.
- SSE ditutup dengan event `maintenance` lalu stream berakhir; FE menampilkan layar
  maintenance dan mencoba ulang berkala.
- Bot Telegram: mode `telegram.maintenance_behavior` — `stay_silent` (default; command
  dijawab "sedang maintenance"), atau `stop_bots`. Bot tetap terhubung pada default supaya
  tidak perlu menunggu `getUpdates` timeouts.
- Scheduler melompati job kecuali `session-sweep`. Watchdog **dibatalkan** dan tidak
  mengarmkan diri baru (mematikan pompa otomatis saat maintenance bukan tindakan yang
  diinginkan). Status watchdog yang sedang berjalan dilaporkan di UI agar tidak mengejutkan.
- Siapa pun dengan `system.maintenance` tetap bisa login dan keluar dari maintenance.

**Alasan dan pemakaian**

- Restore DB memaksa maintenance (tidak bisa diaktifkan/dinonaktifkan manual selama restore).
- Operator bisa mengaktifkan maintenance untuk pemeliharaan singkat; opsional auto-off
  setelah N menit (`maintenance.auto_off_minutes`, default 60) supaya tidak lupa.

**Restore lifecycle (eksklusif):**

1. `POST /api/backup/restore` dengan `system.restore` + `backup.restore` + re-auth password +
   token CSRF.
2. Server set `app_state.restore_in_progress=true`, aktifkan maintenance, tunggu request
   yang sedang berjalan selesai (grace 2 detik), jeda scheduler.
3. Unggah/salin file ke `DATA_DIR/restore/tmp.db`; jalankan `PRAGMA integrity_check` dan
   verifikasi skema; migrasi bila versi lebih lama; tolak bila lebih baru.
4. Buat backup `kind=pre_restore` dari DB saat ini.
5. Tutup semua koneksi (`close_all()`), hapus `-wal`/`-shm`, `os.replace` file.
6. Buka koneksi baru, naikkan generation, reset cache settings/role/registry, rebuild manager
   bot.
7. Tulis audit (`backup.restore`, result, detail versi), set `restore_in_progress=false`,
   dan kembalikan ke keadaan maintenance-manual atau normal.
8. Jika langkah 3–6 gagal di titik mana pun, DB lama tetap utuh (dibuat/dekati backup
   `pre_restore`), maintenance tetap aktif, dan error dilaporkan di UI dengan tombol
   "coba lagi / keluar dari maintenance".

### 8.20 Audit log

Audit menjawab "siapa melakukan apa, kapan, dari mana, hasilnya apa" untuk tindakan yang
mengubah keadaan. Ia terpisah dari `device_activity_logs` (operasi perangkat sehari-hari)
dan `app_error_logs` (kesalahan aplikasi).

**Yang dicatat** (minimal):

- auth: login berhasil/gagal, logout, pencabutan sesi, ganti password, reset password user
  lain.
- user & role: create/patch/delete akun web, user Telegram, role, perubahan izin
  (diff lama→baru di `details`).
- bot: create/patch (token **tidak** dicatat, hanya `changed:true`), enable/disable, test,
  delete.
- device: create/patch/delete, perubahan `access_roles`/DPS, kontrol manual dari UI
  (`device.control` dengan target), scan.
- settings: patch (key, lama→baru; secret hanya `changed:true`).
- backup: create, download, restore (dengan hasil dan versi skema).
- api key: create/delete/rotate.
- maintenance: aktif/nonaktif (termasuk auto-off) dan alasan bila diisi.
- akses ditolak: setiap `403` pada mutasi dicatat `result=denied` — ini yang membuat
  percobaan eskalasi izin terlihat.

**Bentuk dan penulisan**

- Ditulis di dalam transaksi yang sama dengan perubahan (bila perubahan gagal, audit tidak
  ada), kecuali untuk `denied` yang ditulis setelahnya dan tidak boleh menggagalkan request.
- `details` adalah JSON; tidak pernah memuat secret, password, token, atau local key.
- `request_id` (dari middleware) dikembalikan sebagai header `X-Request-Id` dan muncul di
  log aplikasi, sehingga laporan UI bisa ditelusuri ke error log.
- Penulisan memakai `run_db`; kegagalan menulis audit **tidak** menggagalkan operasi bisnis
  tetapi dicatat `app_error_logs` level ERROR (karena audit yang hilang harus terlihat).
- Retensi terpisah: `housekeeping.audit_retention_days` (default 180), dengan opsi ekspor CSV
  sebelum dihapus.

**Akses**

- `GET /api/audit` dengan `audit.view`; filter `actor`, `action`, `target`, `result`,
  rentang waktu, `request_id`; pagination wajib; tidak ada endpoint hapus (hanya retensi).
- UI `system/audit` menampilkan tabel + drawer detail JSON, dengan tautan ke entitas target.

### 8.21 Deploy

- Backend: multi-stage image, non-root, `read_only: true`, `tmpfs: /tmp`, `cap_drop: ALL`
  + `no-new-privileges`, volume `data/`, `logs/`, `backup/`, `HEALTHCHECK` → `/healthz`.
- Frontend: `nginx:alpine` berisi hasil build; nginx memproxy `/api` → `http://backend:8080`,
  fallback SPA ke `index.html`.
- `docker-compose.yml` menyatukan keduanya; hanya frontend yang publish port.

## 9. Testing

Backend (`pytest`):

- migrasi: DB kosong → v1; checksum berubah → gagal; versi DB lebih baru → gagal.
- settings: default, validasi, bulk atomik, masking secret, event apply.
- permission/role: evaluasi katalog, subset-rule (tidak bisa memberi izin lebih tinggi),
  role protected tidak bisa dihapus, tidak bisa mencabut izin inti, akun web terakhir pemegang
  `users.manage` tidak bisa dinonaktifkan.
- pemisahan user: akun web tidak dikenali bot (tidak ada lookup user Telegram ke
  `web_users`), user Telegram tidak bisa login web (tidak ada baris `web_users`), dan endpoint
  web/Telegram saling menolak field milik entitas lain.
- auth: hash/verify, sesi kedaluwarsa/dicabut, login limit, tiap route menolak tanpa izin.
- CSRF: mutasi tanpa `X-CSRF-Token` ditolak; header/cookie tidak cocok ditolak; token dari
  sesi lain ditolak; `Origin` silang ditolak; mutasi dengan API key tidak butuh CSRF.
- konkurensi SQLite: dua thread menulis paralel tidak saling menghilangkan baris; `BEGIN
  IMMEDIATE` pada counter login; generation bump setelah restore membuka ulang koneksi;
  artefak `-wal`/`-shm` dibersihkan; retry `database is locked` berhenti setelah 3 percobaan.
- audit: setiap mutasi sensitif menghasilkan baris dengan actor/result yang benar; `403`
  menghasilkan `result=denied`; secret tidak pernah muncul di `details`; kegagalan menulis
  audit muncul di `app_error_logs`.
- maintenance: semua route non-auth mengembalikan 503; watchdog tidak mengarmkan diri;
  scheduler melewati job; keluar dari maintenance mengembalikan layanan; auto-off berjalan.
- setup: gating 409, sekali pakai, membuat role superadmin + akun web pertama (tidak membuat
  user Telegram apa pun).
- device: registry reload, filter `access_roles` (404 untuk view), pemetaan DPS generik,
  kontrol dengan controller palsu, timeout, device offline tidak menjatuhkan API.
- watchdog: idle mematikan, durasi maksimum mematikan, normal tidak, cancel.
- bot dinamis: dua bot aktif bersamaan, disable satu tidak memengaruhi yang lain, token
  invalid dicatat tanpa menjatuhkan API, ganti token me-rebuild hanya bot itu,
  konflik getUpdates diterjemahkan ke pesan.
- backup/restore: roundtrip, integrity check, tolak versi lebih baru, generation bump,
  semua tabel sama setelah restore, restore gagal di tengah tidak merusak DB lama.
- stream: snapshot tanpa I/O, payload sesuai kontrak, filtrasi per izin.

Frontend: vitest untuk `api/client` (401/403/409), store SSE (reconnect, stale), guard rute;
Playwright smoke: setup → buat role "Tamu" dengan hanya `devices.view` → buat akun web "tamu"
→ login sebagai akun itu (tidak ada tombol kontrol) → login superadmin → daftarkan user
Telegram dengan role Operator → tambah bot → tambah device → toggle → lihat log → backup.

Guard regresi: tidak ada secret bocor di `GET /settings`/`GET /bots`, tidak ada endpoint di
luar daftar 8.15, tidak ada kredensial di `localStorage`, tidak ada `sqlite3` sinkron di
modul route (AST check), tidak ada kode yang menyebut "air" atau "lampu" secara khusus.

## 10. Milestone

| # | Isi | Kriteria selesai |
|---|---|---|
| 1 | Skeleton, bootstrap, DB + migrasi, koneksi & pragma, settings service, permission catalog | `/healthz` 200, settings API jalan, migration & concurrency test hijau |
| 2 | Setup wizard, auth + CSRF + sesi, role dinamis, akun web, user Telegram, API keys, audit log | role baru dengan izin centang dari API langsung berlaku; role protected terkunci; CSRF & pemisahan entitas teruji |
| 3 | Device registry generik, controller, scan/test, kontrol, status, power log, SSE | device baru dari API bisa dikontrol tanpa restart; akses per-role teruji |
| 4 | Bot dinamis (banyak bot), watchdog per device | dua bot aktif, ganti token dari UI tanpa restart container; user Telegram baru dikenali tanpa restart |
| 5 | Backup/restore + maintenance mode + scheduler + stats | restore roundtrip teruji; maintenance menutup mutasi; interval mengikuti settings |
| 6 | Frontend lengkap (roles, bots, devices, logs, settings, backup, system) | semua halaman 8.16; Playwright smoke hijau |
| 7 | Docker, compose, CI, dokumentasi | `docker compose up` dari nol → wizard; CI ruff+pytest+build FE |

## 11. Yang diserahkan ke builder

- Nama file/tema kecil, penamaan komponen FE, library form tambahan.
- Detail tampilan (layout akhir, warna, ikon) — mengikuti arahan visual saat implementasi.
- Cara CI men-generate `schemas.ts` — bebas, asal deterministik.
- Isi help text setting dan label permission.
- Slug role seed yang tepat (`operator`, `viewer`, dst.) selama katalog izinnya sesuai.

## 12. Risiko dan mitigasi

| Risiko | Mitigasi |
|---|---|
| Satu proses menanggung semua beban | executor terpisah Tuya/DB, timeout, cache single-flight |
| Beberapa bot menambah beban polling | hanya bot `enabled` yang jalan; tiap bot ringan karena handler membaca cache; nonaktifkan bot uji setelah selesai |
| Eskalasi izin lewat role baru | subset-rule di `permissions.py`, role protected tidak bisa dicabut izin intinya |
| Operator bingung karena punya dua identitas (web & Telegram) dengan role berbeda | UI menampilkan role per entitas dengan jelas; tidak ada tautan otomatis; dokumentasi menekankan dua tabel terpisah |
| Bot dinamis: builder PTB terikat loop | manager hanya membangun Application di loop utama; test memakai fake Application, bukan token nyata |
| Restore DB di tengah trafik | generation counter + `os.replace` atomik, maintenance mode eksklusif, rebuild manager |
| `database is locked` pada beban tinggi | WAL, timeout 5000 ms, `BEGIN IMMEDIATE` untuk baca-lalu-tulis, retry terbatas, tulis lewat executor DB |
| Sesi dicuri lewat XSS | HttpOnly + hash di DB + CSRF ganda + CSP + rotasi saat ganti password/role |
| Restore setengah jadi | urutan eksklusif + `pre_restore` + verifikasi integritas sebelum tukar file |
| Ganti token bot saat polling | stop → build → start di bawah lock, hanya bot terkait |
| Device offline memperlambat request | cache error TTL pendek, timeout, status "degraded" bukan 500 |
| Secret di DB | permission file, non-root, write-only API, tidak ikut build FE |
