-- 0005 disusun bertahap: kerangka di sini, seed bot_messages di Task 4,
-- pemetaan izin role lama di Task 9. Jangan menandai migrasi ini final
-- sebelum keduanya selesai.

-- ── Akses perangkat per role ──────────────────────────────────────────────
-- can_on dan can_off terpisah karena satu role boleh menyalakan tanpa boleh
-- mematikan (referensi: role User menyalakan air, Admin yang mematikan).
-- can_view terpisah karena melihat status tidak sama dengan mengirim perintah.
CREATE TABLE IF NOT EXISTS role_device_access (
    role_id   INTEGER NOT NULL REFERENCES roles(id)   ON DELETE CASCADE,
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    can_view  INTEGER NOT NULL DEFAULT 0 CHECK (can_view IN (0,1)),
    can_on    INTEGER NOT NULL DEFAULT 0 CHECK (can_on   IN (0,1)),
    can_off   INTEGER NOT NULL DEFAULT 0 CHECK (can_off  IN (0,1)),
    PRIMARY KEY (role_id, device_id)
);

-- Backfill dari sumber lama. devices.access_roles adalah daftar role per
-- perangkat; arahnya berlawanan, isinya sama. Setelah ini kolom itu deprecated
-- (lihat catatan di storage/repos/devices.py) dan tidak lagi menjadi sumber
-- otorisasi — role_device_access menggantikannya.
INSERT OR IGNORE INTO role_device_access (role_id, device_id, can_view, can_on, can_off)
SELECT CAST(j.value AS INTEGER), d.id, 1, 1, 1
FROM devices d, json_each(d.access_roles) j
WHERE d.access_roles IS NOT NULL
  AND d.access_roles != '[]'
  AND EXISTS (SELECT 1 FROM roles r WHERE r.id = CAST(j.value AS INTEGER));

-- ── Teks chat yang bisa diedit ────────────────────────────────────────────
-- Baris diisi di Task 4. Tabel dibuat di sini agar Task 1 dan Task 4 tidak
-- membuat file migrasi terpisah untuk hal yang sama.
CREATE TABLE IF NOT EXISTS bot_messages (
    key        TEXT PRIMARY KEY,
    text       TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- ── Izin role: dari katalog web ke katalog bot ────────────────────────────
-- Dijalankan di sini, bukan ditunggu sampai Task 9, karena katalog di
-- access/permissions.py sudah diganti ke izin bot pada Task 2. Tanpa langkah
-- ini setiap role kehilangan seluruh izinnya dan semua endpoint menolak.
-- Task 9 memverifikasi hasilnya.
--
-- Pemetaan sengaja konservatif: hanya izin yang benar-benar setara.
-- devices.control TIDAK dipetakan menjadi akses perangkat — akses itu kini
-- per perangkat di role_device_access, dan backfill di atas sudah mengisinya
-- untuk pasangan role/device yang memang tercatat.
UPDATE roles
SET permissions = COALESCE(
    (
        SELECT json_group_array(t.new_key)
        FROM (
            SELECT DISTINCT
                CASE j.value
                    WHEN 'devices.view'          THEN 'monitoring'
                    WHEN 'logs.view'             THEN 'view_logs'
                    WHEN 'telegram_users.manage' THEN 'manage_users'
                    WHEN 'devices.manage'        THEN 'manage_devices'
                END AS new_key
            FROM json_each(roles.permissions) j
            WHERE j.value IN (
                'devices.view', 'logs.view', 'telegram_users.manage', 'devices.manage'
            )
        ) t
        WHERE t.new_key IS NOT NULL
    ),
    '[]'
)
WHERE json_valid(permissions);
