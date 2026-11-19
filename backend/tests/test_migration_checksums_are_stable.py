"""Migrations must stop changing once they can have been applied.

The runner records a SHA-256 per file and refuses to start if it differs. A
migration edited after release therefore bricks every database that ran it,
with no way forward except editing schema_migrations by hand. This test pins
that rule so a later edit to an applied file is a deliberate, visible act.
"""

import hashlib
import pathlib

MIGRATIONS = pathlib.Path(__file__).resolve().parent.parent / "src/tuyabot/storage/migrations"

# Checksums of migrations that have shipped. Adding a NEW migration is fine;
# editing an entry below is only allowed together with a deliberate decision to
# break every existing database, which is exactly what this test protects.
SHIPPED: dict[str, str] = {
    "0001_init.sql": "19f6861ad295219cf25642ad5db6f5d8ef0a16f1d057e475e39823a5a375ca2d",
    "0002_seed.sql": "966f81db682c164d0fd4c57b822f4b4c4fc9bc99f455c4995c8380f69eb5d547",
    "0003_settings_seed.sql": "f2e8b84d48c15bcdfe8c900681ce31d3f02b911786b0a161ed17a799fda6eb80",
    "0004_setup_state.sql": "855b6030f412a79446fb8f748fc812e080711cedeb4ef0c637a5e3ec38d880f0",
}


def test_no_shipped_migration_changed():
    changed = []
    for name, expected in SHIPPED.items():
        path = MIGRATIONS / name
        assert path.exists(), f"migrasi {name} hilang"
        # Normalised, the same way the runner hashes: CRLF and LF must agree.
        # Normalised the same way the runner hashes: CRLF and LF must agree.
        raw = path.read_bytes().replace(b"\r\n", b"\n")
        actual = hashlib.sha256(raw).hexdigest()
        if actual != expected:
            changed.append(name)

    assert changed == [], (
        f"migrasi yang sudah dirilis berubah: {changed}. "
        "Buat migrasi baru, jangan menyunting yang lama."
    )
