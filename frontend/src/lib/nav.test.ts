import { describe, expect, it } from 'vitest';
import { nav } from './nav';

describe('nav', () => {
	it('has exactly 12 unique entries', () => {
		expect(nav.items).toHaveLength(12);
		expect(new Set(nav.items.map((item) => item.href)).size).toBe(12);
	});

	it('filters by permission', () => {
		const visible = nav.visibleItems((permission) => permission === 'devices.view');
		expect(visible.map((item) => item.href)).toEqual(['/', '/devices']);
	});

	it('a superadmin sees every entry', () => {
		expect(nav.visibleItems(() => true)).toHaveLength(12);
	});

	it('every entry declares a permission from the backend catalog', () => {
		const known = new Set([
			'devices.view',
			'logs.view',
			'settings.view',
			'users.view',
			'telegram_users.view',
			'bots.view',
			'backup.view',
			'system.view'
		]);
		for (const item of nav.items) {
			expect(known.has(item.permission)).toBe(true);
		}
	});
});
