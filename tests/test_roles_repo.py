"""Role repository against a real migrated SQLite file."""

import pytest

from tuyabot.storage import migrate
from tuyabot.storage.repos import roles


@pytest.fixture()
def ready(fresh_db):
    migrate.apply()
    return fresh_db


def test_seed_roles_exist_after_migration(ready):
    slugs = {role["slug"] for role in roles.list_all()}
    assert slugs == {"superadmin", "admin", "operator", "viewer"}


def test_superadmin_is_protected_and_has_all_permissions(ready):
    from tuyabot.access import permissions

    superadmin = roles.get_by_slug("superadmin")
    assert superadmin["is_protected"] == 1
    assert set(superadmin["permissions"]) == set(permissions.CATALOG)


def test_viewer_cannot_control_devices(ready):
    viewer = roles.get_by_slug("viewer")
    assert viewer["permissions"] == ["devices.view", "logs.view"]


def test_admin_lacks_role_management(ready):
    admin = roles.get_by_slug("admin")
    assert "roles.manage" not in admin["permissions"]
    assert "devices.manage" in admin["permissions"]


def test_create_update_delete(ready):
    role_id = roles.create("tamu", "Tamu", "hanya lihat", ["devices.view"])
    created = roles.get(role_id)
    assert created["slug"] == "tamu"
    assert created["permissions"] == ["devices.view"]

    roles.update(role_id, name="Tamu Rumah", permissions=["devices.view", "logs.view"])
    updated = roles.get(role_id)
    assert updated["name"] == "Tamu Rumah"
    assert updated["permissions"] == ["devices.view", "logs.view"]

    roles.delete(role_id)
    assert roles.get(role_id) is None


def test_user_count_aggregates_web_and_telegram(ready):
    from tuyabot.storage import db

    viewer = roles.get_by_slug("viewer")
    with db.connection(immediate=True) as cur:
        cur.execute(
            "INSERT INTO web_users (username, password_hash, role_id) VALUES ('a', 'x', ?)",
            (viewer["id"],),
        )
        cur.execute(
            "INSERT INTO telegram_users (telegram_id, role_id) VALUES (111, ?)",
            (viewer["id"],),
        )
    assert roles.get(viewer["id"])["user_count"] == 2


def test_roles_referencing_reports_every_table(ready):
    from tuyabot.storage import db

    operator = roles.get_by_slug("operator")
    with db.connection(immediate=True) as cur:
        cur.execute(
            "INSERT INTO devices (name, label, tuya_id, local_key, access_roles) VALUES (?,?,?,?,?)",
            ("air", "Air", "id1", "key1", f"[{operator['id']}]"),
        )
    refs = roles.roles_referencing(operator["id"])
    assert refs["devices"] == 1
    assert refs["web_users"] == 0
