-- 0001_init.sql — skema awal v1.
-- Semua timestamp TEXT lokal. Tidak ada seed di sini (seed ada di 0002+).

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    checksum    TEXT NOT NULL,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS app_settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_by  INTEGER
);

CREATE TABLE IF NOT EXISTS roles (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    slug                  TEXT NOT NULL UNIQUE,
    name                  TEXT NOT NULL,
    description           TEXT,
    permissions           TEXT NOT NULL DEFAULT '[]',
    rate_limit_per_minute INTEGER,
    is_system             INTEGER NOT NULL DEFAULT 0 CHECK (is_system IN (0,1)),
    is_protected          INTEGER NOT NULL DEFAULT 0 CHECK (is_protected IN (0,1)),
    created_at            TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at            TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS web_users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role_id       INTEGER NOT NULL REFERENCES roles(id),
    is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    created_by    INTEGER REFERENCES web_users(id),
    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS web_sessions (
    token_hash   TEXT PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES web_users(id) ON DELETE CASCADE,
    created_at   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    expires_at   TEXT NOT NULL,
    last_seen_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    ip           TEXT,
    user_agent   TEXT,
    revoked_at   TEXT
);

CREATE TABLE IF NOT EXISTS telegram_users (
    telegram_id            INTEGER PRIMARY KEY,
    label                  TEXT,
    role_id                INTEGER NOT NULL REFERENCES roles(id),
    is_active              INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    created_by_web_user_id INTEGER REFERENCES web_users(id),
    created_by_telegram_id INTEGER,
    created_at             TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at             TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    last_seen_at           TEXT
);

CREATE TABLE IF NOT EXISTS telegram_bots (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    label        TEXT NOT NULL,
    token        TEXT NOT NULL,
    token_sha256 TEXT NOT NULL UNIQUE,
    enabled      INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0,1)),
    bot_username TEXT,
    last_ok_at   TEXT,
    last_error   TEXT,
    created_by   INTEGER REFERENCES web_users(id),
    created_at   TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS api_keys (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    key_hash     TEXT NOT NULL UNIQUE,
    role_id      INTEGER NOT NULL REFERENCES roles(id),
    is_active    INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    created_by   INTEGER REFERENCES web_users(id),
    last_used_at TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS devices (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
    label         TEXT NOT NULL,
    tuya_id       TEXT NOT NULL UNIQUE,
    local_key     TEXT NOT NULL,
    ip            TEXT,
    version       REAL NOT NULL DEFAULT 3.5,
    type          TEXT NOT NULL DEFAULT 'plug',
    dps           TEXT NOT NULL DEFAULT '{}',
    features      TEXT NOT NULL DEFAULT '{}',
    access_roles  TEXT NOT NULL DEFAULT '[]',
    is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    sort_order    INTEGER NOT NULL DEFAULT 0,
    last_seen_at  TEXT,
    last_error    TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS device_settings (
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    key       TEXT NOT NULL,
    value     TEXT NOT NULL,
    PRIMARY KEY (device_id, key)
);

CREATE TABLE IF NOT EXISTS device_activity_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   INTEGER REFERENCES devices(id) ON DELETE SET NULL,
    user_id     INTEGER,
    actor       TEXT NOT NULL,
    bot_id      INTEGER,
    action      TEXT NOT NULL,
    status      TEXT NOT NULL,
    message     TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS device_power_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id    INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    power_w      REAL NOT NULL DEFAULT 0,
    voltage_v    REAL NOT NULL DEFAULT 0,
    current_a    REAL NOT NULL DEFAULT 0,
    switch_state INTEGER,
    source       TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS app_error_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    level           TEXT NOT NULL,
    logger_name     TEXT NOT NULL,
    message         TEXT NOT NULL,
    exception_trace TEXT,
    file_name       TEXT,
    line_number     INTEGER,
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS backup_runs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    filename   TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    kind       TEXT NOT NULL,
    note       TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    at          TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    actor_kind  TEXT NOT NULL,
    actor_id    INTEGER,
    actor_label TEXT,
    action      TEXT NOT NULL,
    target_kind TEXT,
    target_id   TEXT,
    result      TEXT NOT NULL DEFAULT 'ok',
    ip          TEXT,
    details     TEXT,
    request_id  TEXT
);

CREATE TABLE IF NOT EXISTS app_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_activity_device_created ON device_activity_logs(device_id, created_at);
CREATE INDEX IF NOT EXISTS idx_power_device_created ON device_power_logs(device_id, created_at);
CREATE INDEX IF NOT EXISTS idx_power_created ON device_power_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_error_created ON app_error_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_web_sessions_expires ON web_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_web_sessions_user ON web_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_web_users_role ON web_users(role_id);
CREATE INDEX IF NOT EXISTS idx_telegram_users_role ON telegram_users(role_id);
CREATE INDEX IF NOT EXISTS idx_audit_at ON audit_logs(at);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_logs(actor_kind, actor_id, at);
