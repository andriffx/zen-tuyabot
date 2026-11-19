import { describe, expect, it } from 'vitest';
import { categoryLabel, groupByCategory, type BotMessage } from './bot-messages';

const msg = (key: string): BotMessage => ({ key, text: 'x', placeholders: [], seed: 'x' });

describe('groupByCategory', () => {
	it('splits keys by their prefix', () => {
		const grouped = groupByCategory([msg('menu.air'), msg('deny.role'), msg('btn.turn_on')]);
		expect(grouped.menu).toHaveLength(1);
		expect(grouped.deny).toHaveLength(1);
		expect(grouped.btn).toHaveLength(1);
	});

	it('keeps every message in exactly one group', () => {
		const grouped = groupByCategory([msg('a.one'), msg('a.two'), msg('b.one')]);
		expect(grouped.a).toHaveLength(2);
		expect(grouped.b).toHaveLength(1);
	});
});

describe('categoryLabel', () => {
	it('names the known groups', () => {
		expect(categoryLabel('deny')).toBe('Penolakan');
		expect(categoryLabel('notify')).toBe('Notifikasi otomatis');
	});

	it('falls back to the prefix for an unknown group', () => {
		expect(categoryLabel('lain')).toBe('lain');
	});
});
