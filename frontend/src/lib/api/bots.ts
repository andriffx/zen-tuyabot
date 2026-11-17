import { del, get, patch, post } from './client';
import type { Bot, BotTestResult } from './types';

export type BotPayload = { label?: string; token?: string; enabled?: boolean };

export const botsApi = {
	list: () => get<{ bots: Bot[] }>('/api/bots'),
	create: (label: string, token: string) => post<Bot>('/api/bots', { label, token }),
	update: (id: number, payload: BotPayload) => patch<Bot>(`/api/bots/${id}`, payload),
	enable: (id: number) => post<{ status: string }>(`/api/bots/${id}/enable`),
	disable: (id: number) => post<{ status: string }>(`/api/bots/${id}/disable`),
	test: (id: number) => post<BotTestResult>(`/api/bots/${id}/test`),
	remove: (id: number) => del<{ deleted: boolean }>(`/api/bots/${id}`)
};
