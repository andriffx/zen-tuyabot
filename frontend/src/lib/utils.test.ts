import { describe, expect, it } from 'vitest';
import { cn } from './utils';

describe('cn', () => {
	it('joins truthy classes and drops falsy ones', () => {
		expect(cn('a', false && 'b', undefined, 'c')).toBe('a c');
	});

	it('lets a later tailwind class win', () => {
		expect(cn('p-2', 'p-4')).toBe('p-4');
	});
});
