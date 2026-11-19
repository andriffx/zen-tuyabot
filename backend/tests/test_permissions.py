"""Permission catalog and role evaluation.

The catalog holds bot permissions only. Device rights are not in it: they live
per role and per device in role_device_access, checked by access.bot_auth.
"""

import pytest

from tuyabot.access import permissions, roles


def test_catalog_is_the_four_bot_permissions():
    assert permissions.CATALOG == ("monitoring", "manage_users", "manage_devices", "view_logs")
    assert len(set(permissions.CATALOG)) == 4


@pytest.mark.parametrize("key", ["monitoring", "manage_users", "manage_devices", "view_logs"])
def test_every_key_appears_in_its_category(key):
    assert key in permissions.CATEGORIES["Bot"]


def test_no_retired_web_key_survives():
    for retired in ("devices.view", "devices.control", "users.manage", "system.restore"):
        assert retired not in permissions.CATALOG


def test_subset_rule():
    assert permissions.is_subset({"monitoring"}, {"monitoring", "manage_users"})
    assert not permissions.is_subset({"manage_users"}, {"monitoring"})
    assert permissions.is_subset(set(), {"monitoring"})


def test_effective_permissions_ignores_retired_keys():
    role = {"permissions": ["monitoring", "devices.view", "something.retired"]}
    assert roles.effective_permissions(role) == frozenset({"monitoring"})


def test_effective_permissions_of_missing_role_is_empty():
    assert roles.effective_permissions(None) == frozenset()


def test_protected_required_is_within_catalog():
    assert set(permissions.CATALOG) >= permissions.PROTECTED_REQUIRED
