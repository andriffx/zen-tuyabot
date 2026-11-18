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


def test_entrypoint_only_touches_the_data_dir():
    """With read_only:true, chown on /app/logs fails and the container loops.

    The app creates logs/ and backups/ inside DATA_DIR itself, so the entrypoint
    has no business with those paths. This caught a real restart loop:
    "chown: changing ownership of '/app/logs': Read-only file system".
    """
    script = (ROOT / "entrypoint.sh").read_text(encoding="utf-8")
    code = "\n".join(
        line for line in script.splitlines() if not line.lstrip().startswith("#")
    )
    assert "/app/logs" not in code
    assert "/app/backup" not in code
    # DATA_DIR must be the one directory it prepares.
    assert 'DATA="${DATA_DIR:-/app/data}"' in script


def test_entrypoint_survives_a_permission_denied():
    """Ownership is a convenience; failing it must not restart the container.

    Under `set -e`, a chown/chmod that returns EPERM aborted the script before
    the exec, so the container restarted forever with
    "chmod: changing permissions of '/app/data': Operation not permitted".
    """
    script = (ROOT / "entrypoint.sh").read_text(encoding="utf-8")
    for line in script.splitlines():
        stripped = line.strip()
        if stripped.startswith(("chown ", "chmod ")):
            assert "||" in stripped, f"no fallback for failure: {stripped}"


def test_dockerfile_does_not_create_unused_mount_points():
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    code = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
    assert "mkdir -p /app/logs" not in code
    assert "mkdir -p /app/data" in code


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


def test_source_packages_are_not_gitignored():
    """Runtime-data patterns must not swallow real source directories.

    A bare `backup/` or `logs/` in .gitignore also matches
    backend/src/tuyabot/backup/ and frontend/src/routes/(app)/{backup,logs}/.
    Those files stayed in the working tree because they were committed before
    the rule existed, so local runs passed while a fresh clone could not import
    tuyabot.backup at all. The patterns are anchored to the repo root now; this
    guard checks the result rather than the pattern.
    """
    import subprocess

    source_paths = [
        "backend/src/tuyabot/backup/service.py",
        "frontend/src/routes/(app)/backup/+page.svelte",
        "frontend/src/routes/(app)/logs/power/+page.svelte",
    ]
    for relative in source_paths:
        assert (REPO / relative).exists(), f"{relative} is missing from the working tree"
        result = subprocess.run(
            ["git", "check-ignore", "-q", relative],
            cwd=REPO,
            capture_output=True,
        )
        assert result.returncode != 0, f"{relative} is gitignored but must be committed"

    # Every one of them must also be tracked, which is what a clone receives.
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.splitlines()
    for relative in source_paths:
        assert relative in tracked, f"{relative} is not tracked by git"


def test_every_python_package_is_tracked():
    """No package directory may be absent from git: the app would not import."""
    import subprocess

    tracked = set(
        subprocess.run(
            ["git", "ls-files"],
            cwd=REPO,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.splitlines()
    )
    missing = []
    for init in sorted((ROOT / "src" / "tuyabot").rglob("__init__.py")):
        relative = init.relative_to(REPO).as_posix()
        if relative not in tracked:
            missing.append(relative)
    assert not missing, f"package files missing from git: {missing}"
    """The .env example files must not be swallowed by the .env ignore rule."""
    import subprocess

    for relative in ("backend/.env.example", "frontend/.env.example"):
        result = subprocess.run(
            ["git", "check-ignore", "-q", relative],
            cwd=REPO,
            capture_output=True,
        )
        assert result.returncode != 0, f"{relative} is ignored but should be tracked"


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
