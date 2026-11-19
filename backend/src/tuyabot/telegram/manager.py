"""Runs zero or more Telegram bots, each its own Application.

Two constraints shape this module:

1. python-telegram-bot bounds an Application to the event loop it was built in,
   so every build happens inside the running loop — never at import, never in a
   worker thread.
2. One bad token must not take down the other bots or the API. Each bot owns
   its lifecycle and its errors.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from telegram.ext import Application, ApplicationBuilder

from ..settings import service as settings_service
from ..storage.repos import bots as bots_repo
from . import guards, handlers

logger = logging.getLogger(__name__)

CONFLICT_HINT = (
    "Bot ini sedang berjalan di tempat lain (Conflict: terminated by other getUpdates). "
    "Pastikan hanya satu instance yang memakai token ini."
)

REDACTED = "[token]"


def _sanitize(message: str, token: str | None) -> str:
    """Strip the token from error text before it is stored or logged.

    python-telegram-bot's InvalidToken message quotes the token verbatim, and
    `last_error` is returned by GET /api/bots — so without this the one secret
    the API promises never to return would be readable from the dashboard.
    """
    if token:
        message = message.replace(token, REDACTED)
        # Also redact the bare numeric part, which some errors print alone.
        prefix = token.split(":", 1)[0]
        if len(prefix) >= 6:
            message = message.replace(prefix, REDACTED)
    return message


class BotManager:
    def __init__(self) -> None:
        self._apps: dict[int, Application] = {}
        self._status: dict[int, str] = {}
        self._lock = asyncio.Lock()

    # ── introspection ──
    def status(self) -> dict[int, str]:
        return dict(self._status)

    async def send(self, chat_id: int, text: str) -> bool:
        """Send a message through the first running bot.

        Used by the watchdog, which has no Update to reply to. Failure is
        reported, never raised: a notification must not take the caller down.
        """
        for application in self._apps.values():
            try:
                await application.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
                return True
            except Exception as exc:  # network, blocked bot, unknown chat
                logger.warning("[TELEGRAM] gagal kirim ke %s: %s", chat_id, exc)
        return False

    def running_ids(self) -> list[int]:
        return [bot_id for bot_id, state in self._status.items() if state == "running"]

    # ── lifecycle ──
    async def start_all(self) -> None:
        if not settings_service.get_bool("telegram.enabled"):
            logger.info("[TELEGRAM] dinonaktifkan lewat setting; tidak ada bot yang dijalankan")
            return
        for record in bots_repo.enabled_bots():
            await self.enable(record["id"])

    async def enable(self, bot_id: int) -> str:
        """Start one bot. Returns its resulting status."""
        async with self._lock:
            if bot_id in self._apps:
                return self._status.get(bot_id, "running")

            token = bots_repo.get_token(bot_id)
            if not token:
                self._status[bot_id] = "missing_token"
                bots_repo.record_error(bot_id, "Token kosong")
                return "missing_token"

            self._status[bot_id] = "starting"
            try:
                application = self._build(token)
                await application.initialize()
                await application.start()
                await application.updater.start_polling(
                    allowed_updates=["message", "callback_query"],
                    drop_pending_updates=True,
                )
                self._apps[bot_id] = application

                me = application.bot
                username = f"@{me.username}" if getattr(me, "username", None) else None
                bots_repo.record_ok(bot_id, username)
                self._status[bot_id] = "running"
                logger.info("[TELEGRAM] bot %s aktif (%s)", bot_id, username or "unknown")
                return "running"
            except Exception as exc:  # invalid token, network, conflict
                message = _sanitize(str(exc), token)
                if "Conflict" in message or "terminated by other getUpdates" in message:
                    message = CONFLICT_HINT
                bots_repo.record_error(bot_id, message)
                self._status[bot_id] = "error"
                logger.error("[TELEGRAM] bot %s gagal start: %s", bot_id, message)
                return "error"

    async def disable(self, bot_id: int) -> str:
        async with self._lock:
            application = self._apps.pop(bot_id, None)
            if application is None:
                self._status[bot_id] = "stopped"
                return "stopped"
            self._status[bot_id] = "stopping"
            await self._shutdown(application)
            self._status[bot_id] = "stopped"
            return "stopped"

    async def rebuild(self, bot_id: int) -> str:
        """Stop and start a bot, e.g. after its token changed."""
        await self.disable(bot_id)
        return await self.enable(bot_id)

    async def shutdown(self) -> None:
        async with self._lock:
            for bot_id, application in list(self._apps.items()):
                await self._shutdown(application)
                self._status[bot_id] = "stopped"
            self._apps.clear()

    async def _shutdown(self, application: Application) -> None:
        try:
            if application.updater and application.updater.running:
                await application.updater.stop()
            await application.stop()
            await application.shutdown()
        except Exception:
            logger.exception("[TELEGRAM] gagal menutup Application")

    def _build(self, token: str) -> Application:
        builder = ApplicationBuilder().token(token).concurrent_updates(True)
        application = builder.build()
        application.add_handler(_principal_handler(), group=-1)
        handlers.register(application)
        return application


def _principal_handler():
    """Resolve the caller's identity before any command handler runs."""
    from telegram.ext import MessageHandler, filters

    async def attach(update, context):
        user = update.effective_user
        context.user_data["principal"] = guards.resolve(user.id) if user else None

    return MessageHandler(filters.ALL, attach)


manager = BotManager()


def validate_token_sync(token: str) -> dict[str, Any]:
    """Check a token outside the loop. Used by the API's 'test' action."""
    import httpx

    try:
        response = httpx.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        payload = response.json()
        if payload.get("ok"):
            return {"ok": True, "username": payload["result"].get("username")}
        return {"ok": False, "message": payload.get("description", "Token tidak valid")}
    except Exception as exc:
        return {"ok": False, "message": str(exc)}
