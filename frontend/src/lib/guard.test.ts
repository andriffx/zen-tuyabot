import { describe, expect, it } from 'vitest';
import { outcomeToLocation } from './guard';

describe('outcomeToLocation', () => {
	it('sends anonymous users to login except on public pages', () => {
		expect(outcomeToLocation('login', '/devices')).toEqual({ redirect: '/login' });
		expect(outcomeToLocation('login', '/login')).toEqual({});
		expect(outcomeToLocation('login', '/setup')).toEqual({});
	});

	it('sends everyone to setup until it is complete', () => {
		expect(outcomeToLocation('setup', '/login')).toEqual({ redirect: '/setup' });
		expect(outcomeToLocation('setup', '/setup')).toEqual({});
		expect(outcomeToLocation('setup', '/devices')).toEqual({ redirect: '/setup' });
	});

	it('renders screens instead of redirecting for maintenance and offline', () => {
		expect(outcomeToLocation('maintenance', '/devices')).toEqual({ render: 'maintenance' });
		expect(outcomeToLocation('maintenance', '/login')).toEqual({});
		expect(outcomeToLocation('offline', '/devices')).toEqual({ render: 'offline' });
		expect(outcomeToLocation('offline', '/setup')).toEqual({ render: 'offline' });
	});

	it('keeps /system reachable during maintenance so the operator can turn it off', () => {
		expect(outcomeToLocation('maintenance', '/system')).toEqual({});
		expect(outcomeToLocation('maintenance', '/devices')).toEqual({ render: 'maintenance' });
	});

	it('lets a ready user through', () => {
		expect(outcomeToLocation('ready', '/devices')).toEqual({});
	});
});
