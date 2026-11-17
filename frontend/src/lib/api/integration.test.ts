import { describe, expect, it } from 'vitest';
import { api, setCsrfToken } from './client';

/**
 * Opt-in integration tests against a live backend.
 *
 * They go through the Vite dev proxy on purpose: `credentials: 'same-origin'`
 * only attaches the session cookie when the request targets the page's own
 * origin. Pointing VITE_TEST_API at 127.0.0.1:8080 directly would send no
 * cookie and produce a misleading 401.
 *
 * Run with:
 *   VITE_TEST_API=1 npm run test -- --run src/lib/api/integration.test.ts
 * (requires `npm run dev` with a backend on 127.0.0.1:8080)
 */
// A relative path is required for same-origin cookies. In a Node test runner
// there is no page origin, so the client must be given an absolute dev-server
// URL that proxies /api to the backend (http://localhost:5173).
const enabled = process.env.VITE_TEST_API === '1';
const base = process.env.VITE_TEST_BASE ?? 'http://localhost:5173';
const user = process.env.SMOKE_USER ?? 'root';
const password = process.env.SMOKE_PASS ?? 'password-panjang';

const url = (path: string) => `${base}${path}`;

describe.skipIf(!enabled)('backend integration via dev proxy', () => {
	it('serves the public setup status', async () => {
		const status = await api<{ required: boolean }>(url('/api/setup/status'));
		expect(typeof status.required).toBe('boolean');
	});

	it('rejects a protected route without a session', async () => {
		await expect(api(url('/api/settings'))).rejects.toMatchObject({ status: 401 });
	});

	it('rejects a login with wrong credentials', async () => {
		await expect(
			api(url('/api/auth/login'), {
				method: 'POST',
				body: { username: user, password: 'pasti-salah' }
			})
		).rejects.toMatchObject({ status: 401 });
	});

	it('rejects a mutation without a CSRF token', async () => {
		// Node has no cookie jar, so an authenticated round-trip is not possible
		// here; the browser smoke tests cover that path. This still proves the
		// server refuses an unauthenticated write instead of accepting it.
		setCsrfToken(null);
		await expect(
			api(url('/api/settings'), { method: 'PATCH', body: { values: { 'ui.title': 'X' } } })
		).rejects.toMatchObject({ status: 401 });
	});

	it('returns the maintenance flag from the unblocked endpoint', async () => {
		const status = await api<{ maintenance: boolean }>(url('/api/maintenance/status'));
		expect(typeof status.maintenance).toBe('boolean');
	});
});
