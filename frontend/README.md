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
| `node e2e-smoke.mjs` | Smoke test browser: shell, guard, tema, login/logout |
| `node e2e-devices.mjs` | Smoke test browser: buat/lihat/hapus device |
| `node e2e-overview.mjs` | Smoke test browser: overview, tile, alert realtime |
| `node e2e-management.mjs` | Smoke test browser: settings, roles, users, telegram users, bots |
| `node e2e-monitoring.mjs` | Smoke test browser: log, audit, maintenance round-trip |
| `node e2e-backup.mjs` | Smoke test browser: buat/unduh backup dan restore nyata |

## Smoke test browser (manual)

Bukan bagian CI. Menjalankan aplikasi sungguhan di browser terhadap backend nyata.

```bash
npx playwright install chromium     # sekali per mesin
npm run dev                          # terminal 1 (backend harus hidup di :8080)
node e2e-smoke.mjs                   # terminal 2
```

Skenario yang diverifikasi:

- **e2e-smoke.mjs** — instance belum setup → wizard; instance sudah setup → login.
  Shell sidebar 12 menu, badge API & SSE tersambung, navigasi `/devices`, dialog device
  dengan DPS terisi dari template, tema gelap, logout, password salah (error inline,
  tidak berpindah halaman), reload anonim → `/login`, dan tidak ada error console.
- **e2e-devices.mjs** — membuat device lewat dialog, kartu menampilkan pesan offline,
  halaman detail menampilkan pemetaan DPS, lalu menghapusnya (idempoten).
- **e2e-overview.mjs** — tile terisi dari API nyata, alert muncul saat SSE diputus,
  dan memastikan halaman tidak kosong.
- **e2e-management.mjs** — settings tersimpan, izin terlindungi terkunci, mengubah role
  `operator` mencabut sesinya sementara editor tetap masuk, user Telegram terdaftar,
  dan token bot tidak pernah dirender.

**e2e-backup.mjs** membuat backup, mengunduhnya, lalu memulihkannya lewat dialog
(password + `RESTORE`). Restore mencabut semua sesi, jadi skripnya login ulang di akhir.

Semua skrip memakai data yang sudah ada, jadi aman dijalankan berulang. Jangan mengubah
izin role yang sedang dipakai untuk login — simpan perubahan itu mencabut sesi Anda
sendiri (perilaku backend yang disengaja).

Keduanya mendeteksi **framework error overlay / halaman kosong** dan gagal bila muncul —
HTTP 200 saja tidak dianggap bukti aplikasi berjalan. Exit code `1` bila ada cek gagal.

Variabel lingkungan: `BASE_URL` (default `http://localhost:5173`), `SHOT_DIR` (folder
screenshot), `SMOKE_USER`/`SMOKE_PASS` (kredensial).

### Integration test (opt-in)

```bash
VITE_TEST_API=1 npm run test -- --run src/lib/api/integration.test.ts
```

Butuh dev server yang mem-proxy `/api`. Node tidak punya cookie jar, jadi test ini hanya
membuktikan jalur tanpa sesi (endpoint publik, 401, kredensial salah, penolakan tulis).
Alur bersesi penuh diuji oleh skrip smoke browser di atas.

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
