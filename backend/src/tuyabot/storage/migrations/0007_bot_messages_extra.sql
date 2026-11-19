-- 0007_bot_messages_extra.sql — teks chat yang ditambahkan setelah 0006.
-- 0006 tidak boleh disunting lagi: checksum-nya sudah tercatat di database
-- yang menjalankannya. Tambahan berikutnya juga harus jadi file baru.
--
-- Dua bagian: baris baru (INSERT) dan teks yang berubah sejak 0006 (UPDATE).
-- UPDATE wajib, bukan INSERT OR IGNORE: baris lama sudah ada di database, jadi
-- IGNORE akan membiarkan teks lama dan kode yang mengharapkan {device} tak
-- pernah mendapatkannya.

INSERT OR IGNORE INTO bot_messages (key, text) VALUES
    ('start.public', '👋 Halo {name}!

🤖 *Bot Smart Home*
Role Anda: *Publik*

Pilih menu di bawah untuk mulai. Buka *Akun Saya* untuk melihat ID yang perlu didaftarkan Superadmin.'),
    ('help.header', '📖 *Bantuan*'),
    ('users.header', '👥 *User Telegram*'),
    ('devices.header', '📱 *Perangkat*'),
    ('status.header', '📊 *Status*'),
    ('help.none', 'Belum ada perangkat yang bisa Anda akses. Minta admin memberi akses.'),
    ('users.adduser_format', 'Format: /adduser <telegram_id> <role>'),
    ('users.role_unknown', 'Role tidak dikenal. Pilihan: {available}'),
    ('users.removeuser_format', 'Format: /removeuser <telegram_id>'),
    ('users.not_found', 'User tidak ditemukan.'),
    ('users.subset_denied', 'Tidak boleh memberikan role dengan izin melebihi izin Anda.'),
    ('logs.header', '🧾 *Aktivitas terakhir*'),
    ('logs.empty', 'Belum ada aktivitas.'),
    ('notify.watchdog_failed', '⚠️ *{device} gagal dimatikan otomatis*

Sistem mencoba mematikan perangkat karena: {reason}.

Perangkat *mungkin masih menyala*. Periksa koneksi lalu matikan manual.');

-- Teks yang berubah setelah 0006 dirilis. Placeholder {device} ditambahkan agar
-- pesan menyebut perangkat mana, bukan hanya "Berhasil Dinyalakan".
UPDATE bot_messages SET text = 'Perangkat ''{name}'' tidak ditemukan.'
 WHERE key = 'device.not_found' AND text NOT LIKE '%{name}%';
UPDATE bot_messages SET text = '✅ {device} berhasil dinyalakan'
 WHERE key = 'control.ok_on' AND text NOT LIKE '%{device}%';
UPDATE bot_messages SET text = '✅ {device} berhasil dimatikan'
 WHERE key = 'control.ok_off' AND text NOT LIKE '%{device}%';
UPDATE bot_messages SET text = '❌ Gagal {action} {device} — {message}'
 WHERE key = 'control.fail' AND text NOT LIKE '%{device}%';

-- Kunci yang 0006 masukkan tetapi tidak dipakai kode lagi. Dibuang di sini,
-- bukan dengan menyunting 0006, supaya checksum 0006 tetap seperti yang sudah
-- tercatat di database yang menjalankannya.
DELETE FROM bot_messages
 WHERE key IN ('menu.air', 'menu.lampu', 'menu.clean', 'btn.status', 'control.noop');
