-- 0006_bot_messages_seed.sql — isi awal teks chat.
-- Dipisah dari 0005 agar skema dan data tidak bercampur: 0005 bisa
-- ditinjau sebagai perubahan struktur saja.

-- Seed 41 teks chat. INSERT OR IGNORE: operator yang sudah mengubah teks
-- tidak tertimpa saat migrasi dijalankan ulang.
INSERT OR IGNORE INTO bot_messages (key, text) VALUES
    ('menu.account', '🪪 Akun Saya'),
    ('menu.help', '📖 Bantuan'),
    ('menu.monitoring', '📊 Monitoring'),
    ('menu.manage', '👑 Manajemen Tuyabot'),
    ('btn.turn_on', '🟢 Nyalakan'),
    ('btn.turn_off', '🔴 Matikan'),
    ('start.public', '👋 Halo {name}!

🤖 *Bot Smart Home*
Role Anda: *Publik*

Pilih menu di bawah untuk mulai. Buka *Akun Saya* untuk melihat ID yang perlu didaftarkan Superadmin.'),
    ('start.greeting', '👋 Halo {name}!
🤖 *Bot Smart Home*
Role Anda: *{role}*

Pilih menu di bawah untuk mulai:'),
    ('account.info', '🪪 *Informasi Akun Anda*
`User ID: {uid}`
Role: {role}'),
    ('help.header', '📖 *Bantuan*'),
    ('users.header', '👥 *User Telegram*'),
    ('devices.header', '📱 *Perangkat*'),
    ('status.header', '📊 *Status*'),
    ('help.none', 'Belum ada perangkat yang bisa Anda akses. Minta admin memberi akses.'),
    ('help.text', 'Perintah: /status /devices /on <nama> /off <nama>'),
    ('device.none', 'Belum ada perangkat.'),
    ('device.not_found', 'Perangkat ''{name}'' tidak ditemukan.'),
    ('help.control_format', 'Format: /on <nama> atau /off <nama>'),
    ('users.adduser_format', 'Format: /adduser <telegram_id> <role>'),
    ('users.role_unknown', 'Role tidak dikenal. Pilihan: {available}'),
    ('users.removeuser_format', 'Format: /removeuser <telegram_id>'),
    ('users.not_found', 'User tidak ditemukan.'),
    ('users.subset_denied', 'Tidak boleh memberikan role dengan izin melebihi izin Anda.'),
    ('logs.header', '🧾 *Aktivitas terakhir*'),
    ('logs.empty', 'Belum ada aktivitas.'),
    ('users.empty', 'Belum ada user Telegram terdaftar.'),
    ('users.row', '`{id}` — {label} — {role}{active}'),
    ('deny.public', '🚫 *Akses ditolak*
Anda belum memiliki akses.
`User ID: {uid}`

Hubungi superadmin untuk mendapatkan akses.'),
    ('deny.role', '⛔ *Akses ditolak*
Anda tidak memiliki izin untuk {action}.'),
    ('deny.device', 'Anda tidak memiliki akses ke {device}.'),
    ('deny.rate_limit', 'Terlalu sering. Coba lagi nanti.'),
    ('control.pending', '⏳ Mengirim perintah…'),
    ('control.ok_on', '✅ {device} berhasil dinyalakan'),
    ('control.ok_off', '✅ {device} berhasil dimatikan'),
    ('control.fail', '❌ Gagal {action} {device} — {message}'),
    ('control.offline', '❌ *{device} tidak terhubung*

_Error:_ `{message}`

• Bot & perangkat di jaringan WiFi yang sama?
• Perangkat masih nyala & terhubung WiFi?
• IP perangkat sudah benar?'),
    ('notify.watchdog_off_user', '💧 *Pemberitahuan Otomatisasi Pompa Air*

Pompa air telah mencapai batas durasi operasional maksimal (*{minutes} menit*).

🛡️ *Tindakan Sistem*: Pompa telah dinonaktifkan secara otomatis guna menghindari pemborosan listrik dan air.

_Apabila Anda masih memerlukan air atau tindakan sistem ini merupakan suatu kesalahan, silakan nyalakan kembali melalui menu pompa air._'),
    ('notify.watchdog_off_idle', '💧 *Pemberitahuan Otomatisasi Pompa Air*

Berdasarkan pemantauan sistem, pompa air terdeteksi *sudah tidak digunakan* (beban daya: `{power:.1f} W`).

🛡️ *Tindakan Sistem*: Pompa telah dinonaktifkan secara otomatis guna menghindari pemborosan listrik dan air.

_Apabila Anda masih memerlukan air atau tindakan sistem ini merupakan suatu kesalahan, silakan nyalakan kembali melalui menu pompa air._'),
    ('notify.watchdog_off_admin', '🚨 *Notifikasi Otomatisasi Pompa Air*

Pompa air yang sebelumnya diaktifkan oleh:
👤 *User*   : {user_name}
🆔 *ID*     : `{user_id}`

Telah *dinonaktifkan secara otomatis* oleh sistem.
📌 *Keterangan*: {reason}
⏰ *Waktu*     : `{timestamp}`'),
    ('notify.watchdog_failed', '⚠️ *{device} gagal dimatikan otomatis*

Sistem mencoba mematikan perangkat karena: {reason}.

Perangkat *mungkin masih menyala*. Periksa koneksi lalu matikan manual.'),
    ('notify.watchdog_failed', '⚠️ *{device} gagal dimatikan otomatis*

Sistem mencoba mematikan perangkat karena: {reason}.

Perangkat *mungkin masih menyala*. Periksa koneksi lalu matikan manual.'),
    ('notify.device_offline', '⚪ {device}: offline');
