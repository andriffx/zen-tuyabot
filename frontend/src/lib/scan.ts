import type { ScanCandidate, ScanJob } from '#lib/api/types';

export type ScanOptions = {
	signal?: AbortSignal;
	onUpdate?: (job: ScanJob) => void;
	intervalMs?: number;
	timeoutMs?: number;
};

function abortError(): Error {
	const error = new Error('Scan dibatalkan');
	error.name = 'AbortError';
	return error;
}

function wait(ms: number, signal?: AbortSignal): Promise<void> {
	return new Promise((resolve, reject) => {
		if (signal?.aborted) {
			reject(abortError());
			return;
		}
		const timer = setTimeout(() => {
			signal?.removeEventListener('abort', onAbort);
			resolve();
		}, ms);
		const onAbort = () => {
			clearTimeout(timer);
			reject(abortError());
		};
		signal?.addEventListener('abort', onAbort, { once: true });
	});
}

/**
 * Run a LAN scan and poll until it finishes.
 *
 * Aborting is first-class: closing the dialog must stop the polling, because a
 * scan keeps the backend's single scan slot busy until it completes.
 */
export const scan = {
	async run(
		start: () => Promise<{ job_id: string; status: string }>,
		poll: (jobId: string, signal?: AbortSignal) => Promise<ScanJob>,
		options: ScanOptions = {}
	): Promise<ScanCandidate[]> {
		const { signal, onUpdate, intervalMs = 1500, timeoutMs = 90_000 } = options;
		const started = await start();
		const deadline = Date.now() + timeoutMs;

		for (;;) {
			if (signal?.aborted) throw abortError();

			const job = await poll(started.job_id, signal);
			onUpdate?.(job);

			if (job.status === 'done') return job.candidates;
			if (job.status === 'error') throw new Error(job.error ?? 'Scan gagal');

			if (Date.now() >= deadline) throw new Error('Scan melewati batas waktu');
			await wait(intervalMs, signal);
		}
	}
};
