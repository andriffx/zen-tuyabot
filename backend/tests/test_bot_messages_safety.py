"""A bad template must never take the bot down, and the preview must work."""

import pytest

from tuyabot.storage.repos import bot_messages


def test_a_malformed_template_is_rejected_on_save(ready_db):
    with pytest.raises(ValueError):
        bot_messages.set_text("deny.rate_limit", "hello {unclosed")


def test_a_positional_field_is_rejected_on_save(ready_db):
    with pytest.raises(ValueError):
        bot_messages.set_text("deny.rate_limit", "nilai {}")


def test_render_survives_a_template_that_was_stored_before_validation(ready_db):
    """Rows written by an older build must not raise on the reply path."""
    from tuyabot.storage import db

    with db.connection(immediate=True) as cur:
        cur.execute(
            "UPDATE bot_messages SET text = ? WHERE key = ?",
            ("nilai {unclosed", "deny.rate_limit"),
        )

    assert bot_messages.render("deny.rate_limit") == "nilai {unclosed"


def test_formatted_placeholders_render_in_the_preview(ready_db):
    """The seed uses {power:.1f}; a string sample must still render."""
    assert "12.5" in bot_messages.render("notify.watchdog_off_idle", power=12.5)
