<script lang="ts" generics="T">
	import { Button } from '#lib/components/ui/button';
	import { Skeleton } from '#lib/components/ui/skeleton';
	import {
		Table,
		TableBody,
		TableCell,
		TableHead,
		TableHeader,
		TableRow
	} from '#lib/components/ui/table';
	import type { LogFetcher } from '#lib/log-table';
	import type { Snippet } from 'svelte';
	import { ChevronLeft, ChevronRight, RefreshCw } from '@lucide/svelte';

	let {
		fetcher,
		columns,
		limit = 50,
		deviceId = $bindable<number | null>(null),
		emptyText = 'Belum ada data.',
		renderCell
	}: {
		fetcher: LogFetcher<T>;
		columns: { key: string; label: string; class?: string }[];
		limit?: number;
		deviceId?: number | null;
		emptyText?: string;
		renderCell: Snippet<[{ row: T & Record<string, unknown>; column: string }]>;
	} = $props();

	let items = $state<T[]>([]);
	let loading = $state(false);
	let error = $state<string | null>(null);
	let hasNext = $state(false);
	let offset = $state(0);
	let busy = $state(false);

	async function load() {
		loading = true;
		error = null;
		try {
			const response = await fetcher({
				limit,
				offset,
				...(deviceId !== null ? { deviceId } : {})
			});
			items = response.items;
			// A full page may have more; a short page is the end.
			hasNext = response.items.length === limit;
		} catch (failure) {
			error = failure instanceof Error ? failure.message : 'Gagal memuat data';
			items = [];
			hasNext = false;
		} finally {
			loading = false;
		}
	}

	async function next() {
		if (!hasNext || busy) return;
		busy = true;
		offset += limit;
		await load();
		busy = false;
	}

	async function prev() {
		if (offset === 0 || busy) return;
		busy = true;
		offset = Math.max(0, offset - limit);
		await load();
		busy = false;
	}

	// Reload when the device filter changes, and once on mount.
	let currentDevice = $state(deviceId);
	$effect(() => {
		if (currentDevice !== deviceId) {
			currentDevice = deviceId;
			offset = 0;
			void load();
		}
	});
	$effect(() => {
		void load();
	});

	export function reload() {
		return load();
	}
</script>

<div class="space-y-3">
	<div class="flex items-center justify-between">
		<p class="text-xs text-muted-foreground">{items.length} baris · offset {offset}</p>
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
	{:else if loading && items.length === 0}
		<Skeleton class="h-48 w-full rounded-xl" />
	{:else if items.length === 0}
		<div class="rounded-lg border border-dashed p-10 text-center text-sm text-muted-foreground">
			{emptyText}
		</div>
	{:else}
		<div class="overflow-x-auto rounded-md border">
			<Table>
				<TableHeader>
					<TableRow>
						{#each columns as column (column.key)}
							<TableHead class={column.class}>{column.label}</TableHead>
						{/each}
					</TableRow>
				</TableHeader>
				<TableBody>
					{#each items as row, index (index)}
						<TableRow>
							{#each columns as column (column.key)}
								<TableCell class={column.class}>
									{@render renderCell({ row: row as T & Record<string, unknown>, column: column.key })}
								</TableCell>
							{/each}
						</TableRow>
					{/each}
				</TableBody>
			</Table>
		</div>

		<div class="flex items-center justify-between">
			<Button variant="outline" size="sm" onclick={prev} disabled={busy || offset === 0}>
				<ChevronLeft class="size-4" />
				Sebelumnya
			</Button>
			<Button variant="outline" size="sm" onclick={next} disabled={busy || !hasNext}>
				Berikutnya
				<ChevronRight class="size-4" />
			</Button>
		</div>
	{/if}
</div>
