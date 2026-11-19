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


def test_every_seed_key_is_listed_with_its_placeholders(ready_db):
    rows = {row["key"]: row for row in bot_messages.all_messages()}
    assert len(rows) == len(bot_messages.SEED)
    assert "action" in rows["deny.role"]["placeholders"]
    assert rows["account.info"]["placeholders"] == ["role", "uid"]


def test_a_stored_blank_row_still_falls_back(ready_db):
    """An empty row must not blank the bot's reply."""
    from tuyabot.storage import db

    # The seed already inserted this key; blank it out rather than inserting.
    with db.connection(immediate=True) as cur:
        cur.execute("UPDATE bot_messages SET text = '   ' WHERE key = ?", ("deny.rate_limit",))

    assert bot_messages.get("deny.rate_limit") == bot_messages.SEED["deny.rate_limit"]
