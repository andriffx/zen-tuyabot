import { describe, expect, it } from 'vitest';
import { audit, createLogState } from './log-table';

describe('createLogState', () => {
	it('pages with a fixed size and stops at a short page', async () => {
		const calls: { limit: number; offset: number }[] = [];
		const fetcher = async (query: { limit: number; offset: number }) => {
			calls.push({ limit: query.limit, offset: query.offset });
			// A full page means "maybe more"; a short page means "this is the end".
			return {
				items:
					query.offset >= 50
						? []
						: Array.from({ length: query.limit }, (_, index) => ({ id: index }))
			};
		};
		const table = createLogState<{ id: number }>(50);

		await table.load(fetcher);
		expect(table.items).toHaveLength(50);
		expect(table.hasNext).toBe(true);

		await table.next(fetcher);
		expect(calls[1].offset).toBe(50);
		expect(table.items).toHaveLength(0);
		expect(table.hasNext).toBe(false);

		// next() at the end is a no-op, not another request.
		await table.next(fetcher);
		expect(calls).toHaveLength(2);
	});

	it('device filter resets to the first page', async () => {
		const calls: { offset: number; deviceId?: number }[] = [];
		const fetcher = async (query: { offset: number; deviceId?: number }) => {
			calls.push({ offset: query.offset, deviceId: query.deviceId });
			return { items: [{ id: 1 }] };
		};
		const table = createLogState<{ id: number }>(50);

		await table.load(fetcher);
		await table.next(fetcher);
		await table.setDevice(fetcher, 3);

		expect(calls.at(-1)).toEqual({ offset: 0, deviceId: 3 });
		expect(table.deviceId).toBe(3);
	});

	it('prev clamps at the first page', async () => {
		const calls: number[] = [];
		const fetcher = async (query: { offset: number }) => {
			calls.push(query.offset);
			return { items: [{ id: 1 }] };
		};
		const table = createLogState<{ id: number }>();
		await table.load(fetcher);
		await table.prev(fetcher);
		expect(calls).toEqual([0]);
	});

	it('surfaces a fetch failure without keeping stale rows', async () => {
		const fetcher = async () => {
			throw new Error('Gagal memuat data dari server');
		};
		const table = createLogState<{ id: number }>();
		await table.load(fetcher);
		expect(table.error).toBe('Gagal memuat data dari server');
		expect(table.items).toEqual([]);
	});
});

describe('audit.filters', () => {
	it('omits empty values and encodes the rest', () => {
		const params = audit.filters({
			result: 'denied',
			action: 'access.denied',
			actor_kind: '',
			limit: 50
		});
		expect(params.has('actor_kind')).toBe(false);
		expect(params.get('action')).toBe('access.denied');
		expect(params.get('result')).toBe('denied');
		expect(params.get('limit')).toBe('50');
	});

	it('keeps a date range', () => {
		const params = audit.filters({ since: '2026-11-01 00:00:00', until: '2026-11-18 23:59:59' });
		expect(params.get('since')).toBe('2026-11-01 00:00:00');
		expect(params.get('until')).toBe('2026-11-18 23:59:59');
	});
});
