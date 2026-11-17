<script lang="ts">
	import { Badge } from '#lib/components/ui/badge';
	import { Card, CardContent, CardHeader, CardTitle } from '#lib/components/ui/card';
	import type { Health } from '#lib/api/types';

	let { health }: { health: Health | null } = $props();

	const statusVariant = $derived(
		health?.status === 'ok' ? 'secondary' : health?.status === 'degraded' ? 'outline' : 'destructive'
	);
</script>

<div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
	<Card>
		<CardHeader class="pb-2">
			<CardTitle class="text-xs uppercase tracking-wide text-muted-foreground">Status</CardTitle>
		</CardHeader>
		<CardContent>
			<Badge variant={statusVariant}>{health?.status ?? '--'}</Badge>
		</CardContent>
	</Card>

	<Card>
		<CardHeader class="pb-2">
			<CardTitle class="text-xs uppercase tracking-wide text-muted-foreground">Database</CardTitle>
		</CardHeader>
		<CardContent class="text-2xl font-semibold">
			{health ? (health.database ? 'terhubung' : 'gagal') : '--'}
		</CardContent>
	</Card>

	<Card>
		<CardHeader class="pb-2">
			<CardTitle class="text-xs uppercase tracking-wide text-muted-foreground">Data perangkat</CardTitle>
		</CardHeader>
		<CardContent class="text-2xl font-semibold tabular-nums">
			{health ? `${health.devices_fresh}/${health.devices_total}` : '--'}
			<p class="text-xs font-normal text-muted-foreground">segar (&lt; 5 menit)</p>
		</CardContent>
	</Card>

	<Card>
		<CardHeader class="pb-2">
			<CardTitle class="text-xs uppercase tracking-wide text-muted-foreground">Maintenance</CardTitle>
		</CardHeader>
		<CardContent>
			<Badge variant={health?.maintenance ? 'destructive' : 'outline'}>
				{health?.maintenance ? 'aktif' : 'nonaktif'}
			</Badge>
		</CardContent>
	</Card>
</div>
