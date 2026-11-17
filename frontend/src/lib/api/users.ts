import { del, get, patch, post } from './client';
import type { TelegramUser, WebUser } from './types';

export type WebUserPayload = {
	username?: string;
	password?: string;
	role_id?: number;
	is_active?: boolean;
};

export const usersApi = {
	list: () => get<{ users: WebUser[] }>('/api/web-users'),
	create: (payload: { username: string; password: string; role_id: number }) =>
		post<WebUser>('/api/web-users', payload),
	update: (id: number, payload: WebUserPayload) => patch<WebUser>(`/api/web-users/${id}`, payload),
	remove: (id: number) => del<{ deleted: boolean }>(`/api/web-users/${id}`)
};

export type TelegramUserPayload = {
	telegram_id?: number;
	label?: string | null;
	role_id?: number;
	is_active?: boolean;
};

export const telegramUsersApi = {
	list: () => get<{ telegram_users: TelegramUser[] }>('/api/telegram-users'),
	create: (payload: { telegram_id: number; label?: string | null; role_id: number }) =>
		post<TelegramUser>('/api/telegram-users', payload),
	update: (telegramId: number, payload: TelegramUserPayload) =>
		patch<TelegramUser>(`/api/telegram-users/${telegramId}`, payload),
	remove: (telegramId: number) => del<{ deleted: boolean }>(`/api/telegram-users/${telegramId}`)
};
