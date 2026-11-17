"""Typed settings registry — the single source of truth for configuration.

Configuration lives in the database (`app_settings`) but its shape, defaults,
validation, and apply semantics live here in code. Adding a setting means
adding one entry; no migration is needed for the value itself unless a row
must be seeded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

APPLY_LIVE = "live"
APPLY_TELEGRAM_RESTART = "telegram_restart"


class ValidationError(ValueError):
    def __init__(self, key: str, message: str) -> None:
        super().__init__(f"{key}: {message}")
        self.key = key
        self.message = message


@dataclass(frozen=True)
class SettingDef:
    key: str
    type: str
    default: Any
    category: str
    label: str
    help: str = ""
    apply: str = APPLY_LIVE
    secret: bool = False
    edit_permission: str = "settings.edit"
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[str, ...] = field(default_factory=tuple)
    read_only: bool = False


def _s(
    key: str,
    type_: str,
    default: Any,
    category: str,
    label: str,
    **kwargs: Any,
) -> SettingDef:
    return SettingDef(key=key, type=type_, default=default, category=category, label=label, **kwargs)


DEFS: tuple[SettingDef, ...] = (
    # ── telegram ──
    _s(
        "telegram.enabled",
        "bool",
        True,
        "telegram",
        "Bot Telegram aktif",
        help="Saklar utama semua bot. Token per bot diatur di halaman Bot.",
        apply=APPLY_TELEGRAM_RESTART,
    ),
    # ── monitoring ──
    _s("monitoring.power_interval_minutes", "int", 5, "monitoring", "Interval catat daya (menit)", minimum=1, maximum=1440),
    _s("monitoring.cache_ttl_seconds", "float", 5.0, "monitoring", "TTL cache status (detik)", minimum=0.5, maximum=300),
    _s("monitoring.error_ttl_seconds", "float", 2.0, "monitoring", "TTL cache kegagalan (detik)", minimum=0.5, maximum=60),
    _s("monitoring.warm_interval_seconds", "float", 60.0, "monitoring", "Interval pemanasan cache (detik)", minimum=15, maximum=3600),
    # ── housekeeping ──
    _s("housekeeping.interval_hours", "int", 24, "housekeeping", "Interval housekeeping (jam)", minimum=1, maximum=720),
    _s("housekeeping.log_retention_days", "int", 60, "housekeeping", "Retensi log perangkat (hari)", minimum=1, maximum=3650),
    _s("housekeeping.audit_retention_days", "int", 180, "housekeeping", "Retensi audit log (hari)", minimum=1, maximum=3650),
    # ── backup ──
    _s("backup.auto_enabled", "bool", True, "backup", "Backup otomatis"),
    _s("backup.interval_hours", "int", 24, "backup", "Interval backup (jam)", minimum=1, maximum=720),
    _s("backup.retention_days", "int", 14, "backup", "Retensi backup (hari)", minimum=1, maximum=3650),
    # ── tuya ──
    _s("tuya.call_timeout_seconds", "float", 25.0, "tuya", "Batas waktu panggilan perangkat (detik)", minimum=1, maximum=120),
    _s("tuya.threads", "int", 4, "tuya", "Jumlah thread I/O perangkat", minimum=1, maximum=32),
    _s("tuya.scan_timeout_seconds", "float", 20.0, "tuya", "Batas waktu scan LAN (detik)", minimum=5, maximum=120),
    # ── security ──
    _s("security.session_ttl_hours", "int", 12, "security", "Umur sesi (jam)", minimum=1, maximum=720),
    _s("security.session_idle_minutes", "int", 60, "security", "Idle timeout sesi (menit)", minimum=5, maximum=1440),
    _s("security.cookie_secure", "bool", False, "security", "Cookie hanya lewat HTTPS"),
    _s("security.login_max_attempts", "int", 5, "security", "Batas gagal login per user", minimum=1, maximum=100),
    _s("security.login_ip_max_attempts", "int", 20, "security", "Batas gagal login per IP", minimum=1, maximum=1000),
    _s("security.login_window_seconds", "int", 300, "security", "Jendela hitung gagal login (detik)", minimum=30, maximum=86400),
    _s("security.rate_limit_window_seconds", "int", 60, "security", "Jendela rate limit (detik)", minimum=10, maximum=3600),
    # ── maintenance ──
    _s("maintenance.auto_off_minutes", "int", 60, "maintenance", "Auto-off maintenance (menit)", minimum=5, maximum=1440),
    _s(
        "maintenance.telegram_behavior",
        "enum",
        "stay_silent",
        "maintenance",
        "Perilaku bot saat maintenance",
        choices=("stay_silent", "stop_bots"),
    ),
    # ── ui ──
    _s("ui.title", "string", "Tuya", "ui", "Judul dashboard", maximum=None),
    _s("ui.theme", "enum", "system", "ui", "Tema", choices=("system", "light", "dark")),
    _s("ui.power_chart_default_range", "enum", "24h", "ui", "Rentang grafik daya", choices=("1h", "24h", "7d")),
    # ── system (read-only) ──
    _s("system.setup_complete", "bool", False, "system", "Setup selesai", read_only=True),
    _s("system.schema_version", "int", 0, "system", "Versi skema", read_only=True),
    _s("system.data_dir", "string", "", "system", "Direktori data", read_only=True),
)

REGISTRY: dict[str, SettingDef] = {definition.key: definition for definition in DEFS}

BY_CATEGORY: dict[str, list[SettingDef]] = {}
for _definition in DEFS:
    BY_CATEGORY.setdefault(_definition.category, []).append(_definition)


def get(key: str) -> SettingDef:
    try:
        return REGISTRY[key]
    except KeyError as exc:
        raise ValidationError(key, "setting tidak dikenal") from exc


def validate(key: str, value: Any) -> Any:
    """Return the value unchanged if valid; raise ValidationError otherwise.

    Deliberately does not coerce: a string where an int is declared is an
    error, not something to parse. The UI sends typed JSON.
    """
    definition = get(key)
    kind = definition.type

    if kind == "bool":
        if not isinstance(value, bool):
            raise ValidationError(key, "harus boolean")
        return value

    if kind in ("int", "float"):
        expected = int if kind == "int" else (int, float)
        if isinstance(value, bool) or not isinstance(value, expected):
            raise ValidationError(key, f"harus {kind}")
        number = int(value) if kind == "int" else float(value)
        if definition.minimum is not None and number < definition.minimum:
            raise ValidationError(key, f"minimal {definition.minimum}")
        if definition.maximum is not None and number > definition.maximum:
            raise ValidationError(key, f"maksimal {definition.maximum}")
        return number

    if kind == "enum":
        if value not in definition.choices:
            raise ValidationError(key, f"pilih salah satu: {', '.join(definition.choices)}")
        return value

    if kind == "string":
        if not isinstance(value, str):
            raise ValidationError(key, "harus teks")
        return value

    if kind == "json":
        if not isinstance(value, (dict, list)):
            raise ValidationError(key, "harus objek atau array")
        return value

    if kind == "secret":
        if not isinstance(value, str):
            raise ValidationError(key, "harus teks")
        return value

    raise ValidationError(key, f"tipe tidak dikenal: {kind}")


def public_schema() -> list[dict[str, Any]]:
    """Everything the settings UI needs, without any stored value."""
    return [
        {
            "key": definition.key,
            "type": definition.type,
            "default": definition.default,
            "category": definition.category,
            "label": definition.label,
            "help": definition.help,
            "apply": definition.apply,
            "secret": definition.secret,
            "edit_permission": definition.edit_permission,
            "minimum": definition.minimum,
            "maximum": definition.maximum,
            "choices": list(definition.choices),
            "read_only": definition.read_only,
        }
        for definition in DEFS
    ]
