import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent

sys.path.insert(0, str(TESTS.parent / "src"))
sys.path.insert(0, str(TESTS.parent))


@pytest.fixture()
def fresh_db(tmp_path):
    """Configure the DB layer against a temporary file and return its path."""
    from tuyabot.storage import db

    path = tmp_path / "tuyabot.db"
    db.configure(str(path))
    db.bump_generation()
    yield path
    db.close_all()
