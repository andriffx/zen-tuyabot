# Catatan lanjutan — Role Telegram Dinamis

Terakhir diperbarui: 2026-11-18

## Status saat ini

Pekerjaan berhenti di tengah, dengan sengaja. Semua commit sudah tersimpan.

| | |
|---|---|
| Worktree | `D:\Datas\MyData\Project Repo\zen-tuyabot-roles` |
| Branch | `feat/telegram-roles` |
| Commit terakhir | `b75803d` |
| Base | `fd866af` (master) |
| Master | bersih, tidak tersentuh |
| Tes | **202 lulus, 33 gagal** |

Rencana: `docs/superpowers/plans/2026-11-18-telegram-roles.md`
Desain: `docs/superpowers/specs/2026-11-18-telegram-roles-design.md`
Ledger: `.superpowers/sdd/2026-11-18-telegram-roles/progress.md` (di worktree, git-ignored)

## Yang sudah selesai

**Task 1** (`8339ff2`) — tabel `role_device_access` (`can_view`, `can_on`, `can_off`
terpisah), backfill dari `devices.access_roles`, kolom lama ditandai deprecated.
Repository `role_devices` dengan `get_for_role` / `access` / `set_for_role`.

**Task 2** (`5d11090`) — katalog izin web (23 kunci) diganti 4 izin bot
(`monitoring`, `manage_users`, `manage_devices`, `view_logs`).
`access/bot_auth.py` dengan `can`, `can_device`, `allowed_devices`.

**Task 2b** (`b75803d`) — `require()` di endpoint web hanya memeriksa autentikasi,
tidak lagi izin. Keputusan pemilik proyek: web hanya punya satu Superadmin.

## Tiga ruling yang sudah diambil (jangan diulang)

1. **`tests/test_migrate.py` hardcoded `0005_broken.sql`.** Bentrok dengan migrasi
   nyata 0005 sehingga tes rollback diam-diam tidak menguji apa pun. Sudah diubah
   menghitung nomor berikutnya.

2. **Pemetaan izin role lama dipindah lebih awal** dari Task 9 ke migrasi 0005.
   Tanpa itu, mengganti katalog di Task 2 membuat semua role kehilangan izin dan
   Superadmin sendiri ditolak. Task 9 nanti tinggal memverifikasi.

3. **Endpoint web cukup login.** `require()` menerima argumen tapi mengabaikannya,
   supaya deklarasi rute tetap mendokumentasikan maksud dan mengembalikan
   otorisasi web nanti cukup mengubah satu fungsi.

## 33 tes yang gagal — sudah dikategorikan, bukan bug

Semua mengunci model lama. Sudah diperiksa satu per satu:

- **Katalog izin** (6 di `test_permissions.py`): mengharapkan 23 kunci.
- **Role web lama** (`operator`, `viewer` sebagai role web): tes "role X dilarang"
  kini 200 karena role itu tidak ada lagi sebagai pembatas web.
- **`/api/web-users`** (11): fitur yang akan **dihapus** di Task 8.
- **Role seed** (`test_roles_repo.py`, `test_telegram_users.py`): mengharapkan
  izin lama `devices.view` dan sejenisnya.

Sempat diduga celah keamanan (403 berubah jadi 200), sudah diperiksa:
`current_principal` tetap mengembalikan 401 untuk anonim. Bukan celah.

## Langkah berikutnya, berurutan

### 0. Keputusan yang belum diambil

Pilih salah satu sebelum lanjut:

- **A. Perbaiki 33 tes dulu** (rekomendasi sebelumnya) — perbarui tes lama ke model
  baru, suite hijau, baru Task 3. Memberi sinyal bersih untuk 6 task berikutnya.
- **B. Lanjut Task 3–8** dengan suite merah sampai Task 8, setiap kegagalan baru
  diperiksa manual.

### 1. Task 3 — otorisasi per aksi di jalur kontrol

`_control` di `web/routes/devices.py` dan handler Telegram memeriksa
`bot_auth.can_device(role_id, device_id, "on"/"off")`. Tes:
`tests/test_control_authorization.py`.

### 2. Task 4 — teks chat dari database

`storage/repos/bot_messages.py` dengan `SEED` 28 kunci (isi di spec §Isi awal
template), `get`, `render` (placeholder tak dikenal dibiarkan literal),
`all_messages`, `set_text`, `placeholders`. Seed diisi di migrasi 0005.
Ganti literal di `telegram/handlers.py`. Tes: `tests/test_bot_messages.py`.

### 3. Task 5 — API dan UI pesan bot

`web/routes/bot_messages.py` (list, put, preview, send), halaman
`frontend/src/routes/(app)/messages/+page.svelte`, `lib/api/bot-messages.ts`.
Tes: `tests/test_api_bot_messages.py`, `lib/api/bot-messages.test.ts`.

### 4. Task 6 — UI role + matriks perangkat + integritas user Telegram

`PUT /api/roles/{id}/devices`; `DELETE /api/roles/{id}` menolak 409 bila masih
dipakai; role tidak dikenal ditolak 422; user dengan role menggantung tidak
mendapat akses. UI role editor dengan tabel 3 kolom centang.
Tes: `tests/test_api_roles_devices.py`, `tests/test_api_telegram_users_integrity.py`.

### 5. Task 7 — watchdog mengikuti izin

`Watchdog.should_arm(device, role_id)` → True bila role **tidak** punya `can_off`.
Hapus `watchdog.trigger_role_slug` dari registry.
Tes: `tests/test_watchdog_permissions.py`.

### 6. Task 8 — hapus akun web multi-user

Hapus `web/routes/web_users.py`, halaman `frontend/src/routes/(app)/users/`,
tautan sidebar. Pertahankan fungsi repo yang dipakai login/setup.
**Di akhir task ini suite harus hijau kembali.**
Tes: `tests/test_no_web_user_management.py`.

### 7. Task 9 — selesaikan dan validasi migrasi 0005

Verifikasi pemetaan izin, tes bahwa `devices.access_roles` bukan lagi sumber
otorisasi, lalu jalankan aplikasi pada database lama yang benar-benar di-upgrade
dan periksa hasilnya.
Tes: `tests/test_migration_0005.py`, `tests/test_deprecated_access_roles.py`.

### 8. Review whole-branch, lalu merge

Reviewer independen untuk seluruh branch, perbaiki temuan Critical/Important,
lalu gabungkan ke `master`. Setelah merge: hapus worktree.

## Cara melanjutkan

```powershell
cd "D:\Datas\MyData\Project Repo\zen-tuyabot-roles"
git log --oneline -3          # pastikan di b75803d
cat .superpowers\sdd\2026-11-18-telegram-roles\progress.md
```

Interpreter tes (venv ada di worktree master, bukan di worktree roles):

```powershell
"D:/Datas/MyData/Project Repo/zen-tuyabot/.venv/Scripts/python.exe" -m pytest -q
```

## Catatan teknis yang mudah dilupakan

- Migrasi 0005 **disusun bertahap**: kerangka + backfill + pemetaan izin sudah ada;
  seed `bot_messages` menyusul di Task 4.
- `devices.access_roles` **jangan dihapus**. Tetap ada, deprecated, hanya untuk
  backfill. Penghapusan adalah pekerjaan terpisah setelah kode terbukti bersih.
- `frontend/build/` di worktree roles belum pernah di-build; jalankan `npm ci`
  dulu di `frontend/` sebelum `npm run build`.
- Server produksi masih menjalankan versi `master` (`fd866af`). Tidak ada yang
  berubah di sana sampai branch ini di-merge.
