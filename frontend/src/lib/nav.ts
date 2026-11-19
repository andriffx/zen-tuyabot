export type NavItem = {
	href: string;
	label: string;
	permission: string;
	icon: string;
};

/**
 * Sidebar entries. The web has a single account, so `permission` no longer
 * filters anything — it stays as documentation of the area each page belongs
 * to, and the visibility filter keeps working if web roles ever return.
 */
const items: NavItem[] = [
	{ href: '/', label: 'Overview', permission: 'monitoring', icon: 'gauge' },
	{ href: '/devices', label: 'Devices', permission: 'monitoring', icon: 'plug' },
	{ href: '/logs/power', label: 'Log Daya', permission: 'view_logs', icon: 'zap' },
	{ href: '/logs/activities', label: 'Log Aktivitas', permission: 'view_logs', icon: 'list' },
	{ href: '/logs/errors', label: 'Log Error', permission: 'view_logs', icon: 'alert' },
	{ href: '/settings', label: 'Settings', permission: 'manage_devices', icon: 'sliders' },
	{ href: '/telegram-users', label: 'Telegram Users', permission: 'manage_users', icon: 'send' },
	{ href: '/roles', label: 'Roles', permission: 'manage_users', icon: 'shield' },
	{ href: '/messages', label: 'Pesan Bot', permission: 'manage_users', icon: 'message' },
	{ href: '/bots', label: 'Bots', permission: 'manage_devices', icon: 'bot' },
	{ href: '/backup', label: 'Backup', permission: 'manage_devices', icon: 'archive' },
	{ href: '/system', label: 'System', permission: 'monitoring', icon: 'activity' }
];

export const nav = {
	items,
	visibleItems(can: (permission: string) => boolean): NavItem[] {
		return items.filter((item) => can(item.permission));
	}
};
