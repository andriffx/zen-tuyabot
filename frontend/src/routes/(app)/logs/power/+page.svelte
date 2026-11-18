<script lang="ts">
	import { page } from '$app/state';
	import DeviceFilter from '#lib/components/device-filter.svelte';
	import LogTable from '#lib/components/log-table.svelte';
	import { logsApi } from '#lib/api';
	import type { PowerLog } from '#lib/api/types';
	import { format } from '#lib/format';

	const initialDevice = page.url.searchParams.get('device');

	let deviceId = $state<number | null>(initialDevice ? Number(initialDevice) : null);

	const fetcher = (query: { limit: number; offset: number; deviceId?: number }) =>
		logsApi.power(query);

	const columns = [
		{ key: 'created_at', label: 'Waktu', class: 'whitespace-nowrap text-xs' },
		{ key: 'device_label', label: 'Perangkat' },
		{ key: 'power_w', label: 'Daya', class: 'text-right font-mono' },
		{ key: 'voltage_v', label: 'Tegangan', class: 'text-right font-mono' },
		{ key: 'current_a', label: 'Arus', class: 'text-right font-mono' },
		{ key: 'switch_state', label: 'Saklar' },
		{ key: 'source', label: 'Sumber', class: 'text-xs' }
	];
</script>

<div class="space-y-4">
	<div class="flex flex-wrap items-center justify-between gap-2">
		<div>
			<h1 class="text-xl font-semibold">Log Daya</h1>
			<p class="text-sm text-muted-foreground">Riwayat konsumsi daya yang dicatat scheduler.</p>
		</div>
		<DeviceFilter bind:value={deviceId} />
	</div>

	<LogTable {fetcher} {columns} bind:deviceId emptyText="Belum ada log daya. Scheduler mencatat setiap beberapa menit.">
		{#snippet renderCell({ row, column })}
			{#if column === 'created_at'}
				{format.dateTime(row.created_at as string)}
			{:else if column === 'power_w'}
				{format.watts(row.power_w as number)}
			{:else if column === 'voltage_v'}
				{format.volts(row.voltage_v as number)}
			{:else if column === 'current_a'}
				{format.amps(row.current_a as number)}
			{:else if column === 'switch_state'}
				{row.switch_state === 1 ? 'NYALA' : row.switch_state === 0 ? 'MATI' : '-'}
			{:else}
				{String(row[column] ?? '-')}
			{/if}
		{/snippet}
	</LogTable>
</div>
