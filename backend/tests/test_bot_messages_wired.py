"""Every editable message must actually be sent by something.

A key in the editor that no code reads is a promise the product does not keep:
the operator rewrites a text and nothing changes. This scans the bot and route
modules for each key and fails on any orphan.
"""

import pathlib

from tuyabot.storage.repos import bot_messages

BACKEND = pathlib.Path(__file__).resolve().parent.parent / "src" / "tuyabot"


def _all_source() -> str:
    files = list((BACKEND / "telegram").glob("*.py")) + list((BACKEND / "web" / "routes").glob("*.py"))
    return "\n".join(path.read_text(encoding="utf-8") for path in files)


def test_every_message_key_has_a_reader():
    source = _all_source()
    orphans = [
        key
        for key in bot_messages.SEED
        if f'"{key}"' not in source and f"'{key}'" not in source
    ]

    assert orphans == [], f"pesan tanpa pembaca: {orphans}"


def test_the_watchdog_notifications_are_wired():
    source = (BACKEND / "telegram" / "watchdog.py").read_text(encoding="utf-8")
    for key in ("notify.watchdog_off_user", "notify.watchdog_off_idle", "notify.watchdog_off_admin"):
        assert key in source, f"{key} belum dikirim"
