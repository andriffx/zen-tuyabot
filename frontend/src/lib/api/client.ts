import { ApiError, toApiError } from './errors';

export type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'DELETE';

export type ApiInit = {
	method?: HttpMethod;
	body?: unknown;
	/** Multipart body. Content-Type is left to the browser so it can add the boundary. */
	form?: FormData;
	signal?: AbortSignal;
	/** Suppress the global 401 handler (used by the auth hydrate path). */
	silent401?: boolean;
};

/** Paths whose 401 is an expected answer, not an expired session. */
const PUBLIC_401_PATHS = new Set(['/api/auth/login', '/api/auth/csrf', '/api/setup', '/api/setup/status']);

let csrfToken: string | null = null;
let unauthorizedHandler: (() => void) | null = null;
let maintenanceHandler: (() => void) | null = null;
let onlineHandler: ((online: boolean) => void) | null = null;

export function setCsrfToken(token: string | null): void {
	csrfToken = token;
}

export function onUnauthorized(handler: (() => void) | null): void {
	unauthorizedHandler = handler;
}

/** Fires when any protected request is answered with 503 maintenance. */
export function onMaintenance(handler: (() => void) | null): void {
	maintenanceHandler = handler;
}

/** Lets the connectivity store observe reachability without importing the client. */
export function onReachability(handler: ((online: boolean) => void) | null): void {
	onlineHandler = handler;
}

function isMutation(method: HttpMethod): boolean {
	return method !== 'GET';
}

function buildHeaders(init: ApiInit, method: HttpMethod): Record<string, string> {
	const headers: Record<string, string> = { Accept: 'application/json' };
	if (init.form) {
		// Deliberately no Content-Type: the browser adds the multipart boundary.
	} else if (init.body !== undefined) {
		headers['Content-Type'] = 'application/json';
	}
	if (isMutation(method) && csrfToken) {
		headers['X-CSRF-Token'] = csrfToken;
	}
	return headers;
}

export async function api<T>(path: string, init: ApiInit = {}): Promise<T> {
	const method = init.method ?? 'GET';
	const request: RequestInit = {
		method,
		credentials: 'same-origin',
		headers: buildHeaders(init, method),
		signal: init.signal
	};
	if (init.form) {
		request.body = init.form;
	} else if (init.body !== undefined) {
		request.body = JSON.stringify(init.body);
	}

	let response: Response;
	try {
		// Only the network call is inside this try. A malformed JSON body below
		// must never be reported as "backend offline".
		response = await fetch(path, request);
	} catch (error) {
		if ((error as Error)?.name === 'AbortError') {
			throw error;
		}
		onlineHandler?.(false);
		throw ApiError.offline();
	}

	onlineHandler?.(true);

	if (!response.ok) {
		const apiError = await toApiError(response);
		if (apiError.status === 401 && !init.silent401 && !PUBLIC_401_PATHS.has(path.split('?')[0])) {
			unauthorizedHandler?.();
		}
		if (apiError.isMaintenance) {
			maintenanceHandler?.();
		}
		if (apiError.isOffline) {
			onlineHandler?.(false);
		}
		throw apiError;
	}

	if (response.status === 204) {
		return undefined as T;
	}

	const contentType = response.headers.get('content-type') ?? '';
	if (!contentType.includes('application/json')) {
		return undefined as T;
	}

	try {
		return (await response.json()) as T;
	} catch {
		// A 200 with a broken body is not a connectivity failure.
		return undefined as T;
	}
}

export function get<T>(path: string, init: Omit<ApiInit, 'method'> = {}): Promise<T> {
	return api<T>(path, { ...init, method: 'GET' });
}

export function post<T>(path: string, body?: unknown, init: Omit<ApiInit, 'method' | 'body'> = {}): Promise<T> {
	return api<T>(path, { ...init, method: 'POST', body });
}

export function patch<T>(path: string, body?: unknown, init: Omit<ApiInit, 'method' | 'body'> = {}): Promise<T> {
	return api<T>(path, { ...init, method: 'PATCH', body });
}

export function del<T>(path: string, init: Omit<ApiInit, 'method'> = {}): Promise<T> {
	return api<T>(path, { ...init, method: 'DELETE' });
}

/** Stream a binary body to the user's disk (backup download). */
export async function download(path: string, filename: string): Promise<void> {
	const response = await fetch(path, { credentials: 'same-origin' });
	if (!response.ok) {
		throw await toApiError(response);
	}
	const blob = await response.blob();
	const url = URL.createObjectURL(blob);
	try {
		const anchor = document.createElement('a');
		anchor.href = url;
		anchor.download = filename;
		anchor.click();
	} finally {
		URL.revokeObjectURL(url);
	}
}
