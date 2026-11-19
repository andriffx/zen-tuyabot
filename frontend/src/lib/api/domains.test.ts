import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
	backupApi,
	botsApi,
	devicesApi,
	logsApi,
	rolesApi,
	systemApi,
	telegramUsersApi
} from './index';

const client = vi.hoisted(() => ({
	api: vi.fn(),
	get: vi.fn(),
	post: vi.fn(),
	patch: vi.fn(),
	del: vi.fn(),
	download: vi.fn(),
	setCsrfToken: vi.fn()
}));

vi.mock('./client', () => client);

beforeEach(() => {
	for (const fn of Object.values(client)) fn.mockReset();
	for (const fn of [client.api, client.get, client.post, client.patch, client.del, client.download]) {
		fn.mockResolvedValue({});
	}
});

describe('domain modules hit the documented endpoints', () => {
	it('telegram users use their own path and integer id', async () => {
		await telegramUsersApi.remove(555);
		expect(client.del).toHaveBeenCalledWith('/api/telegram-users/555');

		await telegramUsersApi.update(555, { role_id: 2 });
		expect(client.patch).toHaveBeenCalledWith('/api/telegram-users/555', { role_id: 2 });
	});

	it('bots expose enable, disable and test', async () => {
		await botsApi.enable(2);
		expect(client.post).toHaveBeenCalledWith('/api/bots/2/enable');
		await botsApi.disable(2);
		expect(client.post).toHaveBeenCalledWith('/api/bots/2/disable');
		await botsApi.test(2);
		expect(client.post).toHaveBeenCalledWith('/api/bots/2/test');
	});

	it('roles use the catalog endpoint', async () => {
		await rolesApi.catalog();
		expect(client.get).toHaveBeenCalledWith('/api/roles/permissions');
	});

	it('devices scan polls by job id', async () => {
		await devicesApi.scanStatus('ab12');
		expect(client.get).toHaveBeenCalledWith('/api/devices/scan/ab12', { signal: undefined });
	});

	it('backup restore posts a multipart body through api()', async () => {
		const form = new FormData();
		await backupApi.restore(form);
		expect(client.api).toHaveBeenCalledWith('/api/backup/restore', { method: 'POST', form });
	});

	it('logs build query strings and omit undefined filters', async () => {
		await logsApi.activities({ limit: 50, offset: 0, deviceId: 3 });
		expect(client.get).toHaveBeenCalledWith('/api/logs/activities?limit=50&offset=0&device_id=3');

		await logsApi.errors({ limit: 10 });
		expect(client.get).toHaveBeenCalledWith('/api/logs/errors?limit=10');
	});

	it('audit omits empty filters', async () => {
		await systemApi.audit({ result: 'denied', action: '', limit: 50 });
		expect(client.get).toHaveBeenCalledWith('/api/audit?result=denied&limit=50');
	});
});
