"""Permission catalog and role evaluation."""

import pytest

from tuyabot.access import permissions, roles


def test_catalog_has_exactly_the_spec_keys():
    assert len(permissions.CATALOG) == 23
    assert len(set(permissions.CATALOG)) == 23
    assert "devices.control" in permissions.CATALOG
    assert "system.restore" in permissions.CATALOG
    assert "telegram_users.manage" in permissions.CATALOG
    assert "audit.view" in permissions.CATALOG


def test_subset_rule():
    assert permissions.is_subset({"devices.view"}, {"devices.view", "devices.control"})
    assert not permissions.is_subset({"roles.manage"}, {"devices.view"})
    assert permissions.is_subset(set(), {"devices.view"})


@pytest.mark.parametrize(
    "category, key",
    [
        ("Device", "devices.scan"),
        ("Log", "logs.cleanup"),
        ("Users Telegram", "telegram_users.view"),
        ("Sistem", "system.maintenance"),
    ],
)
def test_every_key_appears_in_its_category(category, key):
    assert key in permissions.CATEGORIES[category]


def test_effective_permissions_ignores_retired_keys():
    role = {"permissions": ["devices.view", "something.retired"]}
    assert roles.effective_permissions(role) == frozenset({"devices.view"})


def test_effective_permissions_of_missing_role_is_empty():
    assert roles.effective_permissions(None) == frozenset()


def test_protected_required_is_within_catalog():
    assert set(permissions.CATALOG) >= permissions.PROTECTED_REQUIRED
