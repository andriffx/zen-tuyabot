"""Settings registry validation and atomic writes."""

import pytest

from tuyabot.settings import registry, service


def test_defaults_come_from_registry_when_db_empty(ready_db):
    assert service.get("monitoring.power_interval_minutes") == 5
    assert service.get_bool("telegram.enabled") is True


def test_patch_validates_type_and_range(ready_db):
    with pytest.raises(registry.ValidationError):
        service.patch({"monitoring.power_interval_minutes": 0}, actor={})
    with pytest.raises(registry.ValidationError):
        service.patch({"monitoring.power_interval_minutes": "5"}, actor={})
    with pytest.raises(registry.ValidationError):
        service.patch({"monitoring.power_interval_minutes": True}, actor={})


def test_unknown_key_rejected(ready_db):
    with pytest.raises(registry.ValidationError):
        service.patch({"tidak.ada": 1}, actor={})


def test_enum_choice_enforced(ready_db):
    with pytest.raises(registry.ValidationError):
        service.patch({"ui.theme": "neon"}, actor={})
    service.patch({"ui.theme": "dark"}, actor={})
    assert service.get("ui.theme") == "dark"


def test_bulk_patch_is_atomic(ready_db):
    with pytest.raises(registry.ValidationError):
        service.patch({"ui.title": "Baru", "housekeeping.interval_hours": -1}, actor={})
    assert service.get("ui.title") == "Tuya"


def test_read_only_settings_cannot_be_written(ready_db):
    with pytest.raises(registry.ValidationError):
        service.patch({"system.schema_version": 99}, actor={})


def test_patch_returns_changed_map_and_notifies(ready_db):
    seen: list[dict] = []
    service.subscribe(seen.append)

    changed = service.patch({"monitoring.power_interval_minutes": 10}, actor={"id": None})
    assert changed == {"monitoring.power_interval_minutes": {"old": 5, "new": 10}}
    assert seen == [{"monitoring.power_interval_minutes": 10}]


def test_patch_persists_across_cache_reset(ready_db):
    service.patch({"monitoring.power_interval_minutes": 15}, actor={})
    service.reset_cache()
    assert service.get("monitoring.power_interval_minutes") == 15


def test_secrets_are_never_returned(ready_db, monkeypatch):
    import json

    secret_def = registry.SettingDef(
        key="test.secret_value",
        type="secret",
        default="",
        category="ui",
        label="Rahasia uji",
        secret=True,
    )
    monkeypatch.setitem(registry.REGISTRY, secret_def.key, secret_def)
    monkeypatch.setattr(registry, "DEFS", (*registry.DEFS, secret_def))
    service.reset_cache()

    service.patch({"test.secret_value": "sangat-rahasia"}, actor={})

    rendered = json.dumps(service.all_values())
    assert "sangat-rahasia" not in rendered
    assert service.all_values()["test.secret_value"] == {"has_value": True}
    # Pembacaan internal tetap mendapat nilai asli.
    assert service.all_values(include_secrets=True)["test.secret_value"] == "sangat-rahasia"


def test_secret_settings_never_appear_in_schema_values(ready_db):
    import json

    rendered = json.dumps(service.all_values())
    assert "has_value" not in rendered  # no secret keys exist yet in the catalog
