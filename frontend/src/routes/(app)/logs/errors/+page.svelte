<script lang="ts">
	import { Badge } from '#lib/components/ui/badge';
	import LogTable from '#lib/components/log-table.svelte';
	import { logsApi } from '#lib/api';
	import type { ErrorLog } from '#lib/api/types';
	import { format } from '#lib/format';

	const fetcher = (query: { limit: number; offset: number }) => logsApi.errors(query);

	const columns = [
		{ key: 'created_at', label: 'Waktu', class: 'whitespace-nowrap text-xs' },
		{ key: 'level', label: 'Level' },
		{ key: 'logger_name', label: 'Logger', class: 'font-mono text-xs' },
		{ key: 'message', label: 'Pesan' },
		{ key: 'trace', label: 'Trace' }
	];
</script>

<div class="space-y-4">
	<div>
		<h1 class="text-xl font-semibold">Log Error</h1>
		<p class="text-sm text-muted-foreground">Kesalahan aplikasi yang tercatat di database.</p>
	</div>

	<LogTable {fetcher} {columns} emptyText="Tidak ada error tercatat.">
		{#snippet renderCell({ row, column })}
			{#if column === 'created_at'}
				{format.dateTime(row.created_at as string)}
			{:else if column === 'level'}
				<Badge variant={row.level === 'ERROR' || row.level === 'CRITICAL' ? 'destructive' : 'outline'}>
					{String(row.level)}
				</Badge>
			{:else if column === 'trace'}
				{#if row.exception_trace}
					<details>
						<summary class="cursor-pointer text-xs underline underline-offset-2">Lihat</summary>
						<pre class="mt-1 max-h-64 overflow-auto rounded bg-muted p-2 text-[11px]">{String(
								row.exception_trace
							)}</pre>
					</details>
				{:else}
					-
				{/if}
			{:else if column === 'message'}
				<span class="text-xs">{String(row.message)}</span>
			{:else}
				{String(row[column] ?? '-')}
			{/if}
		{/snippet}
	</LogTable>
</div>
