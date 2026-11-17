import { describe, expect, it } from 'vitest';
import type { PowerLog, Stats } from '#lib/api/types';
import { overview, type OverviewInput } from './overview';

const stats: Stats = {
	devices: { total: 3, online: 2, offline: 1 },
	rows: {},
	database: { path: '/x', size_bytes: 1, schema_version: 4 },
	backup: { last: 'a.db', last_at: '2026-11-18 10:00:00' },
	process: { pid: 1 }
};

function input(overrides: Partial<OverviewInput> = {}): OverviewInput {
	return {
		stats,
		health: { status: 'ok' },
		devices: [],
		stream: { devices: {}, sseConnected: true },
		activities: [],
		...overrides
	};
}

describe('overview.build', () => {
	it('builds tiles from stats', () => {
		const model = overview.build(input());
		expect(model.tiles.devicesOnline).toBe(2);
		expect(model.tiles.devicesTotal).toBe(3);
		expect(model.tiles.lastBackup).toBe('a.db');
	});

	it('sums live power and reports null when no device reports', () => {
		const model = overview.build(
			input({
				stream: {
					sseConnected: true,
					devices: {
						1: { id: 1, name: 'a', label: 'A', online: true, switch_on: true, power_w: 12.5, voltage_v: 220, current_a: 0.1, age_seconds: 1 },
						2: { id: 2, name: 'b', label: 'B', online: true, switch_on: true, power_w: 7.5, voltage_v: 220, current_a: 0.1, age_seconds: 1 }
					}
				}
			})
		);
		expect(model.tiles.powerNow).toBe(20);
		expect(overview.build(input()).tiles.powerNow).toBeNull();
	});

	it('warns when health is degraded', () => {
		const model = overview.build(input({ health: { status: 'degraded' } }));
		expect(model.alerts.some((alert) => alert.level === 'warn')).toBe(true);
	});

	it('warns about realtime without claiming the api is offline', () => {
		const model = overview.build(
			input({ stream: { devices: {}, sseConnected: false } })
		);
		expect(model.alerts).toContainEqual({ level: 'warn', text: 'Realtime terputus' });
	});

	it('surfaces the last device error', () => {
		const model = overview.build(
			input({ devices: [{ id: 1, label: 'Pompa', last_error: 'Timeout' }] })
		);
		expect(model.alerts).toContainEqual({ level: 'error', text: 'Pompa: Timeout' });
	});

	it('keeps only the newest 120 power points and derives the peak', () => {
		// The backend returns newest first, so row 0 is the latest reading.
		const rows: Pick<PowerLog, 'power_w' | 'created_at' | 'device_id'>[] = Array.from(
			{ length: 200 },
			(_, index) => ({
				power_w: 199 - index,
				created_at: `2026-11-18 10:00:${String(index % 60).padStart(2, '0')}`,
				device_id: 1
			})
		);
		const model = overview.build(input({ powerRows: rows }));
		expect(model.power.points.length).toBe(120);
		expect(model.power.max).toBe(199);
		expect(model.power.current).toBe(199);
	});

	it('orders power points oldest first', () => {
		const model = overview.build(
			input({
				powerRows: [
					{ power_w: 30, created_at: '2026-11-18 10:00:03', device_id: 1 },
					{ power_w: 20, created_at: '2026-11-18 10:00:02', device_id: 1 },
					{ power_w: 10, created_at: '2026-11-18 10:00:01', device_id: 1 }
				]
			})
		);
		expect(model.power.points.map((point) => point.watts)).toEqual([10, 20, 30]);
		expect(model.power.current).toBe(30);
	});

	it('caps the activity list at eight entries', () => {
		const activities = Array.from({ length: 12 }, (_, index) => ({
			id: index,
			device_label: 'A',
			action: 'turn_on',
			status: 'success',
			created_at: '2026-11-18 10:00:00',
			actor: 'ui'
		}));
		expect(overview.build(input({ activities })).activity).toHaveLength(8);
	});
});
