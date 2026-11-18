"""Deploy configuration guards.

Each assertion encodes a choice that is easy to undo by accident and expensive
to discover in production (open bind address, writable root filesystem,
secrets in compose).
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent


def _compose() -> dict:
    """The full-stack compose lives at the repo root: the frontend image needs
    the repository root as its build context (it copies frontend/ and the lock)."""
    return yaml.safe_load((REPO / "docker-compose.yml").read_text(encoding="utf-8"))


def test_compose_has_no_hardcoded_secrets():
    text = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
    for marker in ("TELEGRAM_BOT_TOKEN=", "DASHBOARD_API_KEY=", "password"):
        assert marker not in text


def test_compose_keeps_data_writable_volumes():
    """One volume: the app writes the database, secret, logs/ and backups/ inside
    DATA_DIR. Mounting ./logs or ./backup separately only created empty dirs, so
    a backup made from the UI appeared to vanish."""
    service = _compose()["services"]["backend"]
    assert service["volumes"] == ["./backend/data:/app/data"]


def test_compose_exposes_only_the_web_container_on_loopback():
    """The backend must not be reachable from outside the Docker network, and the
    web port must bind the host loopback so the operator's nginx is the only door."""
    services = _compose()["services"]
    assert "ports" not in services["backend"]
    assert services["web"]["ports"] == ["127.0.0.1:8081:80"]


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
    assert keys == {"DATA_DIR", "API_HOST", "API_PORT", "TZ", "FORWARDED_ALLOW_IPS"}


def test_forwarded_allow_ips_defaults_to_loopback(monkeypatch):
    """Trusting forwarded headers from arbitrary peers would let anyone spoof
    their IP in the audit log and bypass the per-IP login limiter."""
    from tuyabot import config

    monkeypatch.delenv("FORWARDED_ALLOW_IPS", raising=False)
    assert config.load().forwarded_allow_ips == "127.0.0.1"

    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "10.0.0.5,127.0.0.1")
    assert config.load().forwarded_allow_ips == "10.0.0.5,127.0.0.1"


def test_readme_documents_backup_and_restore():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Backup, restore, pindah mesin" in text
    assert "secret.key" in text


def test_ci_workflow_lives_at_repo_root():
    """The monorepo's CI is at .github/ and runs inside backend/."""
    root = ROOT.parent
    workflow = root / ".github" / "workflows" / "backend.yml"
    assert workflow.exists()
    text = workflow.read_text(encoding="utf-8")
    assert "ruff check ." in text
    assert "pytest -q" in text
    assert "working-directory: backend" in text


def test_private_runtime_files_are_gitignored():
    """The database, its WAL and secret.key must never reach a public remote.

    Checked with real paths: `git check-ignore` says nothing (exit 0 means "not
    ignored") for a path that does not exist, so probing names that are absent
    would make this guard pass while ignoring nothing.
    """
    import subprocess

    samples = [
        "backend/data/tuyabot.db",
        "backend/data/tuyabot.db-wal",
        "backend/data/secret.key",
        "backend/.env",
        "frontend/.env",
    ]
    for relative in samples:
        target = REPO / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        existed = target.exists()
        if not existed:
            target.write_text("probe", encoding="utf-8")
        try:
            result = subprocess.run(
                ["git", "check-ignore", "-q", relative],
                cwd=REPO,
                capture_output=True,
            )
        finally:
            if not existed:
                target.unlink()
        assert result.returncode == 0, f"{relative} is NOT gitignored"


def test_env_examples_stay_tracked():
    """The .env example files must not be swallowed by the .env ignore rule."""
    import subprocess

    for relative in ("backend/.env.example", "frontend/.env.example"):
        result = subprocess.run(
            ["git", "check-ignore", "-q", relative],
            cwd=REPO,
            capture_output=True,
        )
        assert result.returncode != 0, f"{relative} is ignored but should be tracked"
