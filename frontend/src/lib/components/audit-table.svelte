<script lang="ts">
	import { Badge } from '#lib/components/ui/badge';
	import { Button } from '#lib/components/ui/button';
	import { Input } from '#lib/components/ui/input';
	import { Skeleton } from '#lib/components/ui/skeleton';
	import {
		Table,
		TableBody,
		TableCell,
		TableHead,
		TableHeader,
		TableRow
	} from '#lib/components/ui/table';
	import { systemApi } from '#lib/api';
	import type { AuditEntry } from '#lib/api/types';
	import { format } from '#lib/format';
	import { onMount } from 'svelte';
	import { ChevronLeft, ChevronRight, RefreshCw } from '@lucide/svelte';

	let entries = $state<AuditEntry[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let offset = $state(0);
	let hasNext = $state(false);
	const limit = 50;

	let result = $state('');
	let action = $state('');
	let actorKind = $state('');
	let detail = $state<AuditEntry | null>(null);

	const resultOptions = ['', 'ok', 'denied', 'error'];
	const actorOptions = ['', 'web', 'telegram', 'api_key', 'system'];

	async function load() {
		loading = true;
		error = null;
		try {
			const response = await systemApi.audit({
				limit,
				offset,
				result: result || undefined,
				action: action || undefined,
				actor_kind: actorKind || undefined
			});
			entries = response.items;
			hasNext = response.items.length === limit;
		} catch (failure) {
			error = failure instanceof Error ? failure.message : 'Gagal memuat audit log';
			entries = [];
			hasNext = false;
		} finally {
			loading = false;
		}
	}

	function applyFilters() {
		offset = 0;
		void load();
	}

	onMount(load);
</script>

<div class="space-y-3">
	<div class="flex flex-wrap items-end gap-2">
		<label class="flex flex-col gap-1 text-xs">
			<span class="text-muted-foreground">Hasil</span>
			<select
				class="h-8 rounded-md border border-input bg-transparent px-2 text-sm"
				bind:value={result}
				onchange={applyFilters}
			>
				{#each resultOptions as option (option)}
					<option value={option}>{option || 'semua'}</option>
				{/each}
			</select>
		</label>

		<label class="flex flex-col gap-1 text-xs">
			<span class="text-muted-foreground">Aktor</span>
			<select
				class="h-8 rounded-md border border-input bg-transparent px-2 text-sm"
				bind:value={actorKind}
				onchange={applyFilters}
			>
				{#each actorOptions as option (option)}
					<option value={option}>{option || 'semua'}</option>
				{/each}
			</select>
		</label>

		<label class="flex flex-col gap-1 text-xs">
			<span class="text-muted-foreground">Aksi</span>
			<Input
				class="h-8 w-40"
				placeholder="mis. access.denied"
				bind:value={action}
				oninput={applyFilters}
			/>
		</label>

		<Button variant="outline" size="sm" onclick={load} disabled={loading}>
			<RefreshCw class="size-4" />
			Segarkan
		</Button>
	</div>

	{#if error}
		<div class="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm">
			{error}
			<Button variant="link" size="sm" onclick={load}>Coba lagi</Button>
		</div>
	{:else if loading && entries.length === 0}
		<Skeleton class="h-48 w-full rounded-xl" />
	{:else if entries.length === 0}
		<div class="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
			Tidak ada entri audit pada filter ini.
		</div>
	{:else}
		<div class="overflow-x-auto rounded-md border">
			<Table>
				<TableHeader>
					<TableRow>
						<TableHead class="whitespace-nowrap text-xs">Waktu</TableHead>
						<TableHead>Aktor</TableHead>
						<TableHead>Aksi</TableHead>
						<TableHead>Target</TableHead>
						<TableHead>Hasil</TableHead>
						<TableHead></TableHead>
					</TableRow>
				</TableHeader>
				<TableBody>
					{#each entries as entry (entry.id)}
						<TableRow>
							<TableCell class="whitespace-nowrap text-xs">
								{format.dateTime(entry.at)}
							</TableCell>
							<TableCell class="text-xs">
								{entry.actor_label ?? entry.actor_kind}
							</TableCell>
							<TableCell class="font-mono text-xs">{entry.action}</TableCell>
							<TableCell class="text-xs">
								{entry.target_kind ?? '-'}
								{#if entry.target_id}
									<span class="font-mono">#{entry.target_id}</span>
								{/if}
							</TableCell>
							<TableCell>
								<Badge variant={entry.result === 'ok' ? 'secondary' : 'destructive'}>
									{entry.result}
								</Badge>
							</TableCell>
							<TableCell>
								<Button variant="ghost" size="sm" onclick={() => (detail = entry)}>Detail</Button>
							</TableCell>
						</TableRow>
					{/each}
				</TableBody>
			</Table>
		</div>

		<div class="flex items-center justify-between">
			<Button
				variant="outline"
				size="sm"
				disabled={offset === 0 || loading}
				onclick={() => {
					offset = Math.max(0, offset - limit);
					void load();
				}}
			>
				<ChevronLeft class="size-4" />
				Sebelumnya
			</Button>
			<Button
				variant="outline"
				size="sm"
				disabled={!hasNext || loading}
				onclick={() => {
					offset += limit;
					void load();
				}}
			>
				Berikutnya
				<ChevronRight class="size-4" />
			</Button>
		</div>
	{/if}
</div>

<svelte:window
	onkeydown={(event) => {
		if (event.key === 'Escape') detail = null;
	}}
/>

{#if detail}
	<div class="fixed inset-0 z-50 flex justify-end bg-black/40">
		<!-- Backdrop: a real button so Escape and keyboard users have an equivalent. -->
		<button
			type="button"
			class="absolute inset-0 cursor-default"
			aria-label="Tutup detail audit"
			onclick={() => (detail = null)}
		></button>
		<div
			class="relative h-full w-full max-w-md overflow-y-auto bg-background p-5 shadow-xl"
			role="dialog"
			aria-modal="true"
			aria-label="Detail audit"
			tabindex="-1"
		>
			<div class="flex items-center justify-between">
				<h3 class="text-base font-semibold">Detail audit</h3>
				<Button variant="ghost" size="sm" onclick={() => (detail = null)}>Tutup</Button>
			</div>
			<dl class="mt-4 space-y-2 text-sm">
				<div class="flex justify-between gap-4">
					<dt class="text-muted-foreground">Waktu</dt>
					<dd>{format.dateTime(detail.at)}</dd>
				</div>
				<div class="flex justify-between gap-4">
					<dt class="text-muted-foreground">Aktor</dt>
					<dd>{detail.actor_kind} · {detail.actor_label ?? '-'}</dd>
				</div>
				<div class="flex justify-between gap-4">
					<dt class="text-muted-foreground">Aksi</dt>
					<dd class="font-mono">{detail.action}</dd>
				</div>
				<div class="flex justify-between gap-4">
					<dt class="text-muted-foreground">Hasil</dt>
					<dd>{detail.result}</dd>
				</div>
				<div class="flex justify-between gap-4">
					<dt class="text-muted-foreground">IP</dt>
					<dd class="font-mono text-xs">{detail.ip ?? '-'}</dd>
				</div>
				<div class="flex justify-between gap-4">
					<dt class="text-muted-foreground">Request ID</dt>
					<dd class="font-mono text-xs">{detail.request_id ?? '-'}</dd>
				</div>
			</dl>
			{#if detail.details}
				<p class="mt-4 text-xs font-medium text-muted-foreground">Details</p>
				<pre class="mt-1 max-h-96 overflow-auto rounded bg-muted p-3 text-[11px]">{JSON.stringify(
						detail.details,
						null,
						2
					)}</pre>
			{/if}
		</div>
	</div>
{/if}
