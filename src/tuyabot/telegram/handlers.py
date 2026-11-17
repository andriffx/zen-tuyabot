"""Telegram command and callback handlers.

Handlers are generic: they resolve devices from the registry, never from a
hardcoded name, so adding a device in the dashboard makes it controllable in
the bot immediately.
"""

from __future__ import annotations

import logging
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ..access import rate_limit
from ..devices import controller, registry
from ..infra import state_cache
from ..settings import service as settings_service
from ..storage.repos import audit, logs, telegram_users
from ..storage.repos import roles as roles_repo

logger = logging.getLogger(__name__)

EMOJI = {"plug": "🔌", "bulb": "💡", "switch": "🔘", "sensor": "📡"}


def _principal(context: ContextTypes.DEFAULT_TYPE):
    return context.user_data.get("principal")


def _user_id(update: Update) -> int:
    return update.effective_user.id if update.effective_user else 0


def _allowed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    principal = _principal(context)
    if principal is None:
        return False
    limit = settings_service.get_int("security.login_max_attempts") * 10
    window = settings_service.get_int("security.rate_limit_window_seconds")
    role_limit = None
    if principal.role_id:
        role = roles_repo.get(principal.role_id)
        role_limit = (role or {}).get("rate_limit_per_minute")
    return rate_limit.allow(f"tg:{_user_id(update)}", role_limit or limit, window)

def _deny(principal, action: str, required: str) -> None:
    audit.write(
        "telegram",
        principal.actor_id if principal else None,
        principal.label if principal else None,
        "access.denied",
        target_kind="permission",
        target_id=required,
        result="denied",
        details={"channel": "telegram", "action": action},
    )


def _has(context: ContextTypes.DEFAULT_TYPE, *permissions: str) -> bool:
    principal = _principal(context)
    return principal is not None and all(key in principal.permissions for key in permissions)


async def _reply(update: Update, text: str, reply_markup=None) -> None:
    if update.effective_message is None:
        return
    await update.effective_message.reply_text(text, reply_markup=reply_markup)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    principal = _principal(context)
    if principal is None:
        await _reply(
            update,
            "👋 Selamat datang.\n\nAkun Telegram Anda belum terdaftar. "
            "Minta Superadmin mendaftarkan ID Anda dari dashboard.",
        )
        return

    keyboard = None
    if "devices.view" in principal.permissions:
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("📱 Daftar perangkat", callback_data="devices")]]
        )
    await _reply(
        update,
        f"👋 Halo *{principal.label}*.\nRole: *{principal.role_slug}*\n\n"
        "Perintah: /status /devices /on <nama> /off <nama>",
        reply_markup=keyboard,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lines = [
        "📖 *Bantuan*",
        "/start — mulai",
        "/help — bantuan ini",
        "/whoami — identitas & role Anda",
    ]
    principal = _principal(context)
    if principal and "devices.view" in principal.permissions:
        lines += ["/devices — daftar perangkat", "/status — status semua perangkat"]
    if principal and "devices.control" in principal.permissions:
        lines += ["/on <nama> — nyalakan", "/off <nama> — matikan"]
    if principal and "telegram_users.manage" in principal.permissions:
        lines += [
            "/users — daftar user Telegram",
            "/adduser <telegram_id> <role> — daftarkan user",
            "/removeuser <telegram_id> — hapus user",
        ]
    if principal and "logs.view" in principal.permissions:
        lines += ["/logs — aktivitas terakhir"]
    await _reply(update, "\n".join(lines))


async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    principal = _principal(context)
    if principal is None:
        await _reply(update, "Anda belum terdaftar. Role: publik.")
        return
    await _reply(
        update,
        f"🪪 ID: `{principal.actor_id}`\nNama: {principal.label}\nRole: *{principal.role_slug}*",
    )


async def devices_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    principal = _principal(context)
    if principal is None or not _has(context, "devices.view"):
        _deny(principal, "devices", "devices.view")
        await _reply(update, "Tidak berizin.")
        return
    if not _allowed(update, context):
        await _reply(update, "Terlalu sering. Coba lagi nanti.")
        return

    visible = registry.visible_to(principal)
    if not visible:
        await _reply(update, "Belum ada perangkat.")
        return
    lines = ["📱 *Perangkat*"]
    for device in visible:
        icon = EMOJI.get(device["type"], "🔌")
        lines.append(f"{icon} *{device['label']}* (`{device['name']}`)")
    await _reply(update, "\n".join(lines))


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    principal = _principal(context)
    if principal is None or not _has(context, "devices.view"):
        _deny(principal, "status", "devices.view")
        await _reply(update, "Tidak berizin.")
        return
    if not _allowed(update, context):
        await _reply(update, "Terlalu sering. Coba lagi nanti.")
        return

    lines = ["📊 *Status*"]
    for device in registry.visible_to(principal):
        result = await state_cache.get_status(device)
        if result.get("success"):
            state = "🟢 NYALA" if result.get("switch_on") else "🔴 MATI"
            power = result.get("power_w")
            suffix = f" ({power:.1f}W)" if isinstance(power, (int, float)) else ""
            lines.append(f"{EMOJI.get(device['type'], '🔌')} {device['label']}: {state}{suffix}")
        else:
            lines.append(f"⚪ {device['label']}: offline")
    await _reply(update, "\n".join(lines))


async def _toggle(update: Update, context: ContextTypes.DEFAULT_TYPE, on: bool) -> None:
    principal = _principal(context)
    if principal is None or not _has(context, "devices.control"):
        _deny(principal, "control", "devices.control")
        await _reply(update, "Tidak berizin mengontrol perangkat.")
        return
    if not _allowed(update, context):
        await _reply(update, "Terlalu sering. Coba lagi nanti.")
        return

    args = context.args or []
    if not args:
        await _reply(update, "Format: /on <nama> atau /off <nama>")
        return

    device = registry.get_by_name(args[0])
    if device is None or not registry.can_control(principal, device):
        await _reply(update, f"Perangkat '{args[0]}' tidak ditemukan.")
        return

    from ..devices import service as device_service

    result = await device_service.run_tuya(controller.controller.set_switch, device, on)

    if result.get("success"):
        state_cache.cache.invalidate(device["name"])
        await state_cache.get_status(device, force=True)

    logs.log_activity(
        device_id=device["id"],
        user_id=principal.actor_id,
        actor="bot",
        action="turn_on" if on else "turn_off",
        status="success" if result.get("success") else "failed",
        message=str(result.get("message", "")),
    )
    if result.get("success"):
        verdict = f"{device['label']}: {'dinyalakan' if on else 'dimatikan'}"
        await _reply(update, f"✅ {verdict}")
    else:
        await _reply(update, f"⚠️ Gagal: {result.get('message', 'perangkat tidak merespons')}")


async def on_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _toggle(update, context, True)


async def off_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _toggle(update, context, False)


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    principal = _principal(context)
    if principal is None or not _has(context, "telegram_users.view"):
        _deny(principal, "users", "telegram_users.view")
        await _reply(update, "Tidak berizin.")
        return
    rows = telegram_users.list_all()
    if not rows:
        await _reply(update, "Belum ada user Telegram terdaftar.")
        return
    lines = ["👥 *User Telegram*"]
    for row in rows:
        active = "" if row["is_active"] else " (nonaktif)"
        lines.append(f"`{row['telegram_id']}` — {row.get('label') or '-'} — {row['role_slug']}{active}")
    await _reply(update, "\n".join(lines))


async def adduser_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    principal = _principal(context)
    if principal is None or not _has(context, "telegram_users.manage"):
        _deny(principal, "adduser", "telegram_users.manage")
        await _reply(update, "Tidak berizin.")
        return

    args = context.args or []
    if len(args) < 2 or not args[0].lstrip("-").isdigit():
        await _reply(update, "Format: /adduser <telegram_id> <role>")
        return

    target_id = int(args[0])
    role = roles_repo.get_by_slug(args[1].lower())
    if role is None:
        available = ", ".join(r["slug"] for r in roles_repo.list_all())
        await _reply(update, f"Role tidak dikenal. Pilihan: {available}")
        return
    if not guards_can_grant(principal, role):
        _deny(principal, "adduser", "telegram_users.manage")
        await _reply(update, "Tidak boleh memberikan role dengan izin melebihi izin Anda.")
        return

    telegram_users.upsert(
        target_id,
        role["id"],
        label=args[2] if len(args) > 2 else None,
        created_by_telegram_id=principal.actor_id,
    )
    audit.write(
        "telegram",
        principal.actor_id,
        principal.label,
        "telegram_users.create",
        target_kind="telegram_user",
        target_id=target_id,
        details={"role_id": role["id"], "role_slug": role["slug"]},
    )
    await _reply(update, f"✅ `{target_id}` terdaftar dengan role *{role['slug']}*.")


def guards_can_grant(actor, role) -> bool:
    from .guards import can_grant

    return can_grant(actor, role)


async def removeuser_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    principal = _principal(context)
    if principal is None or not _has(context, "telegram_users.manage"):
        _deny(principal, "removeuser", "telegram_users.manage")
        await _reply(update, "Tidak berizin.")
        return

    args = context.args or []
    if not args or not args[0].lstrip("-").isdigit():
        await _reply(update, "Format: /removeuser <telegram_id>")
        return

    target_id = int(args[0])
    record = telegram_users.get(target_id)
    if record is None:
        await _reply(update, "User tidak ditemukan.")
        return
    if not guards_can_grant(principal, roles_repo.get(record["role_id"]) or {}):
        await _reply(update, "Tidak boleh menghapus user dengan izin melebihi izin Anda.")
        return

    telegram_users.delete(target_id)
    audit.write(
        "telegram",
        principal.actor_id,
        principal.label,
        "telegram_users.delete",
        target_kind="telegram_user",
        target_id=target_id,
    )
    await _reply(update, f"🗑️ `{target_id}` dihapus.")


async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    principal = _principal(context)
    if principal is None or not _has(context, "logs.view"):
        _deny(principal, "logs", "logs.view")
        await _reply(update, "Tidak berizin.")
        return
    rows = logs.recent_activities(limit=10)
    if not rows:
        await _reply(update, "Belum ada aktivitas.")
        return
    lines = ["🧾 *Aktivitas terakhir*"]
    for row in rows:
        lines.append(
            f"{row['created_at']} — {row.get('device_label') or '-'} — {row['action']} — {row['status']}"
        )
    await _reply(update, "\n".join(lines))


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    if query.data == "devices":
        await devices_command(update, context)


def register(application) -> None:
    """Attach every handler to an Application."""
    from telegram.ext import CallbackQueryHandler, CommandHandler

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("whoami", whoami))
    application.add_handler(CommandHandler("devices", devices_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("on", on_command))
    application.add_handler(CommandHandler("off", off_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("adduser", adduser_command))
    application.add_handler(CommandHandler("removeuser", removeuser_command))
    application.add_handler(CommandHandler("logs", logs_command))
    application.add_handler(CallbackQueryHandler(callback))


def _unused(_: Any) -> None:  # pragma: no cover - keeps typing honest
    return None
