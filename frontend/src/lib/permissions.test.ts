import { describe, expect, it } from 'vitest';
import type { PermissionCatalog } from '#lib/api/types';
import { permissions } from './permissions';

const catalog: PermissionCatalog = {
	categories: [
		{ name: 'Bot', permissions: ['monitoring', 'manage_devices', 'manage_users'] }
	],
	all: ['monitoring', 'manage_devices', 'manage_users']
};

describe('permissions', () => {
	it('labels known keys in Indonesian', () => {
		const grouped = permissions.groupCatalog(catalog);
		expect(grouped[0].name).toBe('Bot');
		expect(grouped[0].permissions[0]).toEqual({
			key: 'monitoring',
			label: 'Lihat status perangkat lewat bot'
		});
	});

	it('falls back to the raw key for an unknown permission', () => {
		expect(permissions.label('future.permission')).toBe('future.permission');
	});

	it('groups every catalog key exactly once', () => {
		const flat = permissions.groupCatalog(catalog).flatMap((group) => group.permissions);
		expect(flat.map((entry) => entry.key).sort()).toEqual([...catalog.all].sort());
	});

	it('offers only permissions the actor already holds', () => {
		expect(permissions.editable(catalog, ['monitoring'])).toEqual(['monitoring']);
		expect(permissions.editable(catalog, [])).toEqual([]);
	});

	it('marks the protected permission keys', () => {
		expect(permissions.isProtectedKey('manage_users')).toBe(true);
		expect(permissions.isProtectedKey('monitoring')).toBe(false);
	});
});
