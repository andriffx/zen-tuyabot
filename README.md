# Monorepo: Tuya Smart Home

Dua aplikasi dalam satu repo:

| Folder | Isi | Stack |
|---|---|---|
| [`backend/`](backend/README.md) | Bot Telegram + REST API + SQLite | Python 3.11, FastAPI, python-telegram-bot, tinytuya |
| `frontend/` | Dashboard web | SvelteKit, Tailwind, shadcn-svelte |

## Arsitektur

```
Browser ──> frontend (nginx, SPA) ──/api──> backend (FastAPI) ──> SQLite
                                                    ├─> Telegram bots
                                                    ├─> Scheduler
                                                    └─> Tuya devices (LAN)
```

Frontend **memerlukan backend hidup**. Tanpa backend, dashboard tidak bisa login dan
halaman apa pun akan menampilkan error koneksi; `npm run dev` tetap menyala, tetapi
semua permintaan `/api` gagal.

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

- Spesifikasi lengkap: [`backend/docs/superpowers/specs/`](backend/docs/superpowers/specs/)
- Rencana implementasi backend: [`backend/docs/superpowers/plans/`](backend/docs/superpowers/plans/)
- Detail API, backup/restore, troubleshooting: [`backend/README.md`](backend/README.md)

## CI

`.github/workflows/backend.yml` menjalankan ruff + pytest untuk `backend/`.
Workflow frontend ditambahkan bersamaan dengan scaffold-nya.
