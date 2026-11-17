import { get, post } from './client';
import type { AuditEntry, Health, MaintenanceState, Stats } from './types';

export type AuditQuery = {
	limit?: number;
	offset?: number;
	actor_kind?: string;
	action?: string;
	result?: string;
	target_kind?: string;
	request_id?: string;
	since?: string;
	until?: string;
};

export type MaintenancePayload = { enabled: boolean; reason?: string; auto_off_minutes?: number };

export const systemApi = {
	stats: () => get<Stats>('/api/stats'),
	health: () => get<Health>('/api/health'),
	maintenanceStatus: () => get<MaintenanceState>('/api/maintenance/status'),
	maintenance: () => get<MaintenanceState>('/api/maintenance'),
	setMaintenance: (payload: MaintenancePayload) => post<MaintenanceState>('/api/maintenance', payload),
	audit: (query: AuditQuery = {}) => {
		const search = new URLSearchParams();
		for (const [key, value] of Object.entries(query)) {
			if (value !== undefined && value !== null && value !== '') search.set(key, String(value));
		}
		const rendered = search.toString();
		return get<{ items: AuditEntry[]; limit: number; offset: number }>(
			`/api/audit${rendered ? `?${rendered}` : ''}`
		);
	}
};
