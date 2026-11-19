import { beforeEach, describe, expect, it, vi } from 'vitest';
import { authApi } from '#lib/api';
import { ApiError } from '#lib/api/errors';
import { auth } from './auth.svelte';

const me = {
	id: 1,
	username: 'root',
	actor_kind: 'web' as const,
	role: { id: 1, slug: 'superadmin', name: 'Superadmin' },
	permissions: ['monitoring', 'manage_devices'],
	csrf_token: 'tok-1'
};

beforeEach(() => {
	auth.reset();
	vi.restoreAllMocks();
});

describe('auth.hydrate', () => {
	it('stores me, csrf and permissions', async () => {
		vi.spyOn(authApi, 'me').mockResolvedValue(me);
		expect(await auth.hydrate()).toBe('ready');
		expect(auth.me?.username).toBe('root');
		expect(auth.can('monitoring')).toBe(true);
		expect(auth.can('manage_users')).toBe(false);
		expect(auth.canAny('manage_users', 'monitoring')).toBe(true);
	});

	it('maps every failure to an outcome', async () => {
		const spy = vi.spyOn(authApi, 'me');
		spy.mockRejectedValueOnce(new ApiError(409, 'setup_required', [], { isSetupRequired: true }));
		expect(await auth.hydrate()).toBe('setup');

		spy.mockRejectedValueOnce(new ApiError(503, 'maintenance', [], { isMaintenance: true }));
		expect(await auth.hydrate()).toBe('maintenance');

		spy.mockRejectedValueOnce(new ApiError(401, 'Tidak terautentikasi'));
		expect(await auth.hydrate()).toBe('login');

		spy.mockRejectedValueOnce(ApiError.offline());
		expect(await auth.hydrate()).toBe('offline');
		expect(auth.error).toBeTruthy();
	});

	it('clears stale state after a 401 so admin screens cannot linger', async () => {
		vi.spyOn(authApi, 'me').mockResolvedValueOnce(me);
		await auth.hydrate();
		expect(auth.can('monitoring')).toBe(true);

		vi.spyOn(authApi, 'me').mockRejectedValueOnce(new ApiError(401, 'x'));
		expect(await auth.hydrate()).toBe('login');
		expect(auth.me).toBeNull();
		expect(auth.can('monitoring')).toBe(false);
	});
});

describe('auth.login', () => {
	it('sets the csrf token from the login response before hydrating', async () => {
		vi.spyOn(authApi, 'login').mockResolvedValue({
			authenticated: true,
			user_id: 1,
			csrf_token: 'tok-2'
		});
		vi.spyOn(authApi, 'me').mockResolvedValue({ ...me, csrf_token: 'tok-2' });

		await auth.login('root', 'password-panjang');
		expect(auth.me?.username).toBe('root');
		expect(auth.can('monitoring')).toBe(true);
	});
});

describe('auth.refresh', () => {
	it('replaces permissions without a reload', async () => {
		vi.spyOn(authApi, 'me').mockResolvedValueOnce(me);
		await auth.hydrate();

		vi.spyOn(authApi, 'me').mockResolvedValueOnce({ ...me, permissions: ['view_logs'] });
		await auth.refresh();
		expect(auth.can('monitoring')).toBe(false);
		expect(auth.can('view_logs')).toBe(true);
	});

	it('does nothing when there is no session', async () => {
		const spy = vi.spyOn(authApi, 'me');
		await auth.refresh();
		expect(spy).not.toHaveBeenCalled();
	});

	it('drops state when the session died', async () => {
		vi.spyOn(authApi, 'me').mockResolvedValueOnce(me);
		await auth.hydrate();
		vi.spyOn(authApi, 'me').mockRejectedValueOnce(new ApiError(401, 'x'));
		await auth.refresh();
		expect(auth.me).toBeNull();
	});
});

describe('auth.logout', () => {
	it('clears state even when the request fails', async () => {
		vi.spyOn(authApi, 'me').mockResolvedValueOnce(me);
		await auth.hydrate();
		vi.spyOn(authApi, 'logout').mockRejectedValueOnce(ApiError.offline());
		await expect(auth.logout()).rejects.toMatchObject({ isOffline: true });
		expect(auth.me).toBeNull();
	});
});
