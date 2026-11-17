import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent

sys.path.insert(0, str(TESTS.parent / "src"))
sys.path.insert(0, str(TESTS.parent))


@pytest.fixture()
def fresh_db(tmp_path):
    """Configure the DB layer against a temporary file and return its path."""
    from tuyabot.settings import service as settings_service
    from tuyabot.storage import db

    path = tmp_path / "tuyabot.db"
    db.configure(str(path))
    db.bump_generation()
    settings_service.reset_cache()
    yield path
    settings_service.reset_cache()
    db.close_all()


@pytest.fixture()
def ready_db(fresh_db):
    """A migrated database with seed rows."""
    from tuyabot import bootstrap
    from tuyabot.storage import migrate
    from tuyabot.storage.repos import app_state

    migrate.apply()
    bootstrap._secret = b"test-secret-32-bytes-long-padding!"
    # Most API tests are about endpoints, not the wizard: mark setup complete.
    app_state.set("setup_complete", True)
    return fresh_db


class FakeAuth:
    """Lets a test authenticate as any role without running the session code."""

    def __init__(self) -> None:
        self.principal = None

    def install(self, monkeypatch, role_slug: str = "superadmin") -> None:
        from tuyabot.access import roles as roles_module
        from tuyabot.storage.repos import roles as roles_repo
        from tuyabot.web import auth_impl
        from tuyabot.web.deps import Principal

        stored = roles_repo.get_by_slug(role_slug)
        assert stored is not None, f"role {role_slug} tidak ada"
        self.principal = Principal(
            actor_kind="web",
            actor_id=1,
            label="tester",
            role_id=stored["id"],
            role_slug=stored["slug"],
            permissions=roles_module.effective_permissions(stored),
            session_token="test-session",
        )
        monkeypatch.setattr(
            auth_impl, "resolve_session", lambda token, request: self.principal
        )
        return self.principal


@pytest.fixture()
def csrf_value(ready_db):
    """CSRF token bound to the fake session used by the test client."""
    from tuyabot.access import sessions

    return sessions.csrf_token("test-session")


@pytest.fixture()
def client(ready_db, csrf_value):
    """HTTP client whose cookie always resolves to the fake principal.

    It carries a valid CSRF pair by default so mutating routes can be tested;
    tests that exercise CSRF behaviour build their own client.
    """
    from fastapi.testclient import TestClient

    from tuyabot.web.app import create_app

    return TestClient(
        create_app(),
        cookies={"tuyabot_session": "test-session", "csrf_token": csrf_value},
        headers={"X-CSRF-Token": csrf_value},
    )


@pytest.fixture()
def login_as(monkeypatch, ready_db):
    """Fixture that installs a principal for a given role slug."""
    fake = FakeAuth()
    return lambda slug="superadmin": fake.install(monkeypatch, slug)
