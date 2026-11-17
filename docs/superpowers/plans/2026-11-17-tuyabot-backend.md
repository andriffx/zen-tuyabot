# Tuya Bot Backend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend of a self-hosted Tuya smart-home controller — FastAPI REST API, dynamic Telegram bots, SQLite storage, and a scheduler — in which all operational configuration lives in the database and is managed from a dashboard.

**Architecture:** One Python process runs uvicorn, zero-or-more Telegram `Application`s, and one interval scheduler. All shared state is SQLite behind a thread-local connection layer with WAL and a generation counter for restore. Configuration is a typed registry in code, values in `app_settings`, validated and applied live. Authorization is a permission catalog in code with roles stored in the DB.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, python-telegram-bot 22.x, tinytuya 1.21+, stdlib `sqlite3`, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-11-17-tuyabot-rebuild-design.md`

## Global Constraints

- Backend only in this plan. Frontend (`../tuyabot-fe`) is a later, separate plan. No endpoint may assume an SPA exists.
- Fresh build: do not copy or import code from `referensi/`. Read it for patterns only.
- `.env` keys are exactly `DATA_DIR`, `API_HOST`, `API_PORT`, `TZ`, all optional. Any other configuration is a DB row.
- No new runtime dependency beyond: `fastapi`, `uvicorn[standard]`, `python-telegram-bot==22.8`, `tinytuya`, `python-dotenv`. Everything else from the stdlib (hashing, HMAC, base64, sqlite3, json).
- Never `import sqlite3` in a module under `src/tuyabot/web/` or `src/tuyabot/telegram/`.
- Every route handler is `async def` and touches the DB only through `run_db(...)`.
- Timestamps are TEXT `YYYY-MM-DD HH:MM:SS` in local time via `datetime('now','localtime')`.
- Indonesian user-facing strings; English identifiers, comments, and commit messages.
- Secrets (bot token, local key, password hash) are never returned by any endpoint and never logged.
- `ruff check .` clean and `pytest -q` green at the end of every task.

## Review Focus

Failure modes the spec implies that are easy to get wrong; each has a test in the task named.

1. **First run on an empty machine** — no `.env`, no `data/` dir, no DB. The process must create `DATA_DIR`, create the schema, and serve `/api/setup/status` and `/healthz`; everything else returns `409 setup_required`. (Task 1 + Task 5)
2. **Concurrent writers** — scheduler, API, and a Telegram bot writing at the same moment. No lost rows, no unhandled `database is locked`, no `sqlite3` call on the event loop. (Task 1)
3. **Session and CSRF edge cases** — expired session, revoked session, `X-CSRF-Token` missing/mismatched/stale-after-password-change. Each must give a specific status, not a 500. (Task 4)
4. **Restoring a bad backup** — corrupt file, newer schema version, failure halfway through the swap. The old DB must remain usable and maintenance must stay on. (Task 8)
5. **Unreachable device / wrong local key** — status and control endpoints must return `success:false` inside the timeout, never hang the request or 500. (Task 6)

---

### Task 1: Skeleton, bootstrap, SQLite layer, migrations

**Files:**
- Create: `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, `.gitignore`, `.dockerignore`, `.env.example`, `README.md`
- Create: `src/tuyabot/__init__.py`, `src/tuyabot/config.py`, `src/tuyabot/bootstrap.py`, `src/tuyabot/main.py`
- Create: `src/tuyabot/storage/__init__.py`, `src/tuyabot/storage/db.py`, `src/tuyabot/storage/migrate.py`
- Create: `src/tuyabot/storage/migrations/0001_init.sql`
- Create: `src/tuyabot/infra/__init__.py`, `src/tuyabot/infra/asyncdb.py`
- Create: `src/tuyabot/web/__init__.py`, `src/tuyabot/web/app.py`
- Test: `tests/conftest.py`, `tests/test_db.py`, `tests/test_migrate.py`, `tests/test_bootstrap.py`, `tests/test_no_sync_db.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `tuyabot.config.Settings`: frozen dataclass with `data_dir: Path`, `api_host: str`, `api_port: int`, `tz: str`; `config.load() -> Settings`.
  - `tuyabot.storage.db.configure(path: str, busy_timeout_ms: int = 5000) -> None`; `connection(immediate: bool = False)` context manager yielding `sqlite3.Cursor`; `close_all() -> None`; `bump_generation() -> None`; `current_generation() -> int`; `ping() -> bool`.
  - `tuyabot.storage.migrate.apply(data_dir: Path, db_path: str) -> int` (returns resulting schema version; raises `MigrationError` on checksum mismatch or newer DB).
  - `tuyabot.infra.asyncdb.run_db(fn, *args, timeout=15.0, **kwargs)`; `shutdown() -> None`.
  - `tuyabot.web.app.create_app() -> FastAPI` exposing `GET /healthz` → `{"status": "ok"}`.
  - `tuyabot.bootstrap.init(settings) -> None` (mkdirs, secret key, configure db, migrate).

- [ ] **Step 1: Initialize the repo and project files**

```bash
cd "D:/Datas/MyData/Project Repo/tuyabot-be"
git init
```

`requirements.txt`:
```
fastapi==0.115.*
uvicorn[standard]==0.34.*
python-telegram-bot==22.8
tinytuya==1.21.1
python-dotenv==1.0.*
```

`requirements-dev.txt` adds `-r requirements.txt`, `pytest>=8`, `pytest-asyncio>=0.24`, `httpx>=0.28`, `ruff>=0.8`, `pyyaml>=6`.

`pyproject.toml` gets `[tool.pytest.ini_options] pythonpath = ["src"]`, `testpaths = ["tests"]`, `asyncio_mode = "auto"`, and a ruff config with `line-length = 120`, `target-version = "py311"`.

`migrations/0001_init.sql` creates `schema_migrations`, `app_settings`, `roles`, `web_users`, `web_sessions`, `telegram_users`, `telegram_bots`, `api_keys`, `devices`, `device_settings`, `device_activity_logs`, `device_power_logs`, `app_error_logs`, `backup_runs`, `audit_logs`, `app_state` exactly as in spec §8.2, plus the indexes listed there. No seed rows in this file — seeding is Task 2's job so the SQL stays schema-only.

- [ ] **Step 2: Write the failing tests**

`tests/test_db.py`:
```python
def test_connection_reopens_after_generation_bump(tmp_path):
    db.configure(str(tmp_path / "t.db"))
    with db.connection() as cur:
        cur.execute("CREATE TABLE t (v INTEGER)")
        cur.execute("INSERT INTO t VALUES (1)")
    db.bump_generation()
    with db.connection() as cur:
        cur.execute("SELECT count(*) FROM t")
        assert cur.fetchone()[0] == 1   # data visible through the reopened connection

def test_concurrent_writers_keep_all_rows(tmp_path):
    # 4 threads x 50 inserts through db.connection(); total must be 200, no exception
```

`tests/test_migrate.py`:
```python
def test_fresh_db_applies_all(tmp_path): ...          # apply() returns 1, schema_migrations has 1 row
def test_edited_migration_fails(tmp_path): ...        # apply, tamper checksum, apply again -> MigrationError
def test_newer_db_refused(tmp_path): ...              # row with version 99 -> MigrationError
```

`tests/test_bootstrap.py`:
```python
def test_no_env_no_data_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("DATA_DIR", raising=False)
    s = config.load()
    assert s.data_dir  # non-empty default
    bootstrap.init(s)
    assert db.ping()
    assert (s.data_dir / "secret.key").exists()
```

`tests/test_no_sync_db.py`:
```python
def test_web_and_telegram_modules_do_not_import_sqlite3():
    # walk src/tuyabot/web and src/tuyabot/telegram, parse AST,
    # assert no `import sqlite3` / `from sqlite3 import`
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `pytest -q`
Expected: collection errors (`ModuleNotFoundError: tuyabot.storage.db`).

- [ ] **Step 4: Implement the modules**

`storage/db.py` — module-level `_path`, `_busy_timeout_ms`, `_generation: int`, `threading.local()` holding `(conn, generation)`. On every `connection()` entry, if the thread-local generation differs from `_generation`, close and reopen. Apply the four pragmas on open. `connection()` commits on clean exit and rolls back on exception. Do **not** pass `check_same_thread=False`.

`storage/migrate.py` — read `migrations/*.sql` sorted by filename; for each not yet applied, `executescript` inside a transaction and insert `(version, name, checksum)` where checksum is `sha256(file_bytes).hexdigest()`. Verify existing rows' checksums against files before applying anything. If `max(applied.version) > max(file.version)` raise `MigrationError`.

`infra/asyncdb.py` — `ThreadPoolExecutor(max_workers=4, thread_name_prefix="db")`, `run_db` awaits `asyncio.wait_for(loop.run_in_executor(...), timeout)`.

`bootstrap.py` — `data_dir.mkdir(parents=True, exist_ok=True)` with mode `0o700`; create `secret.key` (32 random bytes, `os.open` with `0o600`) if absent; `db.configure(str(data_dir / "tuyabot.db"), ...)`; `migrate.apply(...)`.

`main.py` — `asyncio.run(main())` that boots config → bootstrap → uvicorn on `api_host:api_port`. Scheduler and bots are added in later tasks.

- [ ] **Step 5: Run tests and ruff, then commit**

```bash
pytest -q && ruff check .
git add -A && git commit -m "feat: project skeleton, sqlite layer, migration runner"
```

---

### Task 2: Permission catalog, roles, audit log

**Files:**
- Create: `src/tuyabot/access/__init__.py`, `src/tuyabot/access/permissions.py`, `src/tuyabot/access/roles.py`
- Create: `src/tuyabot/storage/repos/__init__.py`, `src/tuyabot/storage/repos/roles.py`, `src/tuyabot/storage/repos/audit.py`
- Create: `src/tuyabot/storage/migrations/0002_seed.sql`
- Create: `src/tuyabot/web/deps.py`
- Test: `tests/test_permissions.py`, `tests/test_roles_repo.py`, `tests/test_audit.py`

**Interfaces:**
- Consumes: `db.connection`, `migrate.apply`.
- Produces:
  - `permissions.CATALOG: tuple[str, ...]` (ordered; exactly the 23 keys of spec §8.4), `permissions.CATEGORIES: dict[str, tuple[str, ...]]`, `permissions.is_subset(sub: Iterable[str], sup: Collection[str]) -> bool`.
  - `roles_repo.list_all() -> list[dict]` with keys `id, slug, name, description, permissions, is_protected, user_count`; `get(id) -> dict | None`; `get_by_slug(slug)`; `create(slug, name, description, permissions) -> int`; `update(id, **fields) -> None`; `delete(id) -> None`.
  - `audit.write(actor_kind, actor_id, actor_label, action, target_kind=None, target_id=None, result="ok", ip=None, details=None, request_id=None) -> None`.
  - `access.roles.effective_permissions(role: dict) -> frozenset[str]` (returns the stored list intersected with the catalog).

- [ ] **Step 1: Write the failing tests**

```python
def test_catalog_has_exactly_the_spec_keys():
    assert len(permissions.CATALOG) == 23
    assert "devices.control" in permissions.CATALOG
    assert "system.restore" in permissions.CATALOG

def test_subset_rule():
    assert permissions.is_subset({"devices.view"}, {"devices.view", "devices.control"})
    assert not permissions.is_subset({"roles.manage"}, {"devices.view"})

def test_seed_roles_exist_after_migration():
    slugs = {r["slug"] for r in roles_repo.list_all()}
    assert slugs == {"superadmin", "admin", "operator", "viewer"}
    assert roles_repo.get_by_slug("superadmin")["is_protected"] == 1

def test_audit_row_written_with_details_json():
    audit.write("system", None, "startup", "system.start", details={"schema": 2})
    row = ...
    assert row["details"] == {"schema": 2}
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_permissions.py tests/test_roles_repo.py tests/test_audit.py -q`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

`permissions.py` — literal `CATEGORIES` dict; `CATALOG = tuple(k for keys in CATEGORIES.values() for k in keys)`; `is_subset` uses set comparison.

`0002_seed.sql` — insert the four roles with `is_system=1`, `is_protected=1` only for `superadmin`, permissions as JSON arrays:
superadmin = all 23; admin = everything except `roles.manage`, `users.manage`, `telegram_users.manage`, `system.restore`, `system.maintenance`; operator = `devices.view`, `devices.control`, `logs.view`; viewer = `devices.view`, `logs.view`. Use `INSERT OR IGNORE`.

`roles_repo` — plain functions taking a cursor from `db.connection()`, `json.loads` for the permissions column, `user_count` from a `UNION` of `web_users` and `telegram_users`.

`audit.py` — `json.dumps(details)` into the `details` column; never raises (catches and logs to `app_error_logs`).

- [ ] **Step 4: Verify and commit**

```bash
pytest -q && ruff check .
git add -A && git commit -m "feat: permission catalog, seeded roles, audit log"
```

---

### Task 3: Settings registry, service, and API

**Files:**
- Create: `src/tuyabot/settings/__init__.py`, `src/tuyabot/settings/registry.py`, `src/tuyabot/settings/service.py`
- Create: `src/tuyabot/storage/migrations/0003_settings_seed.sql`
- Create: `src/tuyabot/web/routes/__init__.py`, `src/tuyabot/web/routes/settings.py`
- Modify: `src/tuyabot/web/app.py`
- Test: `tests/test_settings.py`, `tests/test_api_settings.py`

**Interfaces:**
- Consumes: `permissions`, `db.connection`, `run_db`.
- Produces:
  - `registry.SettingDef` (frozen dataclass: `key, type, default, category, label, help, apply, secret, edit_permission, minimum, maximum, choices`).
  - `registry.REGISTRY: dict[str, SettingDef]`, `registry.schema() -> list[dict]`, `registry.validate(key, value) -> Any` (raises `ValidationError`).
  - `service.get(key, default=None)`, `service.get_bool/get_int/get_float`, `service.all(include_secrets=False) -> dict`, `service.patch(items: dict, actor: dict) -> dict` (atomic; returns old→new), `service.subscribe(cb)`.
  - Routes: `GET /api/settings` → `{"values": {...}, "schema": [...]}`, `PATCH /api/settings`.

- [ ] **Step 1: Write the failing tests**

```python
def test_defaults_come_from_registry_when_db_empty():
    assert settings_service.get("monitoring.power_interval_minutes") == 5

def test_patch_validates_type_and_range():
    with pytest.raises(ValidationError):
        settings_service.patch({"monitoring.power_interval_minutes": 0}, actor={})
    with pytest.raises(ValidationError):
        settings_service.patch({"monitoring.power_interval_minutes": "5"}, actor={})

def test_bulk_patch_is_atomic():
    with pytest.raises(ValidationError):
        settings_service.patch({"ui.title": "X", "housekeeping.interval_hours": -1}, actor={})
    assert settings_service.get("ui.title") == "Tuya"   # unchanged

def test_secret_values_are_masked():
    out = client.get("/api/settings").json()
    assert out["values"]["telegram.bot_token"] == {"has_value": True} if ... else True
    assert "***" not in json.dumps(out["values"])
```

The secret test asserts no raw secret and no partial secret appears; use a setting of type `secret` seeded for the test.

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_settings.py tests/test_api_settings.py -q`

- [ ] **Step 3: Implement**

`registry.py` holds every key from spec §8.5 (`telegram.enabled`, `monitoring.*`, `housekeeping.*`, `backup.*`, `tuya.*`, `security.*`, `maintenance.*`, `ui.*`, `system.*` read-only) with type, range/choices, `apply`, and `edit_permission`. `validate` coerces nothing: a string where an int is declared is an error, not a parse.

`0003_settings_seed.sql` — `INSERT OR IGNORE` every non-`system` key with its default JSON value.

`service.py` — in-memory cache dict guarded by a lock; `patch` validates the whole item set first, then writes all rows in one `BEGIN IMMEDIATE` transaction, then updates the cache and calls subscribers with the changed map. Read-only `system.*` keys are rejected for writing.

`web/routes/settings.py` — `GET` requires `settings.view`, `PATCH` requires `settings.edit`; `PATCH` body is `{"values": {...}}`; on `ValidationError` return `422 {"errors": [{"key": ..., "message": ...}]}`.

- [ ] **Step 4: Verify and commit**

```bash
pytest -q && ruff check .
git add -A && git commit -m "feat: typed settings registry, atomic patch, settings API"
```

---

### Task 4: Passwords, sessions, CSRF, login, web users, API keys

**Files:**
- Create: `src/tuyabot/access/passwords.py`, `src/tuyabot/access/sessions.py`, `src/tuyabot/access/principal.py`, `src/tuyabot/access/rate_limit.py`
- Create: `src/tuyabot/storage/repos/web_users.py`, `src/tuyabot/storage/repos/api_keys.py`, `src/tuyabot/storage/repos/sessions.py`
- Create: `src/tuyabot/web/routes/auth.py`, `src/tuyabot/web/routes/web_users.py`, `src/tuyabot/web/routes/api_keys.py`
- Create: `src/tuyabot/web/security.py` (middleware: request id, headers, origin check)
- Modify: `src/tuyabot/web/app.py`, `src/tuyabot/web/deps.py`
- Test: `tests/test_passwords.py`, `tests/test_sessions.py`, `tests/test_csrf.py`, `tests/test_api_auth.py`, `tests/test_api_web_users.py`

**Interfaces:**
- Consumes: `permissions`, `roles_repo`, `audit`, `db.connection`.
- Produces:
  - `passwords.hash_password(password: str) -> str`, `passwords.verify_password(password: str, stored: str) -> bool`.
  - `sessions.create(user_id, ip, user_agent, ttl_hours, idle_minutes) -> str`; `sessions.resolve(token: str) -> principal.Principal | None`; `sessions.revoke(token)`; `sessions.revoke_all(user_id, except_token=None) -> int`; `sessions.list_for(user_id) -> list[dict]`; `sessions.csrf_token(session_token: str) -> str`.
  - `principal.Principal` dataclass: `actor_kind, actor_id, label, role_id, role_slug, permissions: frozenset[str], session_token: str | None`.
  - Dependencies: `deps.current_principal(...) -> Principal` (cookie session or `X-API-Key`), `deps.require_csrf(...)`, `deps.require(*perms)` (returns a FastAPI dependency that raises `403` and writes an audit row with `result="denied"`).
  - Routes: `GET /api/auth/csrf`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`, `POST /api/auth/password`, `GET|DELETE /api/auth/sessions[/{id}]`, `GET|POST /api/web-users`, `PATCH|DELETE /api/web-users/{id}`, `GET|POST|DELETE /api/api-keys`.

- [ ] **Step 1: Write the failing tests**

```python
def test_password_roundtrip_and_wrong_password():
    h = passwords.hash_password("s3cret")
    assert h.startswith("scrypt$")
    assert passwords.verify_password("s3cret", h)
    assert not passwords.verify_password("nope", h)

def test_login_sets_cookie_and_me_returns_permissions(client, seeded_superadmin):
    r = client.post("/api/auth/login", json={"username": "root", "password": "pw"}, headers=csrf)
    assert r.status_code == 200 and "session" in r.cookies
    me = client.get("/api/auth/me").json()
    assert me["role"]["slug"] == "superadmin" and "system.restore" in me["permissions"]

def test_mutation_without_csrf_header_is_rejected(client, logged_in):
    assert client.post("/api/web-users", json={...}).status_code == 403

def test_csrf_from_another_session_is_rejected(client, logged_in):
    assert client.post("/api/web-users", json={...}, headers={"X-CSRF-Token": other}).status_code == 403

def test_expired_session_returns_401(client, logged_in):
    # move expires_at into the past, expect 401 on /api/auth/me

def test_password_change_revokes_other_sessions(client, logged_in):
    # second login, then change password with the first, assert second is 401

def test_cannot_grant_role_with_permissions_not_held(client, admin_logged_in):
    assert client.post("/api/web-users", json={"username":"x","password":"p",
        "role_id": superadmin_role_id}).status_code == 403

def test_last_users_manager_cannot_be_deactivated(client, seeded_superadmin): ...
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_passwords.py tests/test_sessions.py tests/test_csrf.py -q`

- [ ] **Step 3: Implement**

`passwords.py` — `hashlib.scrypt(password, salt=salt, n=2**14, r=8, p=1, dklen=32)`, format `scrypt$16384$8$1$<salt_b64>$<hash_b64>`, verify with `hmac.compare_digest`. Reject passwords shorter than 8 characters at the route layer.

`sessions.py` — token `secrets.token_urlsafe(32)`; store `sha256(pepper + token)` where pepper is `secret.key` bytes; `resolve` checks `revoked_at IS NULL`, `expires_at > now`, and `last_seen_at > now - idle`; update `last_seen_at` at most once per 60 s.

CSRF — `csrf_token(session_token) = hmac_sha256(pepper, sha256(session_token))` base64; `GET /api/auth/csrf` sets cookie `csrf_token` (not HttpOnly, SameSite=Lax) and returns `{"csrf_token": ...}`. `require_csrf` compares header, cookie, and recomputed value for the current session with `hmac.compare_digest`; API-key principals skip it.

`web/security.py` — middleware assigns `request_id = uuid4().hex[:12]`, sets response headers `X-Request-Id`, `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`, `Cache-Control: no-store` on `/api/*`; rejects mutations whose `Origin` is present and does not match the request host.

`rate_limit.py` — in-memory sliding window keyed by string, `allow(key, limit, window) -> bool`, pruned lazily.

`web_users` repo — create validates username uniqueness, hashes password, records `created_by`; update can change `password`, `role_id`, `is_active`; deactivate/delete guarded by role subset and "last user holding `users.manage`".

- [ ] **Step 4: Verify and commit**

```bash
pytest -q && ruff check .
git add -A && git commit -m "feat: password hashing, sessions, csrf, auth and user APIs"
```

---

### Task 5: Setup wizard, setup gating, audit wiring

**Files:**
- Create: `src/tuyabot/web/routes/setup.py`, `src/tuyabot/storage/repos/app_state.py`
- Create: `src/tuyabot/web/middleware_setup.py`
- Modify: `src/tuyabot/web/app.py`
- Test: `tests/test_api_setup.py`, `tests/test_audit_wiring.py`

**Interfaces:**
- Consumes: everything from Tasks 2–4.
- Produces:
  - `app_state.get(key, default=None)`, `app_state.set(key, value)`, `app_state.is_setup_complete() -> bool`.
  - `GET /api/setup/status` → `{"required": bool}`, `POST /api/setup` → `{"authenticated": true, "user_id": int}` and sets the session cookie.
  - `407`/`409` gating: every `/api/*` route except `setup/*`, `auth/*`, `health` returns `409 {"detail": "setup_required"}` before setup completes.

- [ ] **Step 1: Write the failing tests**

```python
def test_fresh_instance_gates_everything_but_setup(client):
    assert client.get("/api/setup/status").json() == {"required": True}
    assert client.get("/api/devices").status_code == 409

def test_setup_runs_once(client):
    assert client.post("/api/setup", json={"username": "root", "password": "longenough"}, headers=csrf).status_code == 200
    assert client.post("/api/setup", json={"username": "x", "password": "longenough"}, headers=csrf).status_code == 409
    assert client.get("/api/setup/status").json() == {"required": False}

def test_setup_creates_superadmin_and_no_telegram_user(client): ...

def test_denied_mutation_is_audited(client, viewer_logged_in):
    client.post("/api/web-users", json={...}, headers=csrf)   # 403
    row = ...
    assert row["action"] == "web_users.create" and row["result"] == "denied"
```

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Implement**

`app_state.py` — JSON values in `app_state` table, tiny in-process cache invalidated on write.

`setup.py` — creates a `web_users` row with the `superadmin` role, sets `system.setup_complete=true` in `app_state`, writes an audit row `setup.complete`, and returns a session cookie. Uses `BEGIN IMMEDIATE` so two concurrent setup calls cannot both succeed.

`middleware_setup.py` — ASGI middleware checking `app_state.is_setup_complete()`; bypass list is `/healthz`, `/api/setup/status`, `/api/setup`, `/api/auth/csrf`, `/api/auth/login`.

Audit wiring — add `audit.write` calls inside each mutating route from Task 4 (create/update/delete of web users and api keys, password change, session revocation) and a single handler in `deps.require`/`permissions.require` that writes `result="denied"` on `403`.

- [ ] **Step 4: Verify and commit**

```bash
pytest -q && ruff check .
git add -A && git commit -m "feat: first-run setup wizard and audit wiring"
```

---

### Task 6: Devices — registry, controller, DPS, CRUD, control, scan, SSE

**Files:**
- Create: `src/tuyabot/devices/__init__.py`, `src/tuyabot/devices/dps.py`, `src/tuyabot/devices/controller.py`, `src/tuyabot/devices/service.py`, `src/tuyabot/devices/registry.py`
- Create: `src/tuyabot/infra/state_cache.py`
- Create: `src/tuyabot/storage/repos/devices.py`, `src/tuyabot/storage/repos/logs.py`
- Create: `src/tuyabot/web/routes/devices.py`, `src/tuyabot/web/routes/logs.py`, `src/tuyabot/web/routes/stream.py`
- Modify: `src/tuyabot/web/app.py`
- Test: `tests/test_dps.py`, `tests/test_devices_api.py`, `tests/test_device_control.py`, `tests/test_state_cache.py`, `tests/test_stream.py`

**Interfaces:**
- Consumes: `permissions.require`, `run_db`, `audit`.
- Produces:
  - `dps.TEMPLATES: dict[str, dict[str, int]]` (`plug`: `{"switch":1,"current":18,"power":19,"voltage":20}`, `bulb`: `{"switch":20,"brightness":22,"temp":23,"colour":24}`, `switch`, `sensor` empty).
  - `dps.extract(device: dict, raw: dict) -> dict` returning only mapped keys present in `raw`.
  - `controller.TuyaController` with `status(device) -> dict`, `power(device) -> dict`, `set_switch(device, on: bool) -> dict`, `test(device) -> dict`, `forget(device_id)`, `shutdown()`.
  - `service.run_tuya(fn, *args, timeout=None)`; `service.set_timeout_from_settings()`.
  - `registry.list_for(principal) -> list[dict]`, `registry.get(device_id) -> dict`, `registry.reload()`.
  - `state_cache.read(name, kind)`, `state_cache.get_status(name, force=False)`, `state_cache.get_power(name, force=False)`, `state_cache.invalidate(name)`, `state_cache.age(key)`.
  - Routes: `GET|POST /api/devices`, `PATCH|DELETE /api/devices/{id}`, `POST /api/devices/{id}/on|off`, `GET /api/devices/{id}/status|power`, `POST /api/devices/scan`, `GET /api/devices/scan/{job_id}`, `POST /api/devices/{id}/test`, `GET /api/logs/{activities,power,errors}`, `GET /api/stream`.

- [ ] **Step 1: Write the failing tests**

```python
def test_dps_extract_maps_only_declared_keys():
    dev = {"dps": {"switch": 1, "power": 19}}
    assert dps.extract(dev, {"1": True, "19": 12.5, "99": "x"}) == {"switch_on": True, "power_w": 12.5}

def test_unreachable_device_returns_failure_within_timeout(fake_controller, client, logged_in):
    r = client.get("/api/devices/1/status")
    assert r.status_code == 200
    assert r.json()["success"] is False and r.json()["online"] is False

def test_control_requires_permission_and_access_roles(client, viewer_logged_in):
    assert client.post("/api/devices/1/on", headers=csrf).status_code == 403

def test_device_hidden_from_role_returns_404(client, viewer_logged_in):
    assert client.get("/api/devices/2/status").status_code == 404   # access_roles excludes viewer

def test_stream_snapshot_does_not_call_tuya(client, logged_in, spy):
    # consume one SSE event, assert controller.status call count unchanged
```

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Implement**

`controller.py` — `dict[device_id, {"client": tinytuya.Device | None, "lock": threading.Lock}]`; build the client lazily on first use with `set_socketTimeout(4)`, `set_socketRetryLimit(2)`, `set_socketPersistent(False)`; `forget()` closes and drops the entry so IP/key changes take effect.

`service.py` — `ThreadPoolExecutor(max_workers=<setting tuya.threads>)` and `asyncio.wait_for` returning `{"success": False, "message": "Timeout Ns..."}` on expiry.

`registry.py` — snapshot list of active devices; `reload()` called on every device mutation; `list_for(principal)` filters by `devices.access_roles` (empty list = everyone with `devices.view`).

`state_cache.py` — TTL cache with per-key `asyncio.Lock` single-flight; failures cached for `monitoring.error_ttl_seconds`.

`routes/devices.py` — every handler resolves `Principal`, checks permission, resolves device, filters by `access_roles`; control writes an activity log row with `actor="ui"` and the principal's `actor_id`; after a successful control, `state_cache.invalidate` then `get_status(force=True)`.

`routes/stream.py` — `StreamingResponse` of `text/event-stream`, one snapshot every `STREAM_INTERVAL_SECONDS`, reading only from `state_cache`, filtered per principal, `X-Accel-Buffering: no`.

- [ ] **Step 4: Verify and commit**

```bash
pytest -q && ruff check .
git add -A && git commit -m "feat: dynamic device registry, dps mapping, control, scan, sse"
```

---

### Task 7: Telegram — user registry, bot manager, handlers, watchdog

**Files:**
- Create: `src/tuyabot/telegram/__init__.py`, `src/tuyabot/telegram/manager.py`, `src/tuyabot/telegram/app.py`, `src/tuyabot/telegram/guards.py`
- Create: `src/tuyabot/telegram/handlers/__init__.py`, `start.py`, `devices.py`, `admin.py`
- Create: `src/tuyabot/telegram/watchdog.py`
- Create: `src/tuyabot/storage/repos/telegram_users.py`, `src/tuyabot/storage/repos/bots.py`
- Create: `src/tuyabot/web/routes/telegram_users.py`, `src/tuyabot/web/routes/bots.py`
- Modify: `src/tuyabot/main.py`, `src/tuyabot/web/app.py`
- Test: `tests/test_telegram_users.py`, `tests/test_bot_manager.py`, `tests/test_handlers.py`, `tests/test_watchdog.py`

**Interfaces:**
- Consumes: `devices.registry`, `state_cache`, `permissions`, `audit`, `settings`.
- Produces:
  - `bots_repo.list_all()`, `create(label, token) -> int`, `update(id, **fields)`, `delete(id)`, `set_enabled(id, bool)`; `token_sha256` unique.
  - `manager.BotManager`: `await start_all()`, `await enable(bot_id)`, `await disable(bot_id)`, `await rebuild(bot_id)`, `await shutdown()`, `status() -> dict[int, str]`.
  - `telegram_users_repo.get(telegram_id)`, `upsert(telegram_id, role_id, label, created_by_web_user_id)`, `list_all()`, `delete(telegram_id)`.
  - `watchdog.Watchdog`: `arm(device, trigger_user)`, `cancel(device_id)`, `status() -> dict[str, dict]`, `shutdown()`.
  - Routes: `GET|POST /api/telegram-users`, `PATCH|DELETE /api/telegram-users/{telegram_id}`, `GET|POST /api/bots`, `PATCH|DELETE /api/bots/{id}`, `POST /api/bots/{id}/enable|disable|test`.

- [ ] **Step 1: Write the failing tests**

```python
async def test_two_bots_can_be_enabled_independently(manager, fake_app_factory): ...
async def test_invalid_token_is_recorded_and_does_not_stop_other_bots(manager): ...
async def test_duplicate_token_rejected(bots_repo): ...        # sqlite IntegrityError -> 409 from route
async def test_unregistered_telegram_user_gets_public_commands_only(handler_fixture): ...
async def test_on_command_controls_device_by_name(handler_fixture): ...
async def test_adduser_requires_permission_and_subset_role(handler_fixture): ...
async def test_watchdog_files_idle_device_off(watchdog, fake_controller): ...
async def test_watchdog_cancelled_does_not_rearm(watchdog): ...
```

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Implement**

`manager.py` — `dict[int, Application]`; every build happens inside the running loop; lifecycle is `initialize → start → updater.start_polling` and reverse; each bot wrapped in `try/except`, failures written to `telegram_bots.last_error`; a global `asyncio.Lock` serialises enable/disable/rebuild; rebuilds run as a task and report `starting/stopping` through `status()`.

`app.py` — builder adds handlers from `handlers/`, passes a resolved principal resolver for `telegram_id` into `guards`.

`guards.py` — `resolve_principal(telegram_id) -> Principal | None` (None ⇒ public: only `/start` and `/help`); `require_perm(perm)` decorator that replies "tidak berizin" and audits `denied`.

`handlers/devices.py` — `/status`, `/devices`, `/on <nama>`, `/off <nama>`; device resolved from the registry by name slug; control writes an activity row with `actor="bot"` and `bot_id`.

`handlers/admin.py` — `/users`, `/adduser <telegram_id> <role>`, `/removeuser <telegram_id>`, `/logs`; role assignment enforces subset and audits.

`watchdog.py` — one `asyncio.Task` per armed device; samples power with `force=True`; reads `device_settings` for `idle_watt`, `check_minutes`, `max_minutes`, `sample_count`, `sample_delay`, `trigger_role_id`; turns off and audits `device.watchdog_off`; cancelled and not rearmed when maintenance is on.

- [ ] **Step 4: Verify and commit**

```bash
pytest -q && ruff check .
git add -A && git commit -m "feat: dynamic telegram bots, telegram users, generic handlers, watchdog"
```

---

### Task 8: Backup, restore, maintenance, scheduler, stats

**Files:**
- Create: `src/tuyabot/storage/repos/backups.py`, `src/tuyabot/storage/repos/stats.py`
- Create: `src/tuyabot/backup/service.py`
- Create: `src/tuyabot/maintenance/service.py`
- Create: `src/tuyabot/infra/scheduler.py`
- Create: `src/tuyabot/web/routes/backup.py`, `stats.py`, `maintenance.py`, `health.py`, `audit.py`
- Modify: `src/tuyabot/main.py`, `src/tuyabot/web/app.py`
- Test: `tests/test_backup.py`, `tests/test_restore.py`, `tests/test_maintenance.py`, `tests/test_scheduler.py`

**Interfaces:**
- Consumes: `db`, `migrate`, `settings`, `audit`, `state_cache`, `registry`, `manager`.
- Produces:
  - `backup.create(kind: str, note=None) -> dict` (`{"path", "size_bytes", "id"}`); `backup.prune() -> int`; `backup.list() -> list[dict]`.
  - `backup.restore(upload_path: Path) -> dict`; raises `RestoreError` with a `stage` field.
  - `maintenance.enable(reason=None, auto_off_minutes=None)`, `disable()`, `is_on() -> bool`, `block_response() -> tuple[int, dict]`.
  - `scheduler.Scheduler` with `add_job(name, interval, func, initial_delay=0)`, `start()`, `stop()`, `reschedule(name, interval)`.
  - Routes: `GET|POST /api/backup`, `GET /api/backup/{id}/download`, `POST /api/backup/restore`, `GET /api/stats`, `GET|POST /api/maintenance`, `GET /api/audit`, `GET /api/health`.

- [ ] **Step 1: Write the failing tests**

```python
def test_backup_roundtrip_preserves_all_tables(tmp_path): ...
def test_restore_refuses_newer_schema(tmp_path): ...        # expect RestoreError(stage="version")
def test_restore_refuses_corrupt_file(tmp_path): ...        # integrity_check fails, stage="integrity"
def test_failed_restore_leaves_old_db_usable(tmp_path): ... # after error, ping() and a query still work
def test_restore_bumps_generation_and_reopens(tmp_path): ...
def test_maintenance_blocks_non_auth_routes(client, maintainer): ...
def test_maintenance_does_not_arm_watchdog(watchdog, maintainer): ...
def test_scheduler_reschedule_changes_interval(): ...
```

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Implement**

`backup/service.py` — `create` runs `VACUUM INTO` through `run_db`, inserts a `backup_runs` row, chmod `0600`. `restore` follows the spec §8.19 order exactly, each stage wrapped so a failure raises `RestoreError(stage=...)` and leaves maintenance on with `pre_restore` intact; `close_all()`, unlink `-wal`/`-shm`, `os.replace`, `bump_generation()`, reset caches, rebuild bots.

`maintenance/service.py` — state in `app_state.maintenance` (`{"on": bool, "reason": str, "auto_off_at": iso}`); middleware returns `503` + `Retry-After` for everything outside the allowlist; a scheduler job disables it at `auto_off_at`.

`infra/scheduler.py` — single loop over jobs; `reschedule` recomputes the next run; job failures logged and counted.

`stats.py` — device counts by online state from cache, row counts and DB size, last backup, schema version.

`health.py` — `/api/health` returns `ok|degraded|down` from DB ping plus cache freshness; `/healthz` stays in `app.py` and never touches the DB.

`audit.py` route — paginated, filtered list, `audit.view`.

- [ ] **Step 4: Verify and commit**

```bash
pytest -q && ruff check .
git add -A && git commit -m "feat: backup, atomic restore, maintenance mode, scheduler, stats"
```

---

### Task 9: Container, CI, docs, final verification

**Files:**
- Create: `Dockerfile`, `entrypoint.sh`, `docker-compose.yml`, `.github/workflows/ci.yml`
- Modify: `README.md`, `.env.example`
- Test: `tests/test_deploy_config.py`

**Interfaces:**
- Consumes: everything.
- Produces: `docker compose up` from a clean checkout that serves `/healthz` and `/api/setup/status`.

- [ ] **Step 1: Write the deploy guard tests**

```python
def test_compose_has_no_hardcoded_secrets(): ...
def test_dockerfile_runs_non_root_and_has_healthcheck(): ...
def test_env_example_lists_only_bootstrap_keys(): ...
def test_readme_documents_data_backup_restore(): ...
```

- [ ] **Step 2: Implement**

`Dockerfile` — multi-stage (`builder` installs into `/opt/venv`, runtime copies venv + `src/` + `scripts/`), `PYTHONPATH=/app/src`, `USER 10001:10001`, `HEALTHCHECK CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/healthz')"`. Use `exec` in the CMD so signals reach Python.

`entrypoint.sh` — as root, `chown` `data/`, `logs/`, `backup/` if needed, `chmod 700 data`, then `exec setpriv --reuid=10001 --regid=10001 --init-groups python -m tuyabot.main`.

`docker-compose.yml` — `read_only: true`, `tmpfs: /tmp`, `cap_drop: ALL`, `cap_add: [CHOWN, SETUID, SETGID]`, `security_opt: [no-new-privileges]`, volumes `./data`, `./logs`, `./backup`, `env_file: .env` (`required: false`), `stop_grace_period: 15s`.

CI — ruff + pytest on push/PR.

README — quick start (compose up → open `/api/setup/status`), first-run wizard, env table (4 keys), backup/restore/move-machine runbook, troubleshooting (device unreachable, `Conflict: terminated by other getUpdates`).

- [ ] **Step 3: Verify and commit**

```bash
pytest -q && ruff check .
git add -A && git commit -m "chore: container, compose, ci, documentation"
```

- [ ] **Step 4: End-to-end smoke**

```bash
docker compose up -d --build
curl -s http://127.0.0.1:8080/healthz
curl -s http://127.0.0.1:8080/api/setup/status
```

Expected: `{"status":"ok"}` and `{"required":true}`; `docker compose logs` shows the migration and the scheduler start line.

---

## Self-Review Notes

- Every spec §8 subsection maps to a task: 8.1/8.3 → T1, 8.4 → T2, 8.5 → T3, 8.6/8.18 → T4, 8.8/8.20 → T5, 8.9/8.10/8.11 → T6, 8.13 → T7, 8.12/8.19/8.17 → T1+T8, 8.14 → T8, 8.15 → tasks owning each route group, 8.17 deploy → T9.
- Frontend (§7.2, §8.16) is intentionally absent; it is a separate plan after this one ships.
- Task 7 depends on the Telegram library's loop-bound builder; the test fakes the `Application` and never contacts Telegram.
