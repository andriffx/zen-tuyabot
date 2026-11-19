import { get, post, put } from './client';

export type BotMessage = {
	key: string;
	text: string;
	placeholders: string[];
	seed: string;
};

/** Groups keys by their prefix, so the editor mirrors four sections. */
export function groupByCategory(messages: BotMessage[]): Record<string, BotMessage[]> {
	const grouped: Record<string, BotMessage[]> = {};
	for (const message of messages) {
		const group = message.key.split('.')[0] ?? 'lain';
		(grouped[group] ??= []).push(message);
	}
	return grouped;
}

const LABELS: Record<string, string> = {
	menu: 'Label menu',
	btn: 'Label tombol',
	start: 'Sapaan',
	account: 'Akun',
	help: 'Bantuan',
	users: 'Daftar user',
	device: 'Perangkat',
	deny: 'Penolakan',
	control: 'Hasil kontrol',
	notify: 'Notifikasi otomatis'
};

export function categoryLabel(group: string): string {
	return LABELS[group] ?? group;
}

export const botMessagesApi = {
	list: () => get<{ messages: BotMessage[] }>('/api/bot-messages'),
	update: (key: string, text: string) => put<{ key: string; text: string }>(`/api/bot-messages/${key}`, { text }),
	preview: (key: string) => post<{ key: string; text: string }>(`/api/bot-messages/${key}/preview`)
};
