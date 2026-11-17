import { describe, expect, it } from 'vitest';
import type { ScanJob } from '#lib/api/types';
import { scan } from './scan';

function job(status: ScanJob['status'], candidates: ScanJob['candidates'] = []): ScanJob {
	return { job_id: 'j1', status, candidates, error: null };
}

describe('scan.run', () => {
	it('polls until done and returns the candidates', async () => {
		let polls = 0;
		const candidates = [
			{ ip: '10.0.0.9', tuya_id: 'x', version: 3.5, product_key: 'p', name: 'Lampu' }
		];
		const result = await scan.run(
			async () => ({ job_id: 'j1', status: 'running' }),
			async () => {
				polls += 1;
				return polls < 2 ? job('running') : job('done', candidates);
			},
			{ intervalMs: 1 }
		);
		expect(polls).toBe(2);
		expect(result).toEqual(candidates);
	});

	it('reports a scan error with the backend message', async () => {
		await expect(
			scan.run(
				async () => ({ job_id: 'j1', status: 'running' }),
				async () => ({ ...job('error'), error: 'jaringan tidak mendukung' }),
				{ intervalMs: 1 }
			)
		).rejects.toThrow('jaringan tidak mendukung');
	});

	it('times out rather than polling forever', async () => {
		await expect(
			scan.run(
				async () => ({ job_id: 'j1', status: 'running' }),
				async () => job('running'),
				{ intervalMs: 1, timeoutMs: 15 }
			)
		).rejects.toThrow('batas waktu');
	});

	it('stops polling as soon as the controller aborts', async () => {
		const controller = new AbortController();
		let polls = 0;
		const promise = scan.run(
			async () => ({ job_id: 'j1', status: 'running' }),
			async () => {
				polls += 1;
				return job('running');
			},
			{ signal: controller.signal, intervalMs: 10, timeoutMs: 5000 }
		);
		setTimeout(() => controller.abort(), 25);

		await expect(promise).rejects.toMatchObject({ name: 'AbortError' });
		const seen = polls;
		await new Promise((resolve) => setTimeout(resolve, 60));
		expect(polls).toBe(seen);
	});

	it('refuses to start when already aborted', async () => {
		const controller = new AbortController();
		controller.abort();
		await expect(
			scan.run(
				async () => ({ job_id: 'j1', status: 'running' }),
				async () => job('running'),
				{ signal: controller.signal }
			)
		).rejects.toMatchObject({ name: 'AbortError' });
	});
});
