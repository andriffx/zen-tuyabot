export type HydrateOutcome = 'ready' | 'login' | 'setup' | 'maintenance' | 'offline';

export type GuardDecision = { redirect?: string; render?: 'offline' | 'maintenance' };

const PUBLIC_PATHS = new Set(['/login', '/setup']);

/**
 * Decide what to do with the current location after hydration.
 *
 * Maintenance and offline render a screen instead of redirecting: the operator
 * may still have the URL bookmarked, and a redirect would hide why the app
 * refuses to work.
 */
export function outcomeToLocation(outcome: HydrateOutcome, pathname: string): GuardDecision {
	const isPublic = PUBLIC_PATHS.has(pathname);

	switch (outcome) {
		case 'ready':
			return {};
		case 'login':
			return isPublic ? {} : { redirect: '/login' };
		case 'setup':
			return pathname === '/setup' ? {} : { redirect: '/setup' };
		case 'maintenance':
			return isPublic ? {} : { render: 'maintenance' };
		case 'offline':
			return { render: 'offline' };
	}
}
