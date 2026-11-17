import { del, get, post } from './client';
import type { AuthMe, LoginResponse, SessionRow, SetupStatus } from './types';

export const authApi = {
	me: () => get<AuthMe>('/api/auth/me', { silent401: true }),
	login: (username: string, password: string) =>
		post<LoginResponse>('/api/auth/login', { username, password }, { silent401: true }),
	logout: () => post<{ authenticated: boolean }>('/api/auth/logout'),
	changePassword: (current_password: string, new_password: string) =>
		post<{ changed: boolean; sessions_revoked: number }>('/api/auth/password', {
			current_password,
			new_password
		}),
	sessions: () => get<{ sessions: SessionRow[] }>('/api/auth/sessions'),
	revokeSession: (sessionId: string) => del<{ revoked: boolean }>(`/api/auth/sessions/${sessionId}`)
};

export const setupApi = {
	status: () => get<SetupStatus>('/api/setup/status'),
	run: (username: string, password: string) =>
		post<LoginResponse>('/api/setup', { username, password }, { silent401: true })
};
