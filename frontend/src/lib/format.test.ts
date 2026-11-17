import { describe, expect, it } from 'vitest';
import { format } from './format';

describe('format', () => {
	it('formats readings with their unit', () => {
		expect(format.watts(12.34)).toBe('12.3 W');
		expect(format.watts(0)).toBe('0.0 W');
		expect(format.watts(null)).toBe('--');
		expect(format.volts(219.6)).toBe('220 V');
		expect(format.amps(0.456)).toBe('0.46 A');
	});

	it('formats ages in Indonesian', () => {
		expect(format.age(5)).toBe('5 detik lalu');
		expect(format.age(120)).toBe('2 menit lalu');
		expect(format.age(7200)).toBe('2 jam lalu');
		expect(format.age(172800)).toBe('2 hari lalu');
		expect(format.age(null)).toBe('belum ada data');
	});

	it('formats bytes', () => {
		expect(format.bytes(512)).toBe('512 B');
		expect(format.bytes(2048)).toBe('2.0 KB');
		expect(format.bytes(5 * 1024 * 1024)).toBe('5.0 MB');
	});
});
