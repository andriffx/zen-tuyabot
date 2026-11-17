export type NavItem = {
	href: string;
	label: string;
	permission: string;
	icon: string;
};

/** Exactly 12 entries; a test pins the count and uniqueness. */
const items: NavItem[] = [
	{ href: '/', label: 'Overview', permission: 'devices.view', icon: 'gauge' },
	{ href: '/devices', label: 'Devices', permission: 'devices.view', icon: 'plug' },
	{ href: '/logs/power', label: 'Log Daya', permission: 'logs.view', icon: 'zap' },
	{ href: '/logs/activities', label: 'Log Aktivitas', permission: 'logs.view', icon: 'list' },
	{ href: '/logs/errors', label: 'Log Error', permission: 'logs.view', icon: 'alert' },
	{ href: '/settings', label: 'Settings', permission: 'settings.view', icon: 'sliders' },
	{ href: '/users', label: 'Users', permission: 'users.view', icon: 'users' },
	{ href: '/telegram-users', label: 'Telegram Users', permission: 'telegram_users.view', icon: 'send' },
	{ href: '/roles', label: 'Roles', permission: 'users.view', icon: 'shield' },
	{ href: '/bots', label: 'Bots', permission: 'bots.view', icon: 'bot' },
	{ href: '/backup', label: 'Backup', permission: 'backup.view', icon: 'archive' },
	{ href: '/system', label: 'System', permission: 'system.view', icon: 'activity' }
];

export const nav = {
	items,
	visibleItems(can: (permission: string) => boolean): NavItem[] {
		return items.filter((item) => can(item.permission));
	}
};
