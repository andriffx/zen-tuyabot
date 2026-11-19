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

from ..access import bot_auth, rate_limit
from ..devices import controller, registry
from ..infra import state_cache
from ..settings import service as settings_service
from ..storage.repos import audit, bot_messages, logs, telegram_users
from ..storage.repos import roles as roles_repo

logger = logging.getLogger(__name__)

EMOJI = {"plug": "🔌", "bulb": "💡", "switch": "🔘", "sensor": "📡"}


def _msg(key: str, **context) -> str:
    """Text for a chat message, editable from the dashboard."""
    return bot_messages.render(key, **context)


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

def _main_keyboard(principal) -> InlineKeyboardMarkup:
    """Menu of what this principal may do, labelled from bot_messages.

    Always returns a keyboard. An unregistered user has no role and no device,
    but "Akun Saya" and "Bantuan" need neither, so withholding the whole menu
    would leave them with a promise of a menu and nothing to tap.
    """
    role_id = principal.role_id if principal is not None else None
    visible = bot_auth.allowed_devices(role_id)
    rows: list[list[InlineKeyboardButton]] = []
    if bot_auth.can(role_id, "monitoring"):
        rows.append([InlineKeyboardButton(_msg("menu.monitoring"), callback_data="devices")])
    if bot_auth.can(role_id, "manage_users"):
        rows.append([InlineKeyboardButton(_msg("menu.manage"), callback_data="users")])
    controllable = [
        entry
        for entry in visible
        if entry["access"]["can_on"] or entry["access"]["can_off"]
    ]
    for entry in controllable[:4]:
        # Offer only the action this role actually holds: a menu that offers a
        # button the role may not use is a trap, not a convenience.
        buttons = []
        if entry["access"]["can_on"]:
            buttons.append(
                InlineKeyboardButton(
                    f"{_msg('btn.turn_on')} · {entry['label']}", callback_data=f"on:{entry['name']}"
                )
            )
        if entry["access"]["can_off"]:
            buttons.append(
                InlineKeyboardButton(
                    f"{_msg('btn.turn_off')} · {entry['label']}", callback_data=f"off:{entry['name']}"
                )
            )
        rows.append(buttons)
    # Always present, for every role and for a public user.
    rows.append(
        [
            InlineKeyboardButton(_msg("menu.account"), callback_data="whoami"),
            InlineKeyboardButton(_msg("menu.help"), callback_data="help"),
        ]
    )
    return InlineKeyboardMarkup(rows)


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
        # Unregistered: no role, no device, but still a menu. The two buttons it
        # offers (account, help) are exactly what this person needs to find the
        # ID a Superadmin must register.
        user = update.effective_user
        await _reply(
            update,
            _msg("start.public", name=getattr(user, "first_name", None) or "Tamu"),
            reply_markup=_main_keyboard(None),
        )
        return

    await _reply(
        update,
        _msg("start.greeting", name=principal.label, role=principal.role_slug),
        reply_markup=_main_keyboard(principal),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lines = [
        _msg("help.header"),
        "/start — mulai",
        "/help — bantuan ini",
        "/whoami — identitas & role Anda",
    ]
    principal = _principal(context)
    if principal is None:
        await _reply(update, "\n".join(lines))
        return

    role_id = principal.role_id
    if bot_auth.allowed_devices(role_id):
        lines += ["/devices — daftar perangkat", "/status — status semua perangkat"]
    if any(
        entry["access"]["can_on"] or entry["access"]["can_off"]
        for entry in bot_auth.allowed_devices(role_id)
    ):
        lines += ["/on <nama> — nyalakan", "/off <nama> — matikan"]
    if bot_auth.can(role_id, "manage_users"):
        lines += [
            "/users — daftar user Telegram",
            "/adduser <telegram_id> <role> — daftarkan user",
            "/removeuser <telegram_id> — hapus user",
        ]
    if bot_auth.can(role_id, "view_logs"):
        lines += ["/logs — aktivitas terakhir"]
    if not bot_auth.allowed_devices(role_id):
        # No device is visible, so do not advertise device commands.
        lines.append(_msg("help.none"))
    elif len(lines) == 4:
        # Devices exist but no extra command applies beyond the base list.
        lines.append(_msg("help.text"))
    await _reply(update, "\n".join(lines))


async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    principal = _principal(context)
    if principal is None:
        await _reply(update, _msg("deny.public", uid=_user_id(update)))
        return
    await _reply(
        update,
        _msg(
            "account.info",
            uid=principal.actor_id,
            name=principal.label,
            role=principal.role_slug,
        ),
    )


async def devices_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    principal = _principal(context)
    if principal is None:
        _deny(principal, "devices", "monitoring")
        await _reply(update, _msg("deny.role", action="perintah ini"))
        return
    if not _allowed(update, context):
        await _reply(update, _msg("deny.rate_limit"))
        return

    visible = registry.visible_to(principal)
    if not visible:
        await _reply(update, _msg("device.none"))
        return
    lines = [_msg("devices.header")]
    for device in visible:
        icon = EMOJI.get(device["type"], "🔌")
        lines.append(f"{icon} *{device['label']}* (`{device['name']}`)")
    await _reply(update, "\n".join(lines))


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    principal = _principal(context)
    if principal is None:
        _deny(principal, "status", "monitoring")
        await _reply(update, _msg("deny.role", action="perintah ini"))
        return
    if not _allowed(update, context):
        await _reply(update, _msg("deny.rate_limit"))
        return

    lines = [_msg("status.header")]
    for device in registry.visible_to(principal):
        result = await state_cache.get_status(device)
        if result.get("success"):
            state = "🟢 NYALA" if result.get("switch_on") else "🔴 MATI"
            power = result.get("power_w")
            suffix = f" ({power:.1f}W)" if isinstance(power, (int, float)) else ""
            lines.append(f"{EMOJI.get(device['type'], '🔌')} {device['label']}: {state}{suffix}")
        else:
            lines.append(_msg("notify.device_offline", device=device["label"]))
    await _reply(update, "\n".join(lines))


async def _toggle(update: Update, context: ContextTypes.DEFAULT_TYPE, on: bool) -> None:
    principal = _principal(context)
    # There is no role-wide control permission: the right is per device and per
    # action, so /on and /off are decided separately below.
    if principal is None:
        _deny(principal, "control", "monitoring")
        await _reply(update, _msg("deny.role", action="mengontrol perangkat"))
        return
    if not _allowed(update, context):
        await _reply(update, _msg("deny.rate_limit"))
        return

    args = context.args or []
    if not args:
        await _reply(update, _msg("help.control_format", action="on/off"))
        return

    device = registry.get_by_name(args[0])
    if device is None:
        await _reply(update, _msg("device.not_found", name=args[0]))
        return
    if not registry.can_view(principal, device):
        await _reply(update, _msg("device.not_found", name=args[0]))
        return
    if not registry.can_control(principal, device, "on" if on else "off"):
        # The device exists and is visible, but this role may not send that
        # command. Saying "not found" here would hide why nothing happened.
        action = "menyalakan" if on else "mematikan"
        _deny(principal, action, "control")
        await _reply(update, _msg("deny.device", device=args[0]))
        return

    from ..devices import service as device_service

    await _reply(update, _msg("control.pending", device=device["label"]))
    result = await device_service.run_tuya(controller.controller.set_switch, device, on)

    if result.get("success"):
        # The ACK only says the frame was accepted. Read the DP back, as the web
        # path does, or the bot claims success for a switch that did not move.
        verified = await device_service.run_tuya(controller.controller.switch_state, device)
        if verified is not None and verified is not on:
            result = {
                "success": False,
                "message": (
                    f"saklar tidak berubah (diharapkan {'nyala' if on else 'mati'}). "
                    "Periksa pemetaan DP switch."
                ),
            }

    if result.get("success"):
        state_cache.cache.invalidate(device["name"])
        await state_cache.get_status(device, force=True)
        from . import watchdog as watchdog_module

        watchdog_module.sync_after_control(
            watchdog_module.watchdog,
            device,
            on,
            principal.role_id,
            user_id=principal.actor_id,
            user_name=principal.label,
            actor_kind=principal.actor_kind,
        )

    logs.log_activity(
        device_id=device["id"],
        user_id=principal.actor_id,
        actor="bot",
        action="turn_on" if on else "turn_off",
        status="success" if result.get("success") else "failed",
        message=str(result.get("message", "")),
    )
    if result.get("success"):
        key = "control.ok_on" if on else "control.ok_off"
        await _reply(update, _msg(key, device=device["label"]))
    else:
        # The controller says whether the device was unreachable; guessing from
        # the message text mislabels a DP error as a network one and vice versa.
        key = "control.offline" if result.get("unreachable") else "control.fail"
        await _reply(
            update,
            _msg(
                key,
                action="menyalakan" if on else "mematikan",
                device=device["label"],
                message=result.get("message", "perangkat tidak merespons"),
            ),
        )


async def on_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _toggle(update, context, True)


async def off_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _toggle(update, context, False)


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    principal = _principal(context)
    if principal is None or not _has(context, "manage_users"):
        _deny(principal, "users", "manage_users")
        await _reply(update, _msg("deny.role", action="perintah ini"))
        return
    rows = telegram_users.list_all()
    if not rows:
        await _reply(update, _msg("users.empty"))
        return
    lines = [_msg("users.header")]
    for row in rows:
        lines.append(
            _msg(
                "users.row",
                id=row["telegram_id"],
                label=row.get("label") or "-",
                role=row["role_slug"],
                active="" if row["is_active"] else " (nonaktif)",
            )
        )
    await _reply(update, "\n".join(lines))


async def adduser_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    principal = _principal(context)
    if principal is None or not _has(context, "manage_users"):
        _deny(principal, "adduser", "manage_users")
        await _reply(update, _msg("deny.role", action="perintah ini"))
        return

    args = context.args or []
    if len(args) < 2 or not args[0].lstrip("-").isdigit():
        await _reply(update, _msg("users.adduser_format"))
        return

    target_id = int(args[0])
    role = roles_repo.get_by_slug(args[1].lower())
    if role is None:
        available = ", ".join(r["slug"] for r in roles_repo.list_all())
        await _reply(update, _msg("users.role_unknown", available=available))
        return
    if not guards_can_grant(principal, role):
        _deny(principal, "adduser", "manage_users")
        await _reply(update, _msg("users.subset_denied"))
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
    if principal is None or not _has(context, "manage_users"):
        _deny(principal, "removeuser", "manage_users")
        await _reply(update, _msg("deny.role", action="perintah ini"))
        return

    args = context.args or []
    if not args or not args[0].lstrip("-").isdigit():
        await _reply(update, _msg("users.removeuser_format"))
        return

    target_id = int(args[0])
    record = telegram_users.get(target_id)
    if record is None:
        await _reply(update, _msg("users.not_found"))
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
    if principal is None or not _has(context, "view_logs"):
        _deny(principal, "logs", "view_logs")
        await _reply(update, _msg("deny.role", action="perintah ini"))
        return
    rows = logs.recent_activities(limit=10)
    if not rows:
        await _reply(update, _msg("logs.empty"))
        return
    lines = [_msg("logs.header")]
    for row in rows:
        lines.append(
            f"{row['created_at']} — {row.get('device_label') or '-'} — {row['action']} — {row['status']}"
        )
    await _reply(update, "\n".join(lines))


# Every callback_data value the keyboard can emit. Kept beside the dispatcher so
# a button with no branch is a test failure, not a dead tap.
CALLBACK_COMMANDS = {"whoami": whoami, "help": help_command, "devices": devices_command,
                     "users": users_command}


def handled_callbacks() -> set[str]:
    """Callback data values the dispatcher understands (used by tests)."""
    return set(CALLBACK_COMMANDS) | {"on:", "off:"}


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    data = query.data or ""

    if data in CALLBACK_COMMANDS:
        await CALLBACK_COMMANDS[data](update, context)
        return

    # on:<name> / off:<name> — the per-device buttons.
    for prefix, flag in (("on:", True), ("off:", False)):
        if data.startswith(prefix):
            context.args = [data[len(prefix):]]
            await _toggle(update, context, flag)
            return


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
