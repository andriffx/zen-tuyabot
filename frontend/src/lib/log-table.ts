export type LogQuery = { limit: number; offset: number; deviceId?: number };

export type LogFetcher<T> = (query: LogQuery) => Promise<{ items: T[] }>;

/**
 * Pure pagination state machine shared by the three log pages.
 *
 * Deliberately rune-free so it can be unit-tested without a component and
 * reused from both `.ts` and `.svelte.ts` modules.
 */
export function createLogState<T>(limit = 50) {
	let items: T[] = [];
	let loading = false;
	let error: string | null = null;
	let hasNext = false;
	let offset = 0;
	let deviceId: number | null = null;

	return {
		get items() {
			return items;
		},
		get loading() {
			return loading;
		},
		get error() {
			return error;
		},
		get hasNext() {
			return hasNext;
		},
		get offset() {
			return offset;
		},
		get deviceId() {
			return deviceId;
		},
		get limit() {
			return limit;
		},

		async load(fetcher: LogFetcher<T>): Promise<void> {
			loading = true;
			error = null;
			try {
				const response = await fetcher({
					limit,
					offset,
					...(deviceId !== null ? { deviceId } : {})
				});
				items = response.items;
				// A full page may have more; a short page is the end.
				hasNext = response.items.length === limit;
			} catch (failure) {
				error = failure instanceof Error ? failure.message : 'Gagal memuat data';
				items = [];
				hasNext = false;
			} finally {
				loading = false;
			}
		},

		async next(fetcher: LogFetcher<T>): Promise<void> {
			if (!hasNext) return;
			offset += limit;
			await this.load(fetcher);
		},

		async prev(fetcher: LogFetcher<T>): Promise<void> {
			if (offset === 0) return;
			offset = Math.max(0, offset - limit);
			await this.load(fetcher);
		},

		async setDevice(fetcher: LogFetcher<T>, nextDeviceId: number | null): Promise<void> {
			deviceId = nextDeviceId;
			offset = 0;
			await this.load(fetcher);
		}
	};
}

export type LogState<T> = ReturnType<typeof createLogState<T>>;

export type AuditQuery = {
	actor_kind?: string;
	action?: string;
	result?: string;
	target_kind?: string;
	since?: string;
	until?: string;
	limit?: number;
	offset?: number;
};

/** Build the query string the backend accepts, skipping empty values. */
export const audit = {
	filters(query: AuditQuery): URLSearchParams {
		const params = new URLSearchParams();
		for (const [key, value] of Object.entries(query)) {
			if (value === undefined || value === null || value === '') continue;
			params.set(key, String(value));
		}
		return params;
	}
};
