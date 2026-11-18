<script lang="ts">
	import { Badge } from '#lib/components/ui/badge';
	import DeviceFilter from '#lib/components/device-filter.svelte';
	import LogTable from '#lib/components/log-table.svelte';
	import { logsApi } from '#lib/api';
	import type { ActivityLog } from '#lib/api/types';
	import { format } from '#lib/format';

	let deviceId = $state<number | null>(null);
	const fetcher = (query: { limit: number; offset: number; deviceId?: number }) =>
		logsApi.activities(query);

	const columns = [
		{ key: 'created_at', label: 'Waktu', class: 'whitespace-nowrap text-xs' },
		{ key: 'device_label', label: 'Perangkat' },
		{ key: 'actor', label: 'Aktor' },
		{ key: 'action', label: 'Aksi' },
		{ key: 'status', label: 'Status' },
		{ key: 'message', label: 'Pesan', class: 'text-xs text-muted-foreground' }
	];

	const actorLabel: Record<string, string> = {
		ui: 'Dashboard',
		bot: 'Bot',
		api: 'API',
		system: 'Sistem'
	};
</script>

<div class="space-y-4">
	<div class="flex flex-wrap items-center justify-between gap-2">
		<div>
			<h1 class="text-xl font-semibold">Log Aktivitas</h1>
			<p class="text-sm text-muted-foreground">Setiap kontrol perangkat, dari dashboard atau bot.</p>
		</div>
		<DeviceFilter bind:value={deviceId} />
	</div>

	<LogTable {fetcher} {columns} bind:deviceId emptyText="Belum ada aktivitas kontrol.">
		{#snippet renderCell({ row, column })}
			{#if column === 'created_at'}
				{format.dateTime(row.created_at as string)}
			{:else if column === 'actor'}
				{actorLabel[String(row.actor)] ?? String(row.actor)}
			{:else if column === 'status'}
				<Badge variant={row.status === 'success' ? 'secondary' : 'destructive'}>
					{String(row.status)}
				</Badge>
			{:else if column === 'device_label'}
				{String(row.device_label ?? '-')}
			{:else}
				{String(row[column] ?? '-')}
			{/if}
		{/snippet}
	</LogTable>
</div>
