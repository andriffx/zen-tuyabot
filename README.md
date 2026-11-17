# Monorepo: Zen Tuyabot

Dua aplikasi dalam satu repo:

| Folder | Isi | Stack |
|---|---|---|
| [`backend/`](backend/README.md) | Bot Telegram + REST API + SQLite | Python 3.11, FastAPI, python-telegram-bot, tinytuya |
| `frontend/` | Dashboard web (static SPA) | SvelteKit, Tailwind, shadcn-svelte |

## Arsitektur

```
Browser ──> nginx operator (TLS, SPA) ──/api──> backend (FastAPI) ──> SQLite
                                                      ├─> Telegram bots
                                                      ├─> Scheduler
                                                      └─> Tuya devices (LAN)
```

Frontend **memerlukan backend hidup**. Tanpa backend, dashboard tidak bisa login dan
halaman apa pun akan menampilkan error koneksi; `npm run dev` tetap menyala, tetapi
semua permintaan `/api` gagal.

## Deployment

Tidak ada container frontend. `npm run build` menghasilkan folder `build/` yang dilayani
oleh nginx operator sendiri (TLS dan gerbang luar sudah ditangani di sana). Ringkasnya:

1. `cd frontend && npm ci && npm run build`
2. salin `build/` ke document root nginx
3. pasang blok `location /api/` dan SPA fallback dari
   [`docs/deploy/nginx-example.conf`](docs/deploy/nginx-example.conf)
4. di backend: `API_HOST=127.0.0.1`, `FORWARDED_ALLOW_IPS=<ip nginx>`, dan
   `security.cookie_secure=true` bila memakai HTTPS

## Menjalankan keduanya (development)

Terminal 1 — backend:

```bash
cd backend
python -m venv .venv && .venv/Scripts/activate     # Windows
pip install -r requirements-dev.txt
PYTHONPATH=src python -m tuyabot.main              # http://127.0.0.1:8080
```

Terminal 2 — frontend:

```bash
cd frontend
npm install
npm run dev                                        # http://localhost:5173
```

Vite mem-proxy `/api` ke `http://127.0.0.1:8080`, sehingga cookie sesi dan CSRF tetap
same-origin di development.

## Dokumentasi

- Spesifikasi lengkap: [`docs/superpowers/specs/`](docs/superpowers/specs/)
- Rencana implementasi: [`docs/superpowers/plans/`](docs/superpowers/plans/)
- Contoh konfigurasi nginx: [`docs/deploy/nginx-example.conf`](docs/deploy/nginx-example.conf)
- Detail API, backup/restore, troubleshooting: [`backend/README.md`](backend/README.md)

## CI

- `.github/workflows/backend.yml` — ruff + pytest untuk `backend/`.
- `.github/workflows/frontend.yml` — svelte-check, Vitest, dan build, dengan `build/`
  diunggah sebagai artifact untuk dideploy.
