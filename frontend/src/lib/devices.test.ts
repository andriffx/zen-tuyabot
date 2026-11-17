import { describe, expect, it } from 'vitest';
import type { Device, StreamDevice } from '#lib/api/types';
import { devices } from './devices';

const base: Device = {
	id: 1,
	name: 'pompa',
	label: 'Pompa',
	type: 'plug',
	ip: '10.0.0.5',
	version: 3.5,
	dps: { switch: 1 },
	features: {},
	access_roles: [],
	is_active: true,
	sort_order: 0,
	last_seen_at: null,
	last_error: null,
	has_local_key: true
};

const live: StreamDevice = {
	id: 1,
	name: 'pompa',
	label: 'Pompa',
	online: true,
	switch_on: true,
	power_w: 99,
	voltage_v: 220,
	current_a: 0.4,
	age_seconds: 2
};

describe('devices helper', () => {
	it('explains an unreachable device without echoing the raw backend text', () => {
		expect(devices.statusText({ success: false, online: false })).toBe(
			'Perangkat tidak merespons. Periksa IP dan local key.'
		);
		expect(devices.statusText({ success: true, online: true })).toBe('');
	});

	it('merges live stream data by id', () => {
		const merged = devices.mergeStream([base], { 1: live });
		expect(merged[0].live?.power_w).toBe(99);
		expect(devices.onlineOf(merged[0])).toBe(true);
		expect(devices.switchOf(merged[0])).toBe(true);
	});

	it('reports a device with no live data as offline, not unknown', () => {
		const merged = devices.mergeStream([base], {});
		expect(merged[0].live).toBeNull();
		expect(devices.onlineOf(merged[0])).toBe(false);
		expect(devices.switchOf(merged[0])).toBeNull();
	});

	it('asks for confirmation when the device has a watchdog', () => {
		expect(devices.requiresConfirm({ features: { watchdog: true } })).toBe(true);
		expect(devices.requiresConfirm(base)).toBe(false);
	});

	it('reports missing required fields before sending', () => {
		expect(devices.validation({ name: '', tuya_id: '', local_key: '' })).toEqual([
			{ key: 'name', message: 'Nama wajib diisi' },
			{ key: 'tuya_id', message: 'Tuya ID wajib diisi' },
			{ key: 'local_key', message: 'Local key wajib diisi' }
		]);
	});

	it('rejects an invalid name slug', () => {
		expect(devices.validation({ name: 'Pompa Air', tuya_id: 'x', local_key: 'k' })).toContainEqual({
			key: 'name',
			message: 'Nama hanya huruf kecil, angka, - atau _'
		});
	});

	it('does not require identity fields when editing', () => {
		expect(devices.validation({ label: 'Baru' }, { editing: true })).toEqual([]);
	});

	it('rejects non-integer DP indices', () => {
		expect(devices.validation({ dps: { switch: 1.5 } }, { editing: true })).toEqual([
			{ key: 'dps', message: 'DP untuk switch harus bilangan bulat ≥ 0' }
		]);
	});

	it('rejects a non-numeric version', () => {
		expect(
			devices.validation({ version: Number('abc') }, { editing: true })
		).toContainEqual({ key: 'version', message: 'Versi harus angka' });
	});
});
