import { describe, expect, it } from 'vitest';
import { nav } from './nav';

describe('nav', () => {
	it('has exactly 12 unique entries', () => {
		expect(nav.items).toHaveLength(12);
		expect(new Set(nav.items.map((item) => item.href)).size).toBe(12);
	});

	it('filters by permission', () => {
		const visible = nav.visibleItems((permission) => permission === 'monitoring');
		expect(visible.map((item) => item.href)).toEqual(['/', '/devices', '/system']);
	});

	it('a superadmin sees every entry', () => {
		expect(nav.visibleItems(() => true)).toHaveLength(12);
	});

	it('every entry declares a permission from the backend catalog', () => {
		// The web has one account, so entries tag the bot permission area they
		// belong to; these are the four keys in access/permissions.py.
		const known = new Set(['monitoring', 'manage_users', 'manage_devices', 'view_logs']);
		for (const item of nav.items) {
			expect(known.has(item.permission)).toBe(true);
		}
	});
});
