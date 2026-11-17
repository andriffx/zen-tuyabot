import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api, download, onReachability, onUnauthorized, setCsrfToken } from './client';

function mockFetch(response: Response) {
	const spy = vi.fn().mockResolvedValue(response);
	vi.stubGlobal('fetch', spy);
	return spy;
}

function json(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'content-type': 'application/json' }
	});
}

beforeEach(() => {
	setCsrfToken(null);
	onUnauthorized(null);
	onReachability(null);
});

afterEach(() => vi.unstubAllGlobals());

describe('api', () => {
	it('sends credentials and the csrf header on mutations', async () => {
		const spy = mockFetch(json({}));
		setCsrfToken('abc');
		await api('/api/devices', { method: 'POST', body: { name: 'x' } });
		const [url, init] = spy.mock.calls[0];
		expect(url).toBe('/api/devices');
		expect(init.credentials).toBe('same-origin');
		expect(init.headers['X-CSRF-Token']).toBe('abc');
		expect(init.headers['Content-Type']).toBe('application/json');
		expect(init.body).toBe('{"name":"x"}');
	});

	it('omits the csrf header on GET', async () => {
		const spy = mockFetch(json({}));
		setCsrfToken('abc');
		await api('/api/devices');
		expect(spy.mock.calls[0][1].headers['X-CSRF-Token']).toBeUndefined();
	});

	it('leaves Content-Type to the browser for FormData', async () => {
		const spy = mockFetch(json({}));
		setCsrfToken('abc');
		const form = new FormData();
		await api('/api/backup/restore', { method: 'POST', form });
		const init = spy.mock.calls[0][1];
		expect(init.body).toBe(form);
		expect(init.headers['Content-Type']).toBeUndefined();
		expect(init.headers['X-CSRF-Token']).toBe('abc');
	});

	it('returns undefined for empty bodies and non-JSON successes', async () => {
		mockFetch(new Response(null, { status: 204 }));
		await expect(api('/api/x', { method: 'DELETE' })).resolves.toBeUndefined();

		mockFetch(new Response('{not json', { status: 200 }));
		await expect(api('/api/devices')).resolves.toBeUndefined();
	});

	it('maps a fetch rejection to offline', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
		);
		await expect(api('/api/devices')).rejects.toMatchObject({ isOffline: true, status: 0 });
	});

	it('rethrows abort instead of reporting it as offline', async () => {
		const abort = Object.assign(new Error('aborted'), { name: 'AbortError' });
		vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abort));
		await expect(api('/api/devices')).rejects.toMatchObject({ name: 'AbortError' });
	});

	it('calls the 401 handler for protected routes on GET and mutations', async () => {
		const handler = vi.fn();
		onUnauthorized(handler);
		mockFetch(json({ detail: 'Tidak terautentikasi' }, 401));
		await expect(api('/api/settings')).rejects.toMatchObject({ status: 401 });
		await expect(api('/api/devices', { method: 'POST', body: {} })).rejects.toMatchObject({
			status: 401
		});
		expect(handler).toHaveBeenCalledTimes(2);
	});

	it('does not call the 401 handler for login, setup or csrf', async () => {
		const handler = vi.fn();
		onUnauthorized(handler);
		mockFetch(json({ detail: 'salah' }, 401));
		for (const path of ['/api/auth/login', '/api/setup', '/api/auth/csrf', '/api/setup/status']) {
			await expect(api(path, { method: 'POST', body: {} })).rejects.toMatchObject({ status: 401 });
		}
		expect(handler).not.toHaveBeenCalled();
	});

	it('honours silent401', async () => {
		const handler = vi.fn();
		onUnauthorized(handler);
		mockFetch(json({ detail: 'x' }, 401));
		await expect(api('/api/auth/me', { silent401: true })).rejects.toMatchObject({ status: 401 });
		expect(handler).not.toHaveBeenCalled();
	});

	it('reports reachability to the observer', async () => {
		const observed: boolean[] = [];
		onReachability((online) => observed.push(online));

		mockFetch(json({}));
		await api('/api/devices');
		expect(observed).toEqual([true]);

		vi.stubGlobal(
			'fetch',
			vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
		);
		await expect(api('/api/devices')).rejects.toBeTruthy();
		expect(observed).toEqual([true, false]);
	});
});

describe('download', () => {
	it('streams through a blob url and revokes it', async () => {
		const spy = mockFetch(new Response(new Blob(['d']), { status: 200 }));
		const createObjectURL = vi.fn().mockReturnValue('blob:x');
		const revokeObjectURL = vi.fn();
		vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL });
		const click = vi.fn();
		vi.spyOn(document, 'createElement').mockReturnValue({ click, href: '', download: '' } as never);

		await download('/api/backup/1/download', 'a.db');

		expect(spy.mock.calls[0][1].credentials).toBe('same-origin');
		expect(createObjectURL).toHaveBeenCalled();
		expect(click).toHaveBeenCalled();
		expect(revokeObjectURL).toHaveBeenCalledWith('blob:x');
	});

	it('throws a normalized error on failure', async () => {
		mockFetch(json({ detail: 'Tidak berizin' }, 403));
		await expect(download('/api/backup/1/download', 'a.db')).rejects.toMatchObject({ status: 403 });
	});
});
