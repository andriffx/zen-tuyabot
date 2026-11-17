<script lang="ts">
	import { onDestroy } from 'svelte';
	import { Button } from '#lib/components/ui/button';
	import {
		Dialog,
		DialogContent,
		DialogDescription,
		DialogHeader,
		DialogTitle
	} from '#lib/components/ui/dialog';
	import { Badge } from '#lib/components/ui/badge';
	import { devicesApi } from '#lib/api';
	import { ApiError } from '#lib/api/errors';
	import type { ScanCandidate } from '#lib/api/types';
	import { scan } from '#lib/scan';

	let {
		open = $bindable(false),
		onPick
	}: {
		open?: boolean;
		onPick: (candidate: ScanCandidate) => void;
	} = $props();

	let running = $state(false);
	let error = $state<string | null>(null);
	let candidates = $state<ScanCandidate[]>([]);
	let controller: AbortController | null = null;

	function abort() {
		controller?.abort();
		controller = null;
		running = false;
	}

	$effect(() => {
		// Closing the dialog must stop polling: the backend serves one scan at a time.
		if (!open) abort();
	});

	onDestroy(abort);

	async function start() {
		abort();
		controller = new AbortController();
		running = true;
		error = null;
		candidates = [];

		try {
			const found = await scan.run(
				() => devicesApi.scan(),
				(jobId, signal) => devicesApi.scanStatus(jobId, signal),
				{
					signal: controller.signal,
					onUpdate: (job) => {
						candidates = job.candidates;
					}
				}
			);
			candidates = found;
			if (found.length === 0) error = 'Tidak ada perangkat ditemukan di jaringan.';
		} catch (failure) {
			if ((failure as Error)?.name === 'AbortError') return;
			error =
				failure instanceof ApiError
					? failure.detail
					: (failure as Error)?.message ?? 'Scan gagal';
		} finally {
			running = false;
		}
	}
</script>

<Dialog bind:open>
	<DialogContent class="sm:max-w-2xl">
		<DialogHeader>
			<DialogTitle>Scan LAN</DialogTitle>
			<DialogDescription>
				Mencari perangkat Tuya di jaringan lokal. Local key tetap harus diisi manual.
			</DialogDescription>
		</DialogHeader>

		<div class="space-y-3">
			<Button onclick={start} disabled={running}>
				{running ? 'Memindai…' : candidates.length ? 'Scan ulang' : 'Mulai scan'}
			</Button>

			{#if error}
				<p class="text-sm text-destructive" role="alert">{error}</p>
			{/if}

			{#if candidates.length}
				<div class="max-h-72 overflow-auto rounded-md border">
					<table class="w-full text-sm">
						<thead class="bg-muted/50 text-left">
							<tr>
								<th class="p-2">IP</th>
								<th class="p-2">Tuya ID</th>
								<th class="p-2">Versi</th>
								<th class="p-2"></th>
							</tr>
						</thead>
						<tbody>
							{#each candidates as candidate (candidate.ip + (candidate.tuya_id ?? ''))}
								<tr class="border-t">
									<td class="p-2 font-mono text-xs">{candidate.ip}</td>
									<td class="p-2 font-mono text-xs">{candidate.tuya_id ?? '-'}</td>
									<td class="p-2"><Badge variant="outline">{candidate.version ?? '-'}</Badge></td>
									<td class="p-2 text-right">
										<Button
											size="sm"
											onclick={() => {
												onPick(candidate);
												open = false;
											}}
										>
											Gunakan
										</Button>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</div>
	</DialogContent>
</Dialog>
