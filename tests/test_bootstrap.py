"""Bootstrap on a bare machine: no .env, no data dir, no DB."""

import os
import stat

from tuyabot import bootstrap, config
from tuyabot.storage import db


def test_defaults_without_any_env(monkeypatch):
    for key in ("DATA_DIR", "API_HOST", "API_PORT", "TZ"):
        monkeypatch.delenv(key, raising=False)
    settings = config.load()
    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 8080
    assert settings.data_dir.name == "data"


def test_init_creates_everything_needed(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "fresh"))
    settings = config.load()

    assert bootstrap.init(settings) == 1

    assert db.ping() is True
    assert (settings.data_dir / "secret.key").exists()
    assert (settings.data_dir / "tuyabot.db").exists()
    assert (settings.data_dir / "backups").is_dir()


def test_secret_file_is_private_and_stable(tmp_path):
    settings = config.Settings(data_dir=tmp_path, api_host="127.0.0.1", api_port=8080, tz="UTC")
    first = bootstrap.init(settings)
    secret = bootstrap.secret()
    assert first == 1
    assert len(secret) == 32

    if os.name == "posix":
        mode = stat.S_IMODE(os.stat(tmp_path / "secret.key").st_mode)
        assert mode == 0o600

    bootstrap.init(settings)
    assert bootstrap.secret() == secret


def test_two_secrets_differ_between_machines(tmp_path):
    a = bootstrap.load_or_create_secret(tmp_path / "a")
    (tmp_path / "a").mkdir(exist_ok=True)
    b = bootstrap.load_or_create_secret(tmp_path / "b")
    assert a != b
