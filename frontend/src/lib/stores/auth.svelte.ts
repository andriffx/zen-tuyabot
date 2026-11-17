import { setCsrfToken } from '#lib/api';
import { authApi, setupApi } from '#lib/api';
import { ApiError } from '#lib/api/errors';
import type { AuthMe } from '#lib/api/types';
import type { HydrateOutcome } from '#lib/guard';

/**
 * Auth state for the SPA.
 *
 * `me` is null whenever the caller is not authenticated; keeping a stale
 * `me` after a 401 would leave admin actions on screen.
 */
class AuthStore {
	me = $state<AuthMe | null>(null);
	loading = $state(false);
	error = $state<string | null>(null);

	reset(): void {
		this.me = null;
		this.error = null;
		setCsrfToken(null);
	}

	can(permission: string): boolean {
		return this.me?.permissions.includes(permission) ?? false;
	}

	canAny(...permissions: string[]): boolean {
		return permissions.some((permission) => this.can(permission));
	}

	async hydrate(): Promise<HydrateOutcome> {
		this.loading = true;
		try {
			const me = await authApi.me();
			this.me = me;
			this.error = null;
			setCsrfToken(me.csrf_token);
			return 'ready';
		} catch (error: unknown) {
			this.me = null;
			setCsrfToken(null);

			if (error instanceof ApiError) {
				if (error.isSetupRequired) return 'setup';
				if (error.isMaintenance) return 'maintenance';
				if (error.isOffline || error.status === 0) {
					this.error = error.detail;
					return 'offline';
				}
				if (error.status === 401) return 'login';
				this.error = error.detail;
				return 'offline';
			}

			this.error = 'Terjadi kesalahan tak terduga';
			return 'offline';
		} finally {
			this.loading = false;
		}
	}

	async login(username: string, password: string): Promise<void> {
		const response = await authApi.login(username, password);
		setCsrfToken(response.csrf_token);
		await this.hydrate();
	}

	async setup(username: string, password: string): Promise<void> {
		const response = await setupApi.run(username, password);
		setCsrfToken(response.csrf_token);
		await this.hydrate();
	}

	async logout(): Promise<void> {
		try {
			await authApi.logout();
		} finally {
			this.reset();
		}
	}

	/** Re-read /me so permission changes take effect without a re-login. */
	async refresh(): Promise<void> {
		if (!this.me) return;
		try {
			const me = await authApi.me();
			this.me = me;
			setCsrfToken(me.csrf_token);
		} catch (error) {
			if (error instanceof ApiError && error.status === 401) {
				this.reset();
			}
		}
	}
}

export const auth = new AuthStore();
