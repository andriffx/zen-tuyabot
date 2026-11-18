# Deploy dengan Docker

Dua container, satu port publik:

```
internet ──► nginx operator (TLS, domain asli)
                 │  proxy_pass http://127.0.0.1:8081
                 ▼
            ┌────────────┐        ┌─────────────┐
            │  web       │  /api  │  backend    │
            │ nginx + SPA├───────►│  FastAPI    │
            │ :80        │        │  :8080      │
            └────────────┘        └─────────────┘
              publish 127.0.0.1:8081        internal saja
```

Hanya `web` yang mem-publish port, dan hanya ke loopback host. Port backend tidak
pernah terbuka ke jaringan.

## Prasyarat

- Docker Engine + plugin Compose (`docker compose version`).
- Node **tidak** perlu ada di server: frontend di-build di dalam image.

## Menjalankan

Dari **root repo** (bukan `backend/` — Dockerfile frontend butuh lockfile di root):

```bash
docker compose up -d --build
docker compose ps            # tunggu kolom STATUS menjadi healthy (~20 detik)
docker compose logs -f backend
```

Cek tanpa nginx dulu:

```bash
curl -s http://127.0.0.1:8081/healthz
curl -s http://127.0.0.1:8081/api/setup/status
```

Lalu buka `http://127.0.0.1:8081/setup` untuk membuat akun Superadmin pertama.

## Nginx operator

Tambahkan di server block yang sudah ada (TLS tetap di sini):

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8081;
    proxy_http_version 1.1;

    # WAJIB: $http_host mempertahankan port; $host membuangnya, dan backend
    # membandingkan Origin (memuat port) dengan Host sehingga semua POST 403.
    proxy_set_header Host $http_host;

    proxy_set_header X-Real-IP        $remote_addr;
    proxy_set_header X-Forwarded-For  $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    proxy_buffering off;      # SSE /api/stream
    proxy_read_timeout 1h;
}

location / {
    proxy_pass http://127.0.0.1:8081;
    proxy_set_header Host $http_host;
}
```

## Data dan volume

Semua yang persisten ada di `./backend/data` di host:

| Isi | Keterangan |
|---|---|
| `tuyabot.db` (+ `-wal`, `-shm`) | database |
| `secret.key` | pepper sesi; **jangan** dihapus, semua sesi jadi tidak valid |
| `backups/` | cadangan dari UI |
| `logs/` | log internal aplikasi |

`./logs` dan `./backup` **tidak** di-mount terpisah. Aplikasi menulis log dan
backup ke dalam `DATA_DIR`, jadi mount terpisah hanya menghasilkan folder kosong
yang menyesatkan.

Backup database dari UI sudah cukup untuk migrasi; `secret.key` ikut disalin bila
kamu memindahkan seluruh `data/`.

## Setelah dashboard hidup di HTTPS

Satu langkah manual, karena aplikasi tidak bisa membedakan http dari https di
balik proxy:

> Settings → Keamanan → **Cookie hanya lewat HTTPS** → aktifkan.

Tanpa ini cookie sesi masih terkirim lewat http (dianggap tidak aman). Dengan
HTTPS aktif, ini wajib agar tidak ada celah downgrade.

## Yang perlu diketahui

**Scan perangkat tidak berfungsi.** Container memakai bridge network, sedangkan
scan Tuya mem-broadcast UDP ke LAN. Tambahkan perangkat secara manual: form
"Tambah device" punya kolom IP, local key, dan Tuya ID.

**IP di audit log** berasal dari `X-Forwarded-For` yang diteruskan nginx. Backend
mempercayai `172.16.0.0/12` (jaringan Docker) dan `127.0.0.1`. Kalau nginx
operator berada di mesin lain, tambahkan alamatnya ke `FORWARDED_ALLOW_IPS` di
`docker-compose.yml`, jika tidak, audit akan mencatat IP proxy dan pembatasan
percobaan login menjadi satu kuota untuk semua orang.

**Frontend di-build saat `docker compose build`.** Setelah mengubah kode
frontend, jalankan ulang `docker compose up -d --build`. Cache layer `npm ci`
tetap dipakai selama `package-lock.json` tidak berubah.

## Perintah harian

```bash
docker compose logs -f backend        # log aplikasi + bot
docker compose restart backend        # setelah mengubah .env
docker compose down                   # berhenti (data tetap)
docker compose up -d --build          # rebuild setelah update kode
```

## Batasan yang belum teruji

Image ini belum pernah dijalankan dengan Docker sungguhan saat ditulis — Docker
tidak tersedia di mesin pengembangan. Yang sudah diuji langsung: `/healthz`
menjawab tanpa header, POST lewat proxy dengan `Host $http_host` berhasil (200),
dan dengan `$host` gagal 403 seperti yang didokumentasikan. Lapisan container
(ownership volume, read-only filesystem, healthcheck) perlu diverifikasi pada
percobaan pertama di server.
