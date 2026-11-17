import type { StreamDevice, StreamSnapshot } from '#lib/api/types';

const MAX_BACKOFF_MS = 30_000;
const BASE_BACKOFF_MS = 1_000;

type Source = {
	onopen: (() => void) | null;
	onmessage: ((event: MessageEvent) => void) | null;
	onerror: (() => void) | null;
	close: () => void;
};

/**
 * Live device snapshots over SSE.
 *
 * Kept separate from API reachability on purpose: a dropped SSE stream with a
 * healthy API is a degraded badge, not an offline app.
 */
class StreamStore {
	devices = $state<Record<number, StreamDevice>>({});
	sseConnected = $state(false);
	lastUpdate = $state<number | null>(null);

	private source: Source | null = null;
	private timer: ReturnType<typeof setTimeout> | null = null;
	private attempt = 0;
	private stopped = true;

	start(): void {
		if (!this.stopped) return;
		this.stopped = false;
		this.connect();
	}

	stop(): void {
		this.stopped = true;
		if (this.timer !== null) {
			clearTimeout(this.timer);
			this.timer = null;
		}
		this.source?.close();
		this.source = null;
		this.sseConnected = false;
	}

	reset(): void {
		this.stop();
		this.devices = {};
		this.lastUpdate = null;
		this.attempt = 0;
	}

	private connect(): void {
		if (this.stopped) return;

		const source = new EventSource('/api/stream') as unknown as Source;
		this.source = source;

		source.onopen = () => {
			this.attempt = 0; // a successful connection resets the backoff ladder
			this.sseConnected = true;
		};

		source.onmessage = (event: MessageEvent) => {
			this.sseConnected = true;
			this.lastUpdate = Date.now();
			try {
				const snapshot = JSON.parse(event.data as string) as StreamSnapshot;
				const next: Record<number, StreamDevice> = {};
				for (const device of snapshot.devices ?? []) {
					next[device.id] = device;
				}
				this.devices = next;
			} catch {
				// A malformed frame is ignored; the next one will replace the snapshot.
			}
		};

		source.onerror = () => {
			this.sseConnected = false;
			source.close();
			this.source = null;
			this.scheduleReconnect();
		};
	}

	private scheduleReconnect(): void {
		if (this.stopped) return;
		const delay = Math.min(MAX_BACKOFF_MS, BASE_BACKOFF_MS * 2 ** this.attempt);
		this.attempt += 1;
		this.timer = setTimeout(() => {
			this.timer = null;
			this.connect();
		}, delay);
	}
}

export const stream = new StreamStore();
