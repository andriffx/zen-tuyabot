# Zen Tuyabot — Frontend

Dashboard web (SPA) untuk backend Zen Tuyabot. **Backend wajib berjalan**: tanpa backend,
dashboard menampilkan layar "Backend tidak dapat dihubungi".

## Pengembangan

```bash
npm install
npm run dev          # http://localhost:5173
```

Vite mem-proxy `/api` ke `http://127.0.0.1:8080`. Jalankan backend lebih dulu:

```bash
cd ../backend
PYTHONPATH=src python -m tuyabot.main
```

## Skrip

| Perintah | Isi |
|---|---|
| `npm run dev` | Dev server + proxy `/api` |
| `npm run build` | Build statis ke `build/` |
| `npm run check` | svelte-check (tipe) |
| `npm run test -- --run` | Vitest |
| `node e2e-smoke.mjs` | Smoke test browser (butuh backend + dev server hidup) |

## Deploy

Tidak ada container. Hasil `npm run build` (`build/`) dilayani nginx operator.
Konfigurasi acuan: [`../docs/deploy/nginx-example.conf`](../docs/deploy/nginx-example.conf).

Tiga hal yang harus benar:

1. `proxy_set_header Host $http_host;` — bukan `$host`, yang membuang port dan membuat
   semua mutasi 403 karena pemeriksaan `Origin`.
2. `FORWARDED_ALLOW_IPS` di backend memuat alamat nginx, agar audit mencatat IP klien.
3. `security.cookie_secure=true` saat HTTPS, jika tidak cookie tidak terkirim.

## Struktur

```
src/lib/api/       # client.ts (HTTP, CSRF, 401), errors.ts, types.ts, modul per domain
src/lib/stores/    # auth, stream (SSE), connectivity, theme
src/lib/components/  # komponen domain + ui/ (shadcn-svelte)
src/routes/        # setup, login, (app)/ halaman dashboard
```
