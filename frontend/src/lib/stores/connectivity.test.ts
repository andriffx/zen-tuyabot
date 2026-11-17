import { describe, expect, it } from 'vitest';
import { ApiError } from '#lib/api/errors';
import { connectivity } from './connectivity.svelte';

describe('connectivity', () => {
	it('an offline error flips it false and a success flips it true', () => {
		connectivity.setApiOnline(true);

		connectivity.observe(ApiError.offline());
		expect(connectivity.apiOnline).toBe(false);

		connectivity.observeSuccess();
		expect(connectivity.apiOnline).toBe(true);
	});

	it('a normal HTTP error does not mark the backend offline', () => {
		connectivity.setApiOnline(true);
		connectivity.observe(new ApiError(403, 'Tidak berizin'));
		expect(connectivity.apiOnline).toBe(true);
	});

	it('a 401 also leaves connectivity intact', () => {
		connectivity.setApiOnline(true);
		connectivity.observe(new ApiError(401, 'Tidak terautentikasi'));
		expect(connectivity.apiOnline).toBe(true);
	});
});
