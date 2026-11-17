import { describe, expect, it } from 'vitest';
import type { PermissionCatalog } from '#lib/api/types';
import { permissions } from './permissions';

const catalog: PermissionCatalog = {
	categories: [
		{ name: 'Device', permissions: ['devices.view', 'devices.control'] },
		{ name: 'Roles', permissions: ['roles.manage'] }
	],
	all: ['devices.view', 'devices.control', 'roles.manage']
};

describe('permissions', () => {
	it('labels known keys in Indonesian', () => {
		const grouped = permissions.groupCatalog(catalog);
		expect(grouped[0].name).toBe('Perangkat');
		expect(grouped[0].permissions[0]).toEqual({
			key: 'devices.view',
			label: 'Lihat perangkat'
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
		expect(permissions.editable(catalog, ['devices.view'])).toEqual(['devices.view']);
		expect(permissions.editable(catalog, [])).toEqual([]);
	});

	it('marks the protected permission keys', () => {
		expect(permissions.isProtectedKey('roles.manage')).toBe(true);
		expect(permissions.isProtectedKey('devices.view')).toBe(false);
	});
});
