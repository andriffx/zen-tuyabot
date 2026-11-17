import type { ActivityLog, Device, Health, PowerLog, Stats, StreamDevice } from '#lib/api/types';

export type Alert = { level: 'warn' | 'error'; text: string };

export type OverviewInput = {
	stats: Stats;
	health: Pick<Health, 'status'>;
	devices: Pick<Device, 'id' | 'label' | 'last_error'>[];
	stream: { devices: Record<number, StreamDevice>; sseConnected: boolean };
	activities: Pick<ActivityLog, 'id' | 'device_label' | 'action' | 'status' | 'created_at' | 'actor'>[];
	powerRows?: Pick<PowerLog, 'power_w' | 'created_at' | 'device_id'>[];
};

export type OverviewModel = {
	tiles: {
		devicesOnline: number;
		devicesTotal: number;
		powerNow: number | null;
		lastBackup: string | null;
	};
	power: { points: { at: string; watts: number }[]; current: number | null; max: number };
	activity: OverviewInput['activities'];
	alerts: Alert[];
};

const MAX_POWER_POINTS = 120;

/**
 * Pure model builder for the overview page.
 *
 * Kept free of fetching so the alert and aggregation rules can be tested
 * without a browser or a backend.
 */
export const overview = {
	build(input: OverviewInput): OverviewModel {
		const { stats, health, devices, stream, activities, powerRows = [] } = input;

		const liveValues = Object.values(stream.devices);
		const totalWatts = liveValues.reduce((sum, device) => sum + (device.power_w ?? 0), 0);

		// Power rows arrive newest-first. Take the newest N first, then reverse
		// for the chart — reversing before slicing would keep the oldest rows.
		const points = powerRows
			.slice(0, MAX_POWER_POINTS)
			.reverse()
			.map((row) => ({ at: row.created_at, watts: row.power_w }));

		const max = points.reduce((peak, point) => Math.max(peak, point.watts), 0);

		const alerts: Alert[] = [];
		if (health.status !== 'ok') {
			alerts.push({
				level: 'warn',
				text: health.status === 'down' ? 'Backend melaporkan status down' : 'Status sistem degraded'
			});
		}
		if (!stream.sseConnected) {
			alerts.push({ level: 'warn', text: 'Realtime terputus' });
		}
		for (const device of devices) {
			if (device.last_error) {
				alerts.push({ level: 'error', text: `${device.label}: ${device.last_error}` });
			}
		}

		return {
			tiles: {
				devicesOnline: stats.devices.online,
				devicesTotal: stats.devices.total,
				powerNow: liveValues.length ? totalWatts : null,
				lastBackup: stats.backup.last
			},
			power: { points, current: points.at(-1)?.watts ?? null, max },
			activity: activities.slice(0, 8),
			alerts
		};
	}
};
