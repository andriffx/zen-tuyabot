# Desain: Role dinamis untuk user Telegram, web hanya Superadmin

Tanggal: 2026-11-18
Status: menunggu persetujuan

## Maksud dan alasan

Sistem sekarang memakai satu tabel `roles` untuk dua hal sekaligus: izin akun web
(23 kunci seperti `devices.view`, `users.manage`) dan role user Telegram. Itu
tidak cocok dengan cara aplikasi ini dipakai. Dashboard dikelola satu orang;
yang butuh pembedaan hak akses adalah orang-orang yang mengirim perintah lewat
bot Telegram.

Referensi (`referensi/tuya-telegram-bot-new-patch`) memakai model itu: web hanya
punya Superadmin, dan role sepenuhnya soal bot — role menentukan menu yang
muncul, perangkat mana yang bisa dikontrol, aksi apa yang boleh (nyalakan saja,
atau nyalakan dan matikan), dan siapa yang menerima notifikasi.

Tujuan: memindahkan sistem ke model itu, tetapi **dinamis** — role dibuat dan
diubah dari UI web, bukan dari `ENV` atau kode.

## Tujuan

- Web hanya punya satu akun, yaitu Superadmin yang dibuat saat setup.
- Role adalah entitas bot: dibuat, dinamai, dan diatur dari UI web.
- Hak akses per role mencakup **per perangkat dan per aksi**.
- Admin bisa menambahkan user Telegram ke sebuah role dari UI web.
- Teks yang diterima pengguna di chat bisa diubah dari UI web.
- Watchdog menyala berdasarkan hak akses, bukan daftar role terpisah.

## Bukan tujuan

- Multi-tenant atau banyak Superadmin.
- Pindah ke MySQL/PostgreSQL.
- Menambah perintah bot baru.
- Mengubah tampilan dashboard selain halaman Users/Roles.

## Batasan

- Pengguna yang sudah berjalan punya data di tabel `roles`, `web_users`, dan
  `telegram_users`; migrasi harus mempertahankannya tanpa langkah manual.
- SQLite dengan satu penulis; semua perubahan skema lewat migrasi bernomor.
- `secret.key` tetap tidak ikut backup; aturan itu tidak berubah.

## Keputusan yang sudah diambil

**Ukuran pekerjaan: proyek.** Ini menyentuh skema, otorisasi, handler bot, dan
dua halaman UI.

**Model hak akses: role → perangkat → aksi (opsi A yang diperluas).**
Dipilih dari tiga opsi:

- A. Role punya daftar perangkat + satu saklar "boleh kontrol".
- B. Matriks role × perangkat × aksi penuh (lihat/nyala/mati/status terpisah).
- C. Kebalikan: perangkat memilih role yang boleh mengaksesnya.

A dipilih karena tata letaknya paling mudah dipahami saat mengedit role, tetapi
diperluas dengan aksi terpisah karena requester meminta pemisahan nyala/mati
seperti referensi (role User hanya boleh menyalakan). B ditolak: antarmukanya
jauh lebih ramai untuk manfaat yang sama. C ditolak: mengatur orang baru berarti
membuka setiap perangkat satu per satu.

**Database: tetap SQLite.** Dengan interval 5 menit dan retensi 60 hari, satu
perangkat menghasilkan 17.280 baris, dan seratus perangkat 1,7 juta baris
(~170 MB) pada laju 0,003 baris/detik. MySQL menambah container, kredensial,
jaringan, dan backup yang harus dikoordinasi dengan `secret.key` tanpa manfaat
pada beban ini.

**Watchdog mengikuti hak akses, bukan daftar role.**
Referensi memicu watchdog hanya ketika role yang menyalakan adalah USER, dan
membatalkannya ketika Admin/Superadmin menyalakan atau mematikan. Itu setara
dengan: *watchdog tidak bisa dibatalkan oleh pihak yang menyalakannya bila pihak
itu tidak boleh mematikan.* Aturan itu dipakai apa adanya, sehingga tidak ada
pengaturan role terpisah yang bisa salah sinkron dengan izin.

## Rancangan

### Skema

Tabel `roles` berhenti menyimpan izin web. Isinya menjadi:

```sql
CREATE TABLE roles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    description TEXT,
    -- Izin non-perangkat, dipisah koma: monitoring, manage_users,
    -- manage_devices, view_logs
    permissions TEXT NOT NULL DEFAULT '[]',
    rate_limit_per_minute INTEGER,
    is_protected INTEGER NOT NULL DEFAULT 0,  -- superadmin bot
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
```

Tabel akses perangkat:

```sql
CREATE TABLE role_device_access (
    role_id     INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    device_id   INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    can_view    INTEGER NOT NULL DEFAULT 0,  -- lihat status
    can_on      INTEGER NOT NULL DEFAULT 0,  -- nyalakan
    can_off     INTEGER NOT NULL DEFAULT 0,  -- matikan
    PRIMARY KEY (role_id, device_id)
);
```

`can_on` dan `can_off` terpisah karena role User di referensi boleh menyalakan
pompa tetapi tidak boleh mematikannya. `can_view` terpisah karena menerima
notifikasi status tidak sama dengan boleh mengirim perintah.

`web_users` kehilangan `role_id`. Satu baris tetap ada sebagai akun Superadmin;
tabel `web_sessions` tidak berubah.

### Katalog izin bot

Menggantikan katalog 23 kunci web:

| Kunci | Arti |
|---|---|
| `monitoring` | melihat status semua perangkat lewat bot |
| `manage_users` | menambah/mengubah user Telegram dan role |
| `manage_devices` | mengubah pemetaan device dari bot (bila nanti ada) |
| `view_logs` | `/logs` di chat |

Hak per perangkat tidak masuk katalog ini; tempatnya di `role_device_access`.

### Teks pesan yang bisa diedit

Tabel baru:

```sql
CREATE TABLE bot_messages (
    key         TEXT PRIMARY KEY,   -- mis. deny.control, menu.title, start.greeting
    text        TEXT NOT NULL,      -- template dengan {placeholder}
    updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
```

Seed awal berisi **seluruh teks yang diterima pengguna di chat**, diambil dari
string yang sekarang hardcoded di `handlers.py`. Handler membaca dari tabel
dengan fallback ke nilai seed bila baris hilang, sehingga bot tidak pernah gagal
kirim pesan hanya karena tabelnya kosong.

Cakupan (empat kelompok, semuanya bisa diedit):

**1. Label tombol keyboard** — tombol menu utama dan tombol inline.
```
menu.air            "💧 Air"
menu.lampu          "💡 Lampu"
menu.monitoring     "📊 Monitoring"
menu.manage         "👑 Manajemen Tuyabot"
menu.account        "🪪 Akun Saya"
btn.turn_on         "🟢 Nyalakan"
btn.turn_off        "🔴 Matikan"
btn.status          "ℹ️ Status"
```

**2. Isi menu per role** — bukan teks bebas, tetapi **baris mana yang muncul**.
Ini turunan dari izin, jadi tidak diedit sebagai teks; yang diedit adalah
labelnya. Susunan menu mengikuti `role_device_access` dan izin bot role itu.

**3. Pesan sistem dan penolakan** — yang sekarang menyebar sebagai literal.
```
start.greeting      "👋 Halo {name}! Role Anda: *{role}*"
deny.control        "Tidak berizin mengontrol perangkat."
deny.command        "Perintah ini memerlukan role *{required}*."
deny.rate_limit     "Terlalu sering. Coba lagi nanti."
deny.unregistered   "Anda belum terdaftar. Role: publik."
device.not_found    "Perangkat '{name}' tidak ditemukan."
device.no_devices   "Belum ada perangkat."
help.text           "Perintah: /status /devices /on <nama> /off <nama>"
users.empty         "Belum ada user Telegram terdaftar."
users.row           "`{id}` — {label} — {role}{active}"
```

**4. Notifikasi otomatis** — dikirim saat peristiwa terjadi.
```
notify.power_on     "{label}: {state}"
notify.power_on_ok  "✅ {verdict}"
notify.power_fail   "⚠️ Gagal: {message}"
notify.offline      "⚪ {label}: offline"
notify.watchdog_off "🛑 {label} dimatikan otomatis ({reason})"
notify.auto_off_idle    "daya {power:.1f}W di bawah batas"
notify.auto_off_max     "melewati batas waktu {minutes} menit"
```

Placeholder yang tersedia didokumentasikan per kunci dan ditampilkan di UI saat
mengedit. Placeholder yang tidak dikenal dibiarkan apa adanya (tidak menyebabkan
error), tetapi UI memperingatkan bila nama variabel tidak ada di daftar kunci itu.

Validasi: `text` tidak boleh kosong. Format Markdown tidak divalidasi ketat —
Telegram menolak kirim bila markup rusak, jadi UI menampilkan pratinjau dan
tombol uji kirim ke chat Superadmin.

### Isi awal template

Seed `bot_messages` bukan teks karangan: isinya disalin dari referensi, supaya
saat pertama dibuka kolom editor sudah berisi sesuatu yang bisa diubah, bukan
kosong. Teks di bawah adalah nilai seed yang sebenarnya.

**Label tombol**

| Kunci | Isi |
|---|---|
| `menu.account` | `🪪 Akun Saya` |
| `menu.clean` | `🧹 Clean Message` |
| `menu.help` | `📖 Bantuan` |
| `menu.air` | `💧 Air` |
| `menu.lampu` | `💡 Lampu` |
| `menu.monitoring` | `📊 Monitoring` |
| `menu.manage` | `👑 Manajemen Tuyabot` |
| `btn.turn_on` | `🟢 Nyalakan` |
| `btn.turn_off` | `🔴 Matikan` |
| `btn.status` | `ℹ️ Status` |

**Pesan sistem**

| Kunci | Isi |
|---|---|
| `start.greeting` | `👋 Halo {name}!`<br>`🤖 *Bot Smart Home*`<br>`Role Anda: *{role}*`<br>`Pilih menu di bawah untuk mulai:` |
| `account.info` | `🪪 *Informasi Akun Anda*`<br>`` `User ID: {uid}` ``<br>`Role: {role}` |
| `help.text` | `Perintah: /status /devices /on <nama> /off <nama>` |
| `users.empty` | `Belum ada user Telegram terdaftar.` |
| `users.row` | `` `{id}` — {label} — {role}{active} `` |

**Penolakan**

| Kunci | Isi |
|---|---|
| `deny.public` | `🚫 *Akses ditolak*`<br>`Anda belum memiliki akses.`<br>`` `User ID: {uid}` ``<br>`Hubungi superadmin untuk mendapatkan akses.` |
| `deny.role` | `⛔ *Akses ditolak*`<br>`Anda tidak memiliki izin untuk {action}.` |
| `deny.device` | `Anda adalah *User* — hanya bisa kontrol **AIR**.`<br>`Kontrol lampu memerlukan role **Admin**.` |
| `deny.rate_limit` | `Terlalu sering. Coba lagi nanti.` |

Baris `deny.device` di referensi masih menyebut nama perangkat secara tetap
("AIR"/"lampu"). Seed di sini memakai placeholder agar netral terhadap perangkat
apa pun: `Anda tidak memiliki akses ke {device}.`

**Hasil kontrol**

| Kunci | Isi |
|---|---|
| `control.pending` | `⏳ Mengirim perintah…` |
| `control.ok_on` | `✅ Berhasil Dinyalakan` |
| `control.ok_off` | `✅ Berhasil Dimatikan` |
| `control.noop` | `ℹ️ Sudah Menyala (tidak ada perubahan)` |
| `control.fail` | `❌ Gagal {action} — {message}` |
| `control.offline` | `❌ *{device} tidak terhubung*`<br>`` _Error:_ `{message}` ``<br>`• Bot & perangkat di jaringan WiFi yang sama?`<br>`• Perangkat masih nyala & terhubung WiFi?`<br>`• IP perangkat sudah benar?` |

**Notifikasi otomatis**

| Kunci | Isi |
|---|---|
| `notify.watchdog_off_user` | `💧 *Pemberitahuan Otomatisasi Pompa Air*`<br>`Pompa air telah mencapai batas durasi operasional maksimal (*{minutes} menit*).`<br>`🛡️ *Tindakan Sistem*: Pompa telah dinonaktifkan secara otomatis guna menghindari pemborosan listrik dan air.`<br>`_Apabila Anda masih memerlukan air atau tindakan sistem ini merupakan suatu kesalahan, silakan nyalakan kembali melalui menu pompa air._` |
| `notify.watchdog_off_idle` | Sama seperti di atas, dengan baris kedua diganti:<br>`Berdasarkan pemantauan sistem, pompa air terdeteksi *sudah tidak digunakan* (beban daya: `{power:.1f} W`).` |
| `notify.watchdog_off_admin` | `🚨 *Notifikasi Otomatisasi Pompa Air*`<br>`Pompa air yang sebelumnya diaktifkan oleh:`<br>`👤 *User*   : {user_name} (@{username})`<br>`🆔 *ID*     : `{user_id}``<br>`Telah *dinonaktifkan secara otomatis* oleh sistem.`<br>`📌 *Keterangan*: {reason}`<br>`⏰ *Waktu*     : `{timestamp}`` |
| `notify.device_offline` | `⚪ {device}: offline` |

Nama perangkat pada seed mengikuti placeholder `{device}`, bukan literal "air",
karena aplikasi ini mendukung perangkat apa pun. Referensi hanya punya dua
perangkat bernama tetap, sehingga teksnya menyebut "air" dan "lampu" secara
langsung.



### Watchdog

Aturan: setelah perintah nyala berhasil, watchdog dipasang bila role pelaku
**tidak** punya `can_off` untuk perangkat itu. Perintah mati membatalkannya.
`watchdog.trigger_role_slug` dihapus dari registry karena menjadi turunan.

### API dan UI

| Endpoint | Perubahan |
|---|---|
| `GET/POST/PATCH/DELETE /api/roles` | menerima `device_access` dan izin bot |
| `PUT /api/roles/{id}/devices` | ganti seluruh matriks akses sekaligus |
| `GET /api/bot-messages` | daftar kunci teks beserta placeholder yang tersedia |
| `PUT /api/bot-messages/{key}` | simpan satu teks |
| `POST /api/bot-messages/{key}/preview` | render template dengan data contoh |
| `POST /api/bot-messages/{key}/send` | kirim uji ke chat Superadmin |
| `/api/web-users` | dihapus |
| `/api/telegram-users` | tetap, ditambah filter per role |

Halaman UI:

- **Roles** — daftar role, editor dengan dua bagian: izin bot (checkbox) dan
  tabel perangkat dengan tiga kolom centang (`Lihat`, `Nyalakan`, `Matikan`).
- **Telegram Users** — tambah user, pilih role, aktif/nonaktif.
- **Pesan Bot** — daftar kunci dikelompokkan empat bagian (Label tombol, Pesan
  sistem, Penolakan, Notifikasi), editor teks dengan daftar placeholder yang
  bisa diklik untuk disisipkan, pratinjau hasil render, dan tombol kirim uji.
- **Users** dan **Settings → Users** — dihapus dari sidebar.

### Migrasi

`0005_telegram_roles.sql`:

1. Tambah kolom baru pada `roles`, kosongkan `permissions` lama (izin web tidak
   berlaku lagi), isi ulang dengan izin bot untuk role yang sudah ada.
2. Buat `role_device_access` dan isi dari `devices.access_roles` yang sudah ada
   (kolom tersebut menyimpan daftar role per perangkat — sumber yang sama,
   arah sebaliknya), dengan `can_view/can_on/can_off` = 1 untuk setiap pasangan.
3. Buat `bot_messages` dan seed teks.
4. `web_users.role_id`: SQLite tidak mendukung `DROP COLUMN` sebelum 3.35;
   kolom dibiarkan ada tetapi tidak dipakai, dan dicatat di dokumen ini.

### Yang diserahkan ke pelaksana

- Susunan akhir kunci teks pesan dan placeholder-nya.
- Apakah editor pesan memakai textarea biasa atau pratinjau Markdown.
- Urutan pengerjaan: skema → otorisasi → handler → UI.

## Risiko

- **Role lama menjadi tidak bermakna.** Izin web di `roles.permissions` hilang
  artinya; pengguna yang dulu punya role di web kini hanya Superadmin. Itu
  memang tujuannya, tetapi harus dinyatakan di catatan rilis.
- **`access_roles` per perangkat dan `role_device_access` bisa berbeda** setelah
  migrasi bila keduanya diubah terpisah. Rencananya `access_roles` dihapus dari
  `devices` dan akses sepenuhnya pindah ke tabel baru. Perlu keputusan saat
  pelaksanaan apakah kolomnya dihapus atau dibiarkan tidak terpakai.
