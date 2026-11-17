-- 0002_seed.sql — role awal.
-- Superadmin dilindungi: tidak bisa dihapus dan izin intinya tidak bisa dicabut.

INSERT OR IGNORE INTO roles (slug, name, description, permissions, is_system, is_protected)
VALUES
    (
        'superadmin',
        'Superadmin',
        'Akses penuh termasuk kelola user, role, bot, dan restore database',
        '["devices.view","devices.control","devices.manage","devices.scan","logs.view","logs.cleanup","settings.view","settings.edit","users.view","users.manage","telegram_users.view","telegram_users.manage","roles.manage","bots.view","bots.manage","backup.view","backup.create","backup.restore","apikeys.manage","system.view","audit.view","system.maintenance","system.restore"]',
        1,
        1
    ),
    (
        'admin',
        'Admin',
        'Kelola perangkat, setting, bot, dan backup; tanpa kelola user atau role',
        '["devices.view","devices.control","devices.manage","devices.scan","logs.view","logs.cleanup","settings.view","settings.edit","users.view","telegram_users.view","bots.view","bots.manage","backup.view","backup.create","backup.restore","apikeys.manage","system.view","audit.view"]',
        1,
        0
    ),
    (
        'operator',
        'Operator',
        'Lihat dan kontrol perangkat sesuai pembatasan perangkat',
        '["devices.view","devices.control","logs.view"]',
        1,
        0
    ),
    (
        'viewer',
        'Viewer',
        'Hanya melihat status perangkat dan log',
        '["devices.view","logs.view"]',
        1,
        0
    );
