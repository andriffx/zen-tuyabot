import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { connectivity } from './connectivity.svelte';
import { stream } from './stream.svelte';

class FakeEventSource {
	static instances: FakeEventSource[] = [];
	onopen: (() => void) | null = null;
	onmessage: ((event: MessageEvent) => void) | null = null;
	onerror: (() => void) | null = null;
	constructor(public url: string) {
		FakeEventSource.instances.push(this);
	}
	close() {}
}

beforeEach(() => {
	vi.useFakeTimers();
	vi.stubGlobal('EventSource', FakeEventSource);
	stream.reset();
	connectivity.setApiOnline(true);
});

afterEach(() => {
	vi.useRealTimers();
	vi.unstubAllGlobals();
	FakeEventSource.instances = [];
});

function frame(payload: unknown): MessageEvent {
	return { data: JSON.stringify(payload) } as MessageEvent;
}

describe('stream', () => {
	it('keys devices by id', () => {
		stream.start();
		FakeEventSource.instances[0].onmessage?.(
			frame({ ts: 1, devices: [{ id: 7, name: 'pompa', online: true, power_w: 12 }] })
		);
		expect(stream.devices[7].name).toBe('pompa');
		expect(stream.sseConnected).toBe(true);
	});

	it('marks connected on open', () => {
		stream.start();
		FakeEventSource.instances[0].onopen?.();
		expect(stream.sseConnected).toBe(true);
	});

	it('grows the backoff, caps it, and resets after a successful open', () => {
		stream.start();
		FakeEventSource.instances[0].onerror?.();
		expect(stream.sseConnected).toBe(false);

		vi.advanceTimersByTime(1000);
		expect(FakeEventSource.instances).toHaveLength(2);

		FakeEventSource.instances[1].onerror?.();
		vi.advanceTimersByTime(1999);
		expect(FakeEventSource.instances).toHaveLength(2);
		vi.advanceTimersByTime(1);
		expect(FakeEventSource.instances).toHaveLength(3);

		FakeEventSource.instances[2].onopen?.();
		FakeEventSource.instances[2].onerror?.();
		vi.advanceTimersByTime(1000);
		expect(FakeEventSource.instances).toHaveLength(4);
	});

	it('stop cancels a pending reconnect', () => {
		stream.start();
		FakeEventSource.instances[0].onerror?.();
		stream.stop();
		vi.advanceTimersByTime(120_000);
		expect(FakeEventSource.instances).toHaveLength(1);
		expect(stream.sseConnected).toBe(false);
	});

	it('an sse failure never marks the api offline', () => {
		stream.start();
		FakeEventSource.instances[0].onerror?.();
		expect(connectivity.apiOnline).toBe(true);
	});

	it('ignores malformed frames without dropping the connection state', () => {
		stream.start();
		FakeEventSource.instances[0].onopen?.();
		FakeEventSource.instances[0].onmessage?.({ data: '{bukan json' } as MessageEvent);
		expect(stream.devices).toEqual({});
		expect(stream.sseConnected).toBe(true);
	});
});
