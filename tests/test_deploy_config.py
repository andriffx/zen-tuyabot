"""Deploy configuration guards.

Each assertion encodes a choice that is easy to undo by accident and expensive
to discover in production (open bind address, writable root filesystem,
secrets in compose).
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _compose() -> dict:
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))


def test_compose_has_no_hardcoded_secrets():
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for marker in ("TELEGRAM_BOT_TOKEN=", "DASHBOARD_API_KEY=", "password"):
        assert marker not in text


def test_compose_keeps_data_writable_volumes():
    service = _compose()["services"]["backend"]
    volumes = service["volumes"]
    assert "./data:/app/data" in volumes
    assert "./backup:/app/backup" in volumes


def test_compose_hardens_the_container():
    service = _compose()["services"]["backend"]
    assert service["read_only"] is True
    assert "ALL" in service["cap_drop"]
    assert "no-new-privileges:true" in service["security_opt"]
    assert "/tmp" in service["tmpfs"]


def test_dockerfile_runs_non_root_and_has_healthcheck():
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "HEALTHCHECK" in text
    assert "/healthz" in text
    assert "setpriv" in text  # entrypoint drops privileges
    assert "PYTHONPATH=/app/src" in text


def test_entrypoint_execs_python_so_signals_arrive():
    text = (ROOT / "entrypoint.sh").read_text(encoding="utf-8")
    assert "exec setpriv" in text
    assert "python -m tuyabot.main" in text


def test_env_example_lists_only_bootstrap_keys():
    keys = set()
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            keys.add(line.split("=", 1)[0])
    assert keys == {"DATA_DIR", "API_HOST", "API_PORT", "TZ"}


def test_ci_runs_lint_and_tests():
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "ruff check ." in text
    assert "pytest -q" in text


def test_readme_documents_backup_and_restore():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Backup, restore, pindah mesin" in text
    assert "secret.key" in text
