import type { PermissionCatalog } from '#lib/api/types';

const LABELS: Record<string, string> = {
	monitoring: 'Lihat status perangkat lewat bot',
	manage_users: 'Kelola user Telegram & role',
	manage_devices: 'Kelola perangkat, bot, backup, settings',
	view_logs: 'Lihat log dari bot'
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
	PROTECTED_REQUIRED: ['manage_users'] as const,

	isProtectedKey(key: string): boolean {
		return (this.PROTECTED_REQUIRED as readonly string[]).includes(key);
	}
};
