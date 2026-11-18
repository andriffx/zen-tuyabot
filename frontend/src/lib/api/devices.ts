import { del, get, patch, post } from './client';
import type {
	ControlResult,
	Device,
	DeviceDiagnosis,
	DeviceStatus,
	DeviceTemplates,
	DeviceTestResult,
	ScanJob
} from './types';

export type DevicePayload = {
	name?: string;
	label?: string;
	tuya_id?: string;
	local_key?: string;
	ip?: string | null;
	version?: number;
	type?: string;
	dps?: Record<string, number>;
	features?: Record<string, boolean>;
	access_roles?: number[];
	is_active?: boolean;
	sort_order?: number;
};

export const devicesApi = {
	list: () => get<{ devices: Device[] }>('/api/devices'),
	templates: () => get<DeviceTemplates>('/api/devices/templates'),
	create: (payload: DevicePayload) => post<Device>('/api/devices', payload),
	update: (id: number, payload: DevicePayload) => patch<Device>(`/api/devices/${id}`, payload),
	remove: (id: number) => del<{ deleted: boolean }>(`/api/devices/${id}`),
	on: (id: number) => post<ControlResult>(`/api/devices/${id}/on`),
	off: (id: number) => post<ControlResult>(`/api/devices/${id}/off`),
	status: (id: number) => get<DeviceStatus>(`/api/devices/${id}/status`),
	test: (id: number) => post<DeviceTestResult>(`/api/devices/${id}/test`),
	diagnose: (id: number) => post<DeviceDiagnosis>(`/api/devices/${id}/diagnose`),
	scan: () => post<{ job_id: string; status: string }>('/api/devices/scan'),
	scanStatus: (jobId: string, signal?: AbortSignal) =>
		get<ScanJob>(`/api/devices/scan/${jobId}`, { signal })
};
