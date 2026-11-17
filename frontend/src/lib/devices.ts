import type { Device, DeviceStatus, StreamDevice } from '#lib/api/types';
import type { FieldError } from '#lib/api/errors';

export type DeviceView = Device & { live: StreamDevice | null };

export type DeviceFormPayload = {
	name?: string;
	label?: string;
	tuya_id?: string;
	local_key?: string;
	ip?: string;
	version?: number;
	type?: string;
	dps?: Record<string, number>;
	features?: Record<string, boolean>;
	access_roles?: number[];
};

export const devices = {
	/** Merge live SSE data over the last fetched list, keyed by device id. */
	mergeStream(list: Device[], streamDevices: Record<number, StreamDevice>): DeviceView[] {
		return list.map((device) => ({ ...device, live: streamDevices[device.id] ?? null }));
	},

	/** Friendly text for an unreachable device; never echoes the raw backend error. */
	statusText(status: Pick<DeviceStatus, 'success' | 'online'>): string {
		return status.success && status.online
			? ''
			: 'Perangkat tidak merespons. Periksa IP dan local key.';
	},

	onlineOf(view: DeviceView): boolean {
		return view.live?.online ?? false;
	},

	switchOf(view: DeviceView): boolean | null {
		return view.live?.switch_on ?? null;
	},

	/** Watchdog devices are shut off automatically, so a manual toggle needs a confirm. */
	requiresConfirm(device: Pick<Device, 'features'>): boolean {
		return Boolean(device.features?.watchdog);
	},

	/** Client-side validation; the server is still authoritative. */
	validation(payload: DeviceFormPayload, { editing = false } = {}): FieldError[] {
		const errors: FieldError[] = [];

		if (!editing) {
			if (!payload.name?.trim()) errors.push({ key: 'name', message: 'Nama wajib diisi' });
			else if (!/^[a-z0-9_-]+$/.test(payload.name.trim()))
				errors.push({ key: 'name', message: 'Nama hanya huruf kecil, angka, - atau _' });
			if (!payload.tuya_id?.trim())
				errors.push({ key: 'tuya_id', message: 'Tuya ID wajib diisi' });
			if (!payload.local_key?.trim())
				errors.push({ key: 'local_key', message: 'Local key wajib diisi' });
		}

		if (payload.version !== undefined && !Number.isFinite(Number(payload.version))) {
			errors.push({ key: 'version', message: 'Versi harus angka' });
		}

		for (const [key, index] of Object.entries(payload.dps ?? {})) {
			if (!Number.isInteger(index) || index < 0) {
				errors.push({ key: 'dps', message: `DP untuk ${key} harus bilangan bulat ≥ 0` });
				break;
			}
		}

		return errors;
	}
};
