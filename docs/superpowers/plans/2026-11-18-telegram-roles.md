# Role Telegram Dinamis — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Memindahkan sistem otorisasi dari "role web dengan izin katalog" ke "role bot dinamis dengan akses per perangkat dan per aksi", sementara web hanya punya satu akun Superadmin.

**Architecture:** `roles` menyimpan izin bot (monitoring, manage_users, ...). Akses perangkat pindah ke tabel `role_device_access(role_id, device_id, can_view, can_on, can_off)`. Teks chat pindah ke tabel `bot_messages(key, text)` dengan seed dari referensi. `web_users.role_id` tidak lagi dipakai; halaman Users web dihapus.

**Tech Stack:** Python 3.11 / FastAPI / SQLite (stdlib sqlite3, migrasi bernomor) / python-telegram-bot 22.8 · SvelteKit 3 / Svelte 5 runes / shadcn-svelte / Vitest

**Spec:** `docs/superpowers/specs/2026-11-18-telegram-roles-design.md`

## Global Constraints

- Migrasi bernomor berurutan; migrasi ini `0005_telegram_roles.sql`. Checksum migrasi yang sudah ada tidak boleh berubah.
- SQLite: `ALTER TABLE ... DROP COLUMN` tidak dipakai. Kolom lama dibiarkan, hanya berhenti dipakai.
- Semua endpoint web tetap melewati `require(...)`; tidak ada endpoint tanpa otorisasi selain yang sudah publik (`/api/health`, `/api/setup/*`, `/api/auth/login`).
- Teks yang dibaca dari `bot_messages` harus punya fallback ke seed; bot tidak boleh gagal kirim karena tabel kosong atau baris hilang.
- Local key perangkat tidak boleh muncul di log, respons API, atau pesan chat.
- Bahasa UI: Indonesia, istilah teknis Inggris. Komentar kode: Inggris.
- Setiap perubahan skema disertai tes; setiap task diakhiri commit.
- **Migrasi `0005` disusun bertahap oleh tiga task** dan baru boleh dianggap final di akhir Task 9:
  - Task 1 — kerangka: tabel `role_device_access` + `bot_messages`, backfill akses dari `devices.access_roles`.
  - Task 4 — seed 28 baris `bot_messages`.
  - Task 9 — pemetaan izin role lama dan validasi hasil migrasi.
  Implementer Task 1 **tidak boleh** menandai migrasi selesai, dan tidak boleh menambah isi di luar kerangka itu.
- **Tidak ada refactor atau penghapusan skema di luar rencana ini.** `devices.access_roles` tetap ada dan ditandai deprecated; pembersihannya pekerjaan terpisah setelah kode terbukti tidak memakainya lagi.

## Review Focus

1. **User Telegram tanpa baris role_device_access** — mencoba `/on pompa`. Harapan: ditolak dengan pesan yang jelas, bukan crash atau sukses palsu. Tes: Task 2 `test_a_device_without_a_row_is_not_reachable`.
2. **Role dihapus saat user masih memakainya** — `telegram_users.role_id` menjadi menggantung. Harapan: penghapusan ditolak dengan 409, atau user tetap aman bila baris menggantung sudah terlanjur ada. Tes: Task 6 `test_deleting_a_role_in_use_is_refused` dan `test_a_user_whose_role_vanished_gets_no_access`.
3. **Template pesan dengan placeholder yang tidak dikenal** (`{nama_salah}`) — Harapan: terkirim literal, bot tidak crash. Tes: Task 4 `test_unknown_placeholder_is_left_alone`.
4. **Teks kosong atau hanya spasi** — Harapan: ditolak saat disimpan, tidak pernah terkirim sebagai pesan kosong. Tes: Task 4 `test_empty_text_is_rejected`.
5. **Watchdog untuk role yang bisa mematikan** — User menyalakan pompa lalu Admin mematikannya. Harapan: watchdog berhenti, tidak mematikan ulang belakangan. Tes: Task 7 `test_a_role_that_can_switch_off_does_not_arm_it`.

---

## File Structure

**Dibuat:**
- `backend/src/tuyabot/storage/migrations/0005_telegram_roles.sql` — skema baru + seed
- `backend/src/tuyabot/storage/repos/role_devices.py` — akses perangkat per role
- `backend/src/tuyabot/storage/repos/bot_messages.py` — teks chat + seed fallback
- `backend/src/tuyabot/access/bot_auth.py` — evaluasi izin bot (perangkat + aksi)
- `backend/src/tuyabot/web/routes/bot_messages.py` — API teks pesan
- `frontend/src/routes/(app)/messages/+page.svelte` — halaman Pesan Bot
- `frontend/src/lib/api/bot-messages.ts`

**Dimodifikasi:**
- `backend/src/tuyabot/storage/migrations/` — daftar migrasi
- `backend/src/tuyabot/storage/repos/roles.py` — kolom baru
- `backend/src/tuyabot/web/routes/roles.py` — device_access
- `backend/src/tuyabot/web/routes/devices.py` — otorisasi per aksi
- `backend/src/tuyabot/telegram/handlers.py` — baca bot_messages, izin per perangkat
- `backend/src/tuyabot/telegram/watchdog.py` — aturan can_off
- `backend/src/tuyabot/access/permissions.py` — katalog izin bot
- `frontend/src/lib/components/…`, sidebar, halaman roles & telegram-users

**Dihapus:**
- Halaman `frontend/src/routes/(app)/users/`
- `backend/src/tuyabot/web/routes/web_users.py`

---

### Task 1: Skema dan repo akses perangkat

**Files:**
- Create: `backend/src/tuyabot/storage/migrations/0005_telegram_roles.sql`
- Create: `backend/src/tuyabot/storage/repos/role_devices.py`
- Test: `backend/tests/test_role_devices.py`

**Interfaces:**
- Consumes: `db.connection(immediate=True)` dari `tuyabot.storage.db`
- Produces:
  - `role_devices.get_for_role(role_id: int) -> list[dict]` → `[{"device_id": int, "can_view": bool, "can_on": bool, "can_off": bool}]`
  - `role_devices.set_for_role(role_id: int, entries: list[dict]) -> None` (mengganti seluruh isi role itu)
  - `role_devices.access(role_id: int, device_id: int) -> dict | None`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_role_devices.py
from tuyabot.storage.repos import role_devices, roles
from tuyabot.storage.repos import devices as devices_repo


def test_set_and_read_back(ready_db):
    role_id = roles.create("uji", "Uji", None, ["monitoring"])
    device_id = devices_repo.create({"name": "pompa", "label": "Pompa", "tuya_id": "t1", "local_key": "k"})

    role_devices.set_for_role(role_id, [
        {"device_id": device_id, "can_view": True, "can_on": True, "can_off": False}
    ])

    assert role_devices.get_for_role(role_id) == [
        {"device_id": device_id, "can_view": True, "can_on": True, "can_off": False}
    ]


def test_set_replaces_previous_rows(ready_db):
    role_id = roles.create("uji", "Uji", None, [])
    device_id = devices_repo.create({"name": "pompa", "label": "Pompa", "tuya_id": "t1", "local_key": "k"})

    role_devices.set_for_role(role_id, [{"device_id": device_id, "can_view": True, "can_on": True, "can_off": True}])
    role_devices.set_for_role(role_id, [])

    assert role_devices.get_for_role(role_id) == []


def test_deleting_a_device_removes_its_access_rows(ready_db):
    role_id = roles.create("uji", "Uji", None, [])
    device_id = devices_repo.create({"name": "pompa", "label": "Pompa", "tuya_id": "t1", "local_key": "k"})
    role_devices.set_for_role(role_id, [{"device_id": device_id, "can_view": True, "can_on": True, "can_off": True}])

    devices_repo.delete(device_id)

    assert role_devices.get_for_role(role_id) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_role_devices.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tuyabot.storage.repos.role_devices'`

- [ ] **Step 3: Write the migration skeleton**

`backend/src/tuyabot/storage/migrations/0005_telegram_roles.sql`. Buat tabel `role_device_access` persis seperti di spec (kolom `role_id`, `device_id`, `can_view`, `can_on`, `can_off`, PK gabungan, `ON DELETE CASCADE` untuk keduanya), lalu backfill dari `devices.access_roles`:

```sql
INSERT OR IGNORE INTO role_device_access (role_id, device_id, can_view, can_on, can_off)
SELECT CAST(j.value AS INTEGER), d.id, 1, 1, 1
FROM devices d, json_each(d.access_roles) j
WHERE d.access_roles IS NOT NULL AND d.access_roles != '[]';
```

Buat juga tabel `bot_messages` (skema di spec) **tanpa isi**.

Tambahkan komentar di kepala file:

```sql
-- 0005 disusun bertahap: kerangka di sini, seed bot_messages di Task 4,
-- pemetaan izin role lama di Task 9. Jangan menandai migrasi ini final
-- sebelum keduanya selesai.
```

- [ ] **Step 3b: Mark the devices column deprecated**

Tambahkan komentar di `backend/src/tuyabot/storage/repos/devices.py` tepat di atas pemakaian `access_roles`:

```python
# DEPRECATED: access_roles hanya dipertahankan agar migrasi 0005 dapat
# mem-backfill role_device_access. Sumber otorisasi kini role_device_access;
# jangan tambahkan pemakaian baru. Penghapusan kolom menyusul di migrasi
# tersendiri setelah kode dipastikan tidak membacanya lagi.
```

Jangan mengubah perilaku apa pun di step ini.

- [ ] **Step 4: Implement `role_devices.py`**

`set_for_role` menjalankan `DELETE FROM role_device_access WHERE role_id = ?` lalu `executemany` INSERT, semuanya di dalam satu `connection(immediate=True)`. `get_for_role` mengembalikan bool dari INTEGER.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_role_devices.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add backend/src/tuyabot/storage/migrations/0005_telegram_roles.sql \
        backend/src/tuyabot/storage/repos/role_devices.py \
        backend/tests/test_role_devices.py
git commit -m "feat(be): per-device role access table and repository"
```

---

### Task 2: Evaluasi izin bot (perangkat + aksi)

**Files:**
- Create: `backend/src/tuyabot/access/bot_auth.py`
- Modify: `backend/src/tuyabot/access/permissions.py`
- Test: `backend/tests/test_bot_auth.py`

**Interfaces:**
- Consumes: `role_devices.access(role_id, device_id)` (Task 1), `roles_repo.get(role_id)`
- Produces:
  - `BOT_PERMISSIONS: tuple[str, ...]` — `("monitoring", "manage_users", "manage_devices", "view_logs")`
  - `can(role_id: int | None, permission: str) -> bool`
  - `can_device(role_id: int | None, device_id: int, action: str) -> bool` dengan `action` ∈ `("view", "on", "off")`
  - `allowed_devices(role_id: int | None) -> list[dict]` — device yang `can_view`, digabung dengan data device

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_bot_auth.py
from tuyabot.access import bot_auth
from tuyabot.storage.repos import role_devices, roles
from tuyabot.storage.repos import devices as devices_repo


def test_unknown_role_has_nothing(ready_db):
    assert bot_auth.can(None, "monitoring") is False
    assert bot_auth.can_device(None, 1, "on") is False


def test_permission_comes_from_role(ready_db):
    role_id = roles.create("uji", "Uji", None, ["monitoring"])
    assert bot_auth.can(role_id, "monitoring") is True
    assert bot_auth.can(role_id, "manage_users") is False


def test_on_and_off_are_separate(ready_db):
    role_id = roles.create("uji", "Uji", None, [])
    device_id = devices_repo.create({"name": "pompa", "label": "Pompa", "tuya_id": "t1", "local_key": "k"})
    role_devices.set_for_role(role_id, [
        {"device_id": device_id, "can_view": True, "can_on": True, "can_off": False}
    ])

    assert bot_auth.can_device(role_id, device_id, "on") is True
    assert bot_auth.can_device(role_id, device_id, "off") is False
    assert bot_auth.can_device(role_id, device_id, "view") is True


def test_a_device_without_a_row_is_not_reachable(ready_db):
    role_id = roles.create("uji", "Uji", None, [])
    device_id = devices_repo.create({"name": "pompa", "label": "Pompa", "tuya_id": "t1", "local_key": "k"})
    assert bot_auth.can_device(role_id, device_id, "view") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_bot_auth.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Replace the permission catalog in `permissions.py`**

`CATEGORIES` menjadi satu kategori berisi izin bot:
```python
CATEGORIES = {"Bot": ("monitoring", "manage_users", "manage_devices", "view_logs")}
```
`PROTECTED_REQUIRED` menjadi `frozenset({"manage_users"})`.

- [ ] **Step 4: Implement `bot_auth.py`**

`can` membaca role lewat `roles_repo.get` dan memeriksa `permissions`. `can_device` membaca `role_devices.access` lalu memilih kolom sesuai `action` (`view`→`can_view`, `on`→`can_on`, `off`→`can_off`). Role `None` atau baris hilang selalu `False`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_bot_auth.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add backend/src/tuyabot/access/bot_auth.py backend/src/tuyabot/access/permissions.py backend/tests/test_bot_auth.py
git commit -m "feat(be): bot permission and per-device action checks"
```

---

### Task 3: Otorisasi per aksi di jalur kontrol

**Files:**
- Modify: `backend/src/tuyabot/web/routes/devices.py` (`_control`, dan resolusi device)
- Modify: `backend/src/tuyabot/telegram/handlers.py` (perintah `/on`, `/off`, `/status`)
- Test: `backend/tests/test_control_authorization.py`

**Interfaces:**
- Consumes: `bot_auth.can_device` (Task 2)
- Produces: jalur kontrol web menolak dengan 403 bila principal tidak punya aksi itu; handler bot menolak dengan pesan `deny.role`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_control_authorization.py
def test_on_requires_can_on(client, login_as, ready_db):
    # device milik role tanpa can_on -> 403
    ...

def test_off_requires_can_off(client, login_as, ready_db):
    # role dengan can_on tapi bukan can_off -> /off 403, /on 200
    ...
```

Isi kedua tes mengikuti fixture `client`, `login_as`, dan pola `tests/test_devices_api.py` yang sudah ada (buat role, buat device, hubungkan lewat `role_devices.set_for_role`, lalu panggil endpoint).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_control_authorization.py -v`
Expected: FAIL — `/off` mengembalikan 200 padahal role tidak punya izin matikan

- [ ] **Step 3: Implement**

Di `_control(device_id, on, principal, request)`, sebelum memanggil `set_switch`, periksa aksi: `on=True` → `"on"`, `on=False` → `"off"`. Tolak dengan `403 {"detail": "Tidak berizin mengontrol perangkat ini"}` bila `bot_auth.can_device` False. Tambahkan pemeriksaan yang sama di handler Telegram dengan pesan dari `bot_messages`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_control_authorization.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(be): per-action authorization on device control"
```

---

### Task 4: Teks chat dari database dengan fallback seed

**Files:**
- Create: `backend/src/tuyabot/storage/repos/bot_messages.py`
- Modify: `backend/src/tuyabot/storage/migrations/0005_telegram_roles.sql` (seed baris)
- Modify: `backend/src/tuyabot/telegram/handlers.py`
- Test: `backend/tests/test_bot_messages.py`

**Interfaces:**
- Consumes: `db.connection`
- Produces:
  - `SEED: dict[str, str]` — 28 kunci dari spec §Isi awal template
  - `get(key: str) -> str` — baris DB, fallback `SEED[key]`, `""` bila tidak dikenal
  - `render(key: str, **context) -> str` — `str.format_map` dengan `_SafeDict`
  - `all_messages() -> list[dict]` — `{"key", "text", "placeholders"}` untuk API
  - `set_text(key: str, text: str) -> None`
  - `placeholders(key: str) -> list[str]`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_bot_messages.py
import pytest

from tuyabot.storage.repos import bot_messages


def test_unknown_placeholder_is_left_alone(ready_db):
    bot_messages.set_text("deny.rate_limit", "Coba lagi {nama_salah}")
    assert bot_messages.render("deny.rate_limit") == "Coba lagi {nama_salah}"


def test_known_placeholder_is_substituted(ready_db):
    bot_messages.set_text("deny.role", "Butuh {action}")
    assert bot_messages.render("deny.role", action="matikan") == "Butuh matikan"


def test_empty_text_is_rejected(ready_db):
    with pytest.raises(ValueError):
        bot_messages.set_text("deny.role", "   ")


def test_missing_row_falls_back_to_seed(ready_db):
    assert bot_messages.get("deny.rate_limit") == bot_messages.SEED["deny.rate_limit"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_bot_messages.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement `bot_messages.py`**

`SEED` disalin verbatim dari spec §Isi awal template. `_SafeDict` mengimplementasikan `__missing__` yang mengembalikan `"{" + key + "}"`. `render` memakai `str.format_map(_SafeDict(context))`. `set_text` menolak teks yang `strip()`-nya kosong dengan `ValueError`.

- [ ] **Step 4: Seed the table in the migration**

Tambahkan `INSERT INTO bot_messages (key, text) VALUES ...` untuk 28 kunci, memakai `INSERT OR IGNORE` agar migrasi idempoten.

- [ ] **Step 5: Replace literals in `handlers.py`**

Ganti setiap string yang termasuk 28 kunci dengan `bot_messages.render(...)`. Pesan yang tidak ada di daftar tetap apa adanya.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_bot_messages.py -v`
Expected: 4 passed

- [ ] **Step 7: Commit**

```bash
git commit -am "feat(be): editable bot message templates with seed fallback"
```

---

### Task 5: API dan UI teks pesan

**Files:**
- Create: `backend/src/tuyabot/web/routes/bot_messages.py`
- Create: `frontend/src/lib/api/bot-messages.ts`
- Create: `frontend/src/routes/(app)/messages/+page.svelte`
- Modify: `backend/src/tuyabot/web/app.py`, `frontend/src/lib/sidebar.ts` (atau file navigasi yang ada)
- Test: `backend/tests/test_api_bot_messages.py`, `frontend/src/lib/api/bot-messages.test.ts`

**Interfaces:**
- Consumes: `bot_messages` repo (Task 4)
- Produces: `GET /api/bot-messages`, `PUT /api/bot-messages/{key}`, `POST /api/bot-messages/{key}/preview`, `POST /api/bot-messages/{key}/send`

- [ ] **Step 1: Write the failing backend test**

```python
# backend/tests/test_api_bot_messages.py
def test_list_groups_messages_by_key(client, login_as_superadmin, ready_db):
    body = client.get("/api/bot-messages").json()
    assert any(item["key"] == "deny.rate_limit" for item in body["messages"])
    assert "action" in next(i for i in body["messages"] if i["key"] == "deny.role")["placeholders"]


def test_put_rejects_empty_text(client, login_as_superadmin, ready_db):
    response = client.put("/api/bot-messages/deny.role", json={"text": "  "})
    assert response.status_code == 422
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_api_bot_messages.py -v`
Expected: FAIL — 404

- [ ] **Step 3: Implement the route**

Semua endpoint memakai `require("manage_users")`. `preview` merender dengan nilai contoh per placeholder. `send` mengirim ke chat Superadmin yang sedang login bila ia terdaftar sebagai user Telegram; bila belum, kembalikan 409 dengan pesan yang menjelaskan.

- [ ] **Step 4: Write the failing frontend test**

```ts
// frontend/src/lib/api/bot-messages.test.ts
import { describe, expect, it } from 'vitest';
import { groupByCategory } from './bot-messages';

describe('groupByCategory', () => {
  it('splits keys by their prefix', () => {
    const grouped = groupByCategory([
      { key: 'menu.air', text: 'x', placeholders: [] },
      { key: 'deny.role', text: 'y', placeholders: ['action'] }
    ]);
    expect(grouped.menu).toHaveLength(1);
    expect(grouped.deny).toHaveLength(1);
  });
});
```

- [ ] **Step 5: Run to verify it fails**

Run: `cd frontend && npm run test -- --run src/lib/api/bot-messages.test.ts`
Expected: FAIL — module not found

- [ ] **Step 6: Implement the client and page**

`bot-messages.ts` mengekspor `botMessagesApi` dan `groupByCategory`. Halaman menampilkan empat kelompok, textarea per kunci, daftar placeholder yang bisa diklik, pratinjau, dan tombol "Kirim uji".

- [ ] **Step 7: Run to verify it passes**

Run: `cd frontend && npm run test -- --run src/lib/api/bot-messages.test.ts && npm run check`
Expected: 1 passed, 0 errors

- [ ] **Step 8: Commit**

```bash
git commit -am "feat: bot message editor API and page"
```

---

### Task 6: UI role dengan matriks perangkat, plus integritas user Telegram

**Files:**
- Modify: `frontend/src/routes/(app)/roles/+page.svelte` (dan `[id]` bila ada)
- Modify: `frontend/src/lib/api/roles.ts`, `frontend/src/lib/api/types.ts`
- Modify: `backend/src/tuyabot/web/routes/roles.py`
- Modify: `backend/src/tuyabot/web/routes/telegram_users.py`
- Modify: `frontend/src/routes/(app)/telegram-users/+page.svelte`
- Test: `backend/tests/test_api_roles_devices.py`, `backend/tests/test_api_telegram_users_integrity.py`

**Interfaces:**
- Consumes: `role_devices` (Task 1), `bot_auth.BOT_PERMISSIONS` (Task 2)
- Produces:
  - `PUT /api/roles/{id}/devices` dengan body `{"entries": [{"device_id", "can_view", "can_on", "can_off"}]}`
  - `DELETE /api/roles/{id}` menolak dengan 409 bila `telegram_users.count_by_role(role_id) > 0`, body `{"detail": "...", "user_count": n}`
  - `GET /api/telegram-users` menyertakan `role_id` dan `role_slug` yang sudah divalidasi ada

- [ ] **Step 1: Write the failing test for the matrix**

```python
def test_put_devices_replaces_the_matrix(client, login_as_superadmin, ready_db):
    # simpan dua device, lalu kirim satu -> hanya satu yang tersisa
    ...
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_api_roles_devices.py -v`
Expected: FAIL — 404/405

- [ ] **Step 3: Write the failing test for user integrity**

```python
# backend/tests/test_api_telegram_users_integrity.py
def test_deleting_a_role_in_use_is_refused(client, login_as_superadmin, ready_db):
    role_id = roles.create("uji", "Uji", None, [])
    telegram_users.upsert(7001, "Budi", role_id)

    response = client.delete(f"/api/roles/{role_id}")

    assert response.status_code == 409
    assert response.json()["user_count"] == 1
    assert roles.get(role_id) is not None


def test_creating_a_telegram_user_with_an_unknown_role_is_refused(client, login_as_superadmin, ready_db):
    response = client.post("/api/telegram-users", json={"telegram_id": 7002, "role_id": 999999})
    assert response.status_code == 422


def test_a_user_whose_role_vanished_gets_no_access(ready_db):
    """Data could still carry a dangling role_id from an older database."""
    telegram_users.upsert(7003, "Budi", roles.create("sementara", "Sementara", None, []))
    role_id = telegram_users.get(7003)["role_id"]
    with db.connection(immediate=True) as cur:
        cur.execute("PRAGMA foreign_keys=OFF")
        cur.execute("DELETE FROM roles WHERE id = ?", (role_id,))

    assert bot_auth.can_device(telegram_users.get(7003)["role_id"], 1, "on") is False
```

- [ ] **Step 4: Run to verify it fails**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_api_telegram_users_integrity.py -v`
Expected: FAIL — role masih bisa dihapus (200), role tidak dikenal diterima

- [ ] **Step 5: Implement endpoint and UI**

Endpoint matriks mengganti seluruh isi dalam satu transaksi. `DELETE /api/roles/{id}` memeriksa `telegram_users.count_by_role` lebih dulu. `POST`/`PATCH /api/telegram-users` memvalidasi `role_id` ada lewat `roles_repo.get`. UI role editor mendapat tabel: kolom Device, Lihat, Nyalakan, Matikan; setiap baris tiga checkbox. Izin bot tampil di atasnya sebagai checkbox dari `GET /api/roles/permissions`. Halaman Telegram Users menampilkan peringatan saat role dipilih yang akan ditolak, dan tetap bisa menambah user seperti sebelumnya.

- [ ] **Step 6: Run to verify it passes**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_api_roles_devices.py tests/test_api_telegram_users_integrity.py -v && cd ../frontend && npm run check`
Expected: semua passed, 0 errors

- [ ] **Step 7: Commit**

```bash
git commit -am "feat: role editor matrix and telegram user role integrity"
```

---

### Task 7: Watchdog mengikuti izin, bukan daftar role

**Files:**
- Modify: `backend/src/tuyabot/telegram/watchdog.py`
- Modify: `backend/src/tuyabot/settings/registry.py` (hapus `watchdog.trigger_role_slug`)
- Test: `backend/tests/test_watchdog_permissions.py`

**Interfaces:**
- Consumes: `bot_auth.can_device` (Task 2)
- Produces: `Watchdog.should_arm(device, role_id)` — True bila role **tidak** punya `can_off` untuk device itu.

- [ ] **Step 1: Write the failing test**

```python
def test_a_role_that_cannot_switch_off_arms_the_watchdog(ready_db):
    # role can_on=True, can_off=False -> should_arm True
    ...

def test_a_role_that_can_switch_off_does_not_arm_it(ready_db):
    # role can_on=True, can_off=True -> should_arm False
    ...
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_watchdog_permissions.py -v`
Expected: FAIL — signature masih memakai `principal_role_slug`

- [ ] **Step 3: Implement**

Ubah signature `should_arm(self, device, role_id)`; kembalikan `dps_module.has_feature(device, "watchdog") and not bot_auth.can_device(role_id, device["id"], "off")`. Perbarui pemanggil (handler Telegram dan route web) untuk meneruskan `role_id`. Hapus `watchdog.trigger_role_slug` dari `DEFAULTS` dan registry.

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_watchdog_permissions.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(be): watchdog arms based on the ability to switch off"
```

---

### Task 8: Hapus akun web multi-user

**Files:**
- Delete: `backend/src/tuyabot/web/routes/web_users.py`
- Delete: `frontend/src/routes/(app)/users/`
- Modify: `backend/src/tuyabot/web/app.py`, sidebar, `backend/src/tuyabot/storage/repos/web_users.py`
- Test: `backend/tests/test_no_web_user_management.py`

**Interfaces:**
- Consumes: tidak ada
- Produces: `/api/web-users*` mengembalikan 404; `web_users` tinggal fungsi yang dipakai login/setup (`get_with_hash`, `count`, `create_first`).

- [ ] **Step 1: Write the failing test**

```python
def test_web_users_endpoint_is_gone(client, login_as_superadmin, ready_db):
    assert client.get("/api/web-users").status_code == 404
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_no_web_user_management.py -v`
Expected: FAIL — 200

- [ ] **Step 3: Delete and rewire**

Hapus router dari `app.py`, hapus halaman dan tautan sidebar, buang fungsi repo yang hanya dipakai manajemen (`list_all`, `update`, `delete`, `set_active`). Pertahankan yang dipakai login/setup.

- [ ] **Step 4: Run tests**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest -q && cd ../frontend && npm run check && npm run test -- --run`
Expected: semua lulus

- [ ] **Step 5: Commit**

```bash
git commit -am "feat!: web has a single superadmin account"
```

---

### Task 9: Selesaikan migrasi 0005 — pemetaan izin lama dan validasi

**Files:**
- Modify: `backend/src/tuyabot/storage/migrations/0005_telegram_roles.sql`
- Test: `backend/tests/test_migration_0005.py`
- Test: `backend/tests/test_deprecated_access_roles.py`

**Interfaces:**
- Consumes: Task 1 (kerangka migrasi), Task 4 (seed `bot_messages`)
- Produces: migrasi `0005` final. Setelah task ini, tiga bagian migrasi lengkap dan boleh disebut selesai.

**Catatan kepemilikan:** task ini penutup migrasi. Bila kerangka dari Task 1 atau seed dari Task 4 belum ada, perbaiki di sini — bukan dengan memindahkan pekerjaan ke task lain.

- [ ] **Step 1: Write the failing mapping test**

```python
# backend/tests/test_migration_0005.py
def test_old_web_permissions_become_bot_permissions(tmp_path):
    # bangun DB di skema lama (0004) dengan role berisi
    #   ['devices.view', 'devices.control', 'telegram_users.manage']
    # jalankan migrasi 0005
    # assert role itu kini berisi {'monitoring', 'manage_users'}
    #       dan 'devices.control' tidak lagi tersimpan
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_migration_0005.py -v`
Expected: FAIL — izin lama masih tersimpan apa adanya

- [ ] **Step 3: Implement the mapping in the migration**

Aturan pemetaan, ditulis sebagai `UPDATE` idempoten di akhir `0005`:

| Izin lama | Izin baru |
|---|---|
| `devices.view` | `monitoring` |
| `telegram_users.manage` | `manage_users` |
| `logs.view` | `view_logs` |

Role yang seluruh izinnya tidak dikenal menjadi `[]`. Tulis lewat `json_group_array`/`json_each` bila memungkinkan, atau tiga `UPDATE` terpisah — pilih yang paling terbaca.

- [ ] **Step 4: Write the failing deprecation test**

```python
# backend/tests/test_deprecated_access_roles.py
def test_access_roles_is_not_an_authorization_source(ready_db):
    """A device granting access_roles=[role] must not authorize on its own."""
    role_id = roles.create("uji", "Uji", None, [])
    device_id = devices_repo.create({
        "name": "pompa", "label": "Pompa", "tuya_id": "t1", "local_key": "k",
        "access_roles": [role_id],
    })

    assert bot_auth.can_device(role_id, device_id, "on") is False
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd backend && ../.venv/Scripts/python.exe -m pytest tests/test_migration_0005.py tests/test_deprecated_access_roles.py -v`
Expected: passed

- [ ] **Step 6: Full verification**

Run: `cd backend && ../.venv/Scripts/python.exe -m ruff check . && ../.venv/Scripts/python.exe -m pytest -q && cd ../frontend && npm run check && npm run test -- --run && npm run build`
Expected: ruff bersih, semua tes lulus, build sukses

- [ ] **Step 7: Verify against a real upgraded database**

Salin sebuah database lama (skema 0004) ke direktori sementara, jalankan aplikasi sekali agar migrasi `0005` berjalan, lalu periksa:

```sql
SELECT key FROM bot_messages;                      -- 28 baris
SELECT COUNT(*) FROM role_device_access;           -- > 0 bila ada access_roles
SELECT slug, permissions FROM roles;               -- hanya izin bot
```

Expected: tidak ada error migrasi, dan hasil ketiga query sesuai.

- [ ] **Step 8: Commit**

```bash
git commit -am "feat(be): finish migration 0005 and validate the upgraded database"
```
