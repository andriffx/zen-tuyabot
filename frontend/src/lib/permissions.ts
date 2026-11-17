import type { PermissionCatalog } from '#lib/api/types';

const LABELS: Record<string, string> = {
	'devices.view': 'Lihat perangkat',
	'devices.control': 'Kontrol perangkat',
	'devices.manage': 'Kelola perangkat',
	'devices.scan': 'Scan jaringan & test koneksi',
	'logs.view': 'Lihat log',
	'logs.cleanup': 'Bersihkan log',
	'settings.view': 'Lihat settings',
	'settings.edit': 'Ubah settings',
	'users.view': 'Lihat akun web',
	'users.manage': 'Kelola akun web',
	'telegram_users.view': 'Lihat user Telegram',
	'telegram_users.manage': 'Kelola user Telegram',
	'roles.manage': 'Kelola role & permission',
	'bots.view': 'Lihat bot',
	'bots.manage': 'Kelola bot',
	'backup.view': 'Lihat backup',
	'backup.create': 'Buat backup',
	'backup.restore': 'Unduh backup',
	'apikeys.manage': 'Kelola API key',
	'system.view': 'Lihat sistem',
	'audit.view': 'Lihat audit log',
	'system.maintenance': 'Aktifkan maintenance',
	'system.restore': 'Restore database'
};

const CATEGORY_LABELS: Record<string, string> = {
	Device: 'Perangkat',
	Log: 'Log',
	Settings: 'Settings',
	'Users web': 'Akun web',
	'Users Telegram': 'User Telegram',
	Roles: 'Role',
	Bot: 'Bot',
	Backup: 'Backup',
	'API key': 'API key',
	Sistem: 'Sistem'
};

export type GroupedPermissions = {
	name: string;
	permissions: { key: string; label: string }[];
};

export const permissions = {
	label(key: string): string {
		return LABELS[key] ?? key;
	},

	groupCatalog(catalog: PermissionCatalog): GroupedPermissions[] {
		return catalog.categories.map((category) => ({
			name: CATEGORY_LABELS[category.name] ?? category.name,
			permissions: category.permissions.map((key) => ({ key, label: this.label(key) }))
		}));
	},

	/** A role editor may only grant what the editor already holds. */
	editable(catalog: PermissionCatalog, actorPermissions: string[]): string[] {
		const held = new Set(actorPermissions);
		return catalog.all.filter((key) => held.has(key));
	},

	/** Permissions a protected (superadmin) role may never lose. */
	PROTECTED_REQUIRED: ['roles.manage', 'users.manage', 'system.view'] as const,

	isProtectedKey(key: string): boolean {
		return (this.PROTECTED_REQUIRED as readonly string[]).includes(key);
	}
};
