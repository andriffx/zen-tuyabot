import { describe, expect, it } from 'vitest';
import { ApiError, toApiError } from './errors';

function jsonResponse(body: unknown, status = 400): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'content-type': 'application/json' }
	});
}

describe('toApiError', () => {
	it('reads field errors from the backend 422 shape', async () => {
		const error = await toApiError(
			jsonResponse({ detail: { errors: [{ key: 'name', message: 'wajib' }] } }, 422)
		);
		expect(error.status).toBe(422);
		expect(error.fieldErrors).toEqual([{ key: 'name', message: 'wajib' }]);
		expect(error.fieldError('name')).toBe('wajib');
	});

	it('reads the restore stage and message', async () => {
		const error = await toApiError(
			jsonResponse({ detail: { stage: 'version', message: 'lebih baru', maintenance: true } }, 422)
		);
		expect(error.stage).toBe('version');
		expect(error.detail).toBe('lebih baru');
	});

	it('uses a plain string detail', async () => {
		const error = await toApiError(jsonResponse({ detail: 'Tidak berizin' }, 403));
		expect(error.detail).toBe('Tidak berizin');
	});

	it('never turns an HTML error page into the message', async () => {
		const error = await toApiError(new Response('<html>502 Bad Gateway</html>', { status: 502 }));
		expect(error.status).toBe(502);
		expect(error.detail).not.toContain('<html>');
		expect(error.fieldErrors).toEqual([]);
	});

	it('flags setup_required and maintenance', async () => {
		const setup = await toApiError(jsonResponse({ detail: 'setup_required', setup_required: true }, 409));
		expect(setup.isSetupRequired).toBe(true);

		const maintenance = await toApiError(jsonResponse({ detail: 'maintenance', message: 'mt' }, 503));
		expect(maintenance.isMaintenance).toBe(true);
		expect(maintenance.detail).toBe('mt');
	});

	it('builds an offline error', () => {
		const offline = ApiError.offline();
		expect(offline.isOffline).toBe(true);
		expect(offline.status).toBe(0);
	});
});
