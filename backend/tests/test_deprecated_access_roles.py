"""devices.access_roles is kept only for the migration backfill.

It must never authorize anything again: the source of truth is role_device_access.
"""

from tuyabot.access import bot_auth
from tuyabot.devices import registry
from tuyabot.storage.repos import devices as devices_repo
from tuyabot.storage.repos import roles
from tuyabot.web.deps import Principal


def test_access_roles_is_not_an_authorization_source(ready_db):
    role_id = roles.create("uji", "Uji", None, [])
    device_id = devices_repo.create(
        {
            "name": "pompa",
            "label": "Pompa",
            "tuya_id": "t1",
            "local_key": "k",
            "access_roles": [role_id],
        }
    )

    assert bot_auth.can_device(role_id, device_id, "on") is False

    principal = Principal("web", None, "tester", role_id, "uji", frozenset())
    assert registry.can_view(principal, registry.get(device_id)) is False


def test_the_column_still_exists_for_the_backfill(ready_db):
    """Insurance against someone dropping it in this change."""
    from tuyabot.storage import db

    with db.connection() as cur:
        cur.execute("SELECT access_roles FROM devices LIMIT 1")
        cur.fetchall()  # raises if the column is gone
