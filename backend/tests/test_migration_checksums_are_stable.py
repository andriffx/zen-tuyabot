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
    "0001_init.sql": "ed9193d094ce0c757dbcfe0ed47fddac71e31b7d01e9142b0ae44736a199f5e2",
    "0002_seed.sql": "2cf87f2084aee753f8a2212dcf4c419f15561d2af77742e7921d666e3fc90639",
    "0003_settings_seed.sql": "63bbc444d04159da9f1d0123084881f970344cdb85d9143247b1b4fa44669b77",
    "0004_setup_state.sql": "d2afb7a0ce1481ee86a014f978ce0e2e90e8a776fdd020313d4615c510bdc61f",
}


def test_no_shipped_migration_changed():
    changed = []
    for name, expected in SHIPPED.items():
        path = MIGRATIONS / name
        assert path.exists(), f"migrasi {name} hilang"
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            changed.append(name)

    assert changed == [], (
        f"migrasi yang sudah dirilis berubah: {changed}. "
        "Buat migrasi baru, jangan menyunting yang lama."
    )
