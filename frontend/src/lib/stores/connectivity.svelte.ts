import { onReachability } from '#lib/api';
import type { ApiError } from '#lib/api/errors';

/**
 * Backend API reachability.
 *
 * Distinct from `stream.sseConnected`: the API can be perfectly healthy while
 * the live stream is reconnecting.
 */
class ConnectivityStore {
	apiOnline = $state(true);

	setApiOnline(online: boolean): void {
		this.apiOnline = online;
	}

	observe(error: ApiError): void {
		if (error.isOffline || error.status === 0) {
			this.apiOnline = false;
		}
	}

	observeSuccess(): void {
		this.apiOnline = true;
	}

	/** Wire the API client so every request updates this store. */
	attach(): () => void {
		onReachability((online) => this.setApiOnline(online));
		return () => onReachability(null);
	}
}

export const connectivity = new ConnectivityStore();
