import { del, get, patch, post } from './client';
import type { PermissionCatalog, Role } from './types';

export type RolePayload = {
	slug?: string;
	name?: string;
	description?: string | null;
	permissions?: string[];
	rate_limit_per_minute?: number | null;
};

export const rolesApi = {
	list: () => get<{ roles: Role[] }>('/api/roles'),
	catalog: () => get<PermissionCatalog>('/api/roles/permissions'),
	create: (payload: { slug: string; name: string; description?: string | null; permissions: string[] }) =>
		post<Role>('/api/roles', payload),
	update: (id: number, payload: RolePayload) => patch<Role>(`/api/roles/${id}`, payload),
	remove: (id: number) => del<{ deleted: boolean }>(`/api/roles/${id}`)
};
