<script lang="ts">
	import { Card, CardContent, CardHeader, CardTitle } from '#lib/components/ui/card';
	import { Skeleton } from '#lib/components/ui/skeleton';

	let {
		label,
		value,
		hint = '',
		loading = false
	}: { label: string; value: string | number; hint?: string; loading?: boolean } = $props();
</script>

<Card>
	<CardHeader class="pb-2">
		<CardTitle class="text-xs font-medium uppercase tracking-wide text-muted-foreground">
			{label}
		</CardTitle>
	</CardHeader>
	<CardContent>
		{#if loading}
			<Skeleton class="h-8 w-24" />
		{:else}
			<div class="text-2xl font-semibold tabular-nums">{value}</div>
			{#if hint}
				<p class="mt-1 text-xs text-muted-foreground">{hint}</p>
			{/if}
		{/if}
	</CardContent>
</Card>
