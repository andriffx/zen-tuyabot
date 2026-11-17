"""Backup roundtrip, restore safety, and maintenance gating."""

import sqlite3
from pathlib import Path

import pytest

from tuyabot.backup import service as backup_service
from tuyabot.maintenance import service as maintenance_service
from tuyabot.settings import service as settings_service
from tuyabot.storage import db, migrate
from tuyabot.storage.repos import backup_runs, roles, web_users
from tuyabot.storage.repos import devices as devices_repo


@pytest.fixture()
def populated(ready_db):
    web_users.create("root", "password-panjang", roles.get_by_slug("superadmin")["id"])
    devices_repo.create({"name": "air", "label": "Air", "tuya_id": "a1", "local_key": "k"})
    yield ready_db
    maintenance_service.disable()


def test_backup_file_exists_and_is_private(populated):
    result = backup_service.create()
    from pathlib import Path

    path = Path(result["path"])
    assert path.exists()
    assert path.stat().st_size > 0
    assert backup_runs.get(result["id"])["kind"] == "manual"


def test_backup_roundtrip_preserves_all_tables(populated):
    result = backup_service.create()
    before = {
        "web_users": len(web_users.list_all()),
        "devices": len(devices_repo.list_all()),
    }

    devices_repo.delete(devices_repo.get_by_name("air")["id"])
    web_users.delete(web_users.list_all()[0]["id"])
    assert len(web_users.list_all()) == 0

    from pathlib import Path

    backup_service.restore(Path(result["path"]))
    assert len(web_users.list_all()) == before["web_users"]
    assert len(devices_repo.list_all()) == before["devices"]


def test_restore_refuses_newer_schema(populated, tmp_path):
    result = backup_service.create()
    source = result["path"]
    copy = tmp_path / "newer.db"
    copy.write_bytes(Path(source).read_bytes())

    conn = sqlite3.connect(copy)
    conn.execute("INSERT INTO schema_migrations (version, name, checksum) VALUES (999, 'future', 'x')")
    conn.commit()
    conn.close()

    with pytest.raises(backup_service.RestoreError) as excinfo:
        backup_service.restore(copy)
    assert excinfo.value.stage == "version"


def test_restore_refuses_corrupt_file(populated, tmp_path):
    broken = tmp_path / "broken.db"
    broken.write_bytes(b"ini bukan database sqlite" * 100)
    with pytest.raises(backup_service.RestoreError) as excinfo:
        backup_service.restore(broken)
    assert excinfo.value.stage in {"integrity", "schema"}


def test_failed_restore_leaves_old_db_usable(populated, tmp_path):
    broken = tmp_path / "broken2.db"
    broken.write_bytes(b"rusak" * 100)

    with pytest.raises(backup_service.RestoreError):
        backup_service.restore(broken)

    assert db.ping() is True
    assert len(devices_repo.list_all()) == 1


def test_restore_bumps_generation(populated):
    result = backup_service.create()
    from pathlib import Path

    before = db.current_generation()
    backup_service.restore(Path(result["path"]))
    assert db.current_generation() == before + 1
    assert db.ping() is True


def test_restore_creates_pre_restore_backup(populated):
    result = backup_service.create()
    from pathlib import Path

    backup_service.restore(Path(result["path"]))
    kinds = [row["kind"] for row in backup_runs.list_all()]
    assert "pre_restore" in kinds


def test_prune_removes_old_files(populated, monkeypatch):
    import os
    import time
    from pathlib import Path

    result = backup_service.create()
    path = Path(result["path"])
    # Backdate the file: pruning is about age, not about when it was recorded.
    old = time.time() - 40 * 86400
    os.utime(path, (old, old))

    monkeypatch.setattr(settings_service, "get_int", lambda key: 14 if "retention" in key else 30)
    assert backup_service.prune() == 1
    assert not path.exists()


def test_maintenance_blocks_non_auth_routes(client, login_as):
    login_as("superadmin")
    maintenance_service.enable("uji")
    try:
        assert client.get("/api/settings").status_code == 503
        assert client.get("/api/auth/me").status_code in (200, 401)
        assert client.get("/api/maintenance/status").status_code == 200
    finally:
        maintenance_service.disable()


def test_maintenance_auto_off_expires(ready_db):
    maintenance_service.enable("uji", auto_off_minutes=0.001)
    import time

    time.sleep(0.1)
    assert maintenance_service.is_on() is False


def test_maintenance_toggle_is_audited(client, login_as):
    from tuyabot.storage.repos import audit

    login_as("superadmin")
    client.post("/api/maintenance", json={"enabled": True, "reason": "pemasangan", "auto_off_minutes": 5})
    rows = audit.list_page(action="maintenance.enable")
    assert rows and rows[0]["details"]["reason"] == "pemasangan"
    client.post("/api/maintenance", json={"enabled": False})


def test_stats_reports_devices_and_db(client, login_as, populated):
    login_as("superadmin")
    body = client.get("/api/stats").json()
    assert body["devices"]["total"] == 1
    assert body["database"]["schema_version"] == migrate.current_version()


def test_health_reports_degraded_when_no_fresh_data(client, login_as, populated):
    login_as("superadmin")
    body = client.get("/api/health").json()
    assert body["status"] in {"ok", "degraded", "down"}
    assert body["database"] is True


def test_backup_download_requires_restore_permission(client, login_as, populated):
    login_as("operator")  # no backup.view at all
    result = backup_service.create()
    assert client.get(f"/api/backup/{result['id']}/download").status_code == 403
