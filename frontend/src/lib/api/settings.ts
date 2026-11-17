import { get, patch } from './client';
import type { SettingsResponse, SettingsSchemaEntry } from './types';

export const settingsApi = {
	get: () => get<SettingsResponse>('/api/settings'),
	schema: () => get<{ schema: SettingsSchemaEntry[] }>('/api/settings/schema'),
	patch: (values: Record<string, unknown>) =>
		patch<{ changed: Record<string, { old: unknown; new: unknown }>; values: Record<string, unknown> }>(
			'/api/settings',
			{ values }
		)
};
