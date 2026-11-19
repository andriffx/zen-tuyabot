"""Bot message templates, editable from the dashboard.

Seed values are the texts the bot already sent, so an operator opening the
editor sees something real to change rather than empty boxes. A missing row
falls back to the seed, which means a cleared or partially-migrated table can
never stop the bot from replying.
"""

from __future__ import annotations

from typing import Any

from .. import db

# Grouped by role in the UI; the prefix before the dot is the group.
SEED: dict[str, str] = {
    # ── Label tombol ──
    "menu.account": "🪪 Akun Saya",
    "menu.clean": "🧹 Clean Message",
    "menu.help": "📖 Bantuan",
    "menu.air": "💧 Air",
    "menu.lampu": "💡 Lampu",
    "menu.monitoring": "📊 Monitoring",
    "menu.manage": "👑 Manajemen Tuyabot",
    "btn.turn_on": "🟢 Nyalakan",
    "btn.turn_off": "🔴 Matikan",
    "btn.status": "ℹ️ Status",
    # ── Pesan sistem ──
    "start.greeting": (
        "👋 Halo {name}!\n"
        "🤖 *Bot Smart Home*\n"
        "Role Anda: *{role}*\n\n"
        "Pilih menu di bawah untuk mulai:"
    ),
    "account.info": "🪪 *Informasi Akun Anda*\n`User ID: {uid}`\nRole: {role}",
    "help.text": "Perintah: /status /devices /on <nama> /off <nama>",
    "device.none": "Belum ada perangkat.",
    "device.not_found": "Perangkat '{name}' tidak ditemukan.",
    "help.control_format": "Format: /on <nama> atau /off <nama>",
    "users.empty": "Belum ada user Telegram terdaftar.",
    "users.row": "`{id}` — {label} — {role}{active}",
    # ── Penolakan ──
    "deny.public": (
        "🚫 *Akses ditolak*\n"
        "Anda belum memiliki akses.\n"
        "`User ID: {uid}`\n\n"
        "Hubungi superadmin untuk mendapatkan akses."
    ),
    "deny.role": "⛔ *Akses ditolak*\nAnda tidak memiliki izin untuk {action}.",
    "deny.device": "Anda tidak memiliki akses ke {device}.",
    "deny.rate_limit": "Terlalu sering. Coba lagi nanti.",
    # ── Hasil kontrol ──
    "control.pending": "⏳ Mengirim perintah…",
    "control.ok_on": "✅ Berhasil Dinyalakan",
    "control.ok_off": "✅ Berhasil Dimatikan",
    "control.noop": "ℹ️ Sudah Menyala (tidak ada perubahan)",
    "control.fail": "❌ Gagal {action} — {message}",
    "control.offline": (
        "❌ *{device} tidak terhubung*\n\n"
        "_Error:_ `{message}`\n\n"
        "• Bot & perangkat di jaringan WiFi yang sama?\n"
        "• Perangkat masih nyala & terhubung WiFi?\n"
        "• IP perangkat sudah benar?"
    ),
    # ── Notifikasi otomatis ──
    "notify.watchdog_off_user": (
        "💧 *Pemberitahuan Otomatisasi Pompa Air*\n\n"
        "Pompa air telah mencapai batas durasi operasional maksimal (*{minutes} menit*).\n\n"
        "🛡️ *Tindakan Sistem*: Pompa telah dinonaktifkan secara otomatis guna "
        "menghindari pemborosan listrik dan air.\n\n"
        "_Apabila Anda masih memerlukan air atau tindakan sistem ini merupakan suatu "
        "kesalahan, silakan nyalakan kembali melalui menu pompa air._"
    ),
    "notify.watchdog_off_idle": (
        "💧 *Pemberitahuan Otomatisasi Pompa Air*\n\n"
        "Berdasarkan pemantauan sistem, pompa air terdeteksi *sudah tidak digunakan* "
        "(beban daya: `{power:.1f} W`).\n\n"
        "🛡️ *Tindakan Sistem*: Pompa telah dinonaktifkan secara otomatis guna "
        "menghindari pemborosan listrik dan air.\n\n"
        "_Apabila Anda masih memerlukan air atau tindakan sistem ini merupakan suatu "
        "kesalahan, silakan nyalakan kembali melalui menu pompa air._"
    ),
    "notify.watchdog_off_admin": (
        "🚨 *Notifikasi Otomatisasi Pompa Air*\n\n"
        "Pompa air yang sebelumnya diaktifkan oleh:\n"
        "👤 *User*   : {user_name} (@{username})\n"
        "🆔 *ID*     : `{user_id}`\n\n"
        "Telah *dinonaktifkan secara otomatis* oleh sistem.\n"
        "📌 *Keterangan*: {reason}\n"
        "⏰ *Waktu*     : `{timestamp}`"
    ),
    "notify.device_offline": "⚪ {device}: offline",
}


class _SafeDict(dict):
    """Unknown placeholders are left as written rather than raising.

    A typo in an operator-edited template must not take the bot down; the UI
    warns about unknown names when saving.
    """

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def get(key: str) -> str:
    with db.connection() as cur:
        cur.execute("SELECT text FROM bot_messages WHERE key = ?", (key,))
        row = cur.fetchone()
    if row is not None and row["text"].strip():
        return row["text"]
    return SEED.get(key, "")


def render(key: str, **context: Any) -> str:
    return get(key).format_map(_SafeDict(context))


def set_text(key: str, text: str) -> None:
    if not text.strip():
        raise ValueError("text tidak boleh kosong")
    with db.connection(immediate=True) as cur:
        cur.execute(
            "INSERT INTO bot_messages (key, text, updated_at) "
            "VALUES (?, ?, datetime('now','localtime')) "
            "ON CONFLICT(key) DO UPDATE SET text = excluded.text, updated_at = excluded.updated_at",
            (key, text),
        )


def placeholders(key: str) -> list[str]:
    """Field names the template can be given, as written in the seed."""
    import string

    template = SEED.get(key, "")
    return sorted({name for _, name, _, _ in string.Formatter().parse(template) if name})


def all_messages() -> list[dict[str, Any]]:
    rows = []
    for key, seed in SEED.items():
        rows.append({"key": key, "text": get(key), "placeholders": placeholders(key), "seed": seed})
    return rows
