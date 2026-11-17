<script lang="ts">
	import { Badge } from '#lib/components/ui/badge';
	import { Tooltip, TooltipContent, TooltipTrigger } from '#lib/components/ui/tooltip';
	import { connectivity } from '#lib/stores/connectivity.svelte';
	import { stream } from '#lib/stores/stream.svelte';

	const realtimeLabel = $derived(stream.sseConnected ? 'Realtime' : 'Realtime terputus');
	const lastUpdate = $derived(
		stream.lastUpdate ? new Date(stream.lastUpdate).toLocaleTimeString('id-ID') : 'belum ada'
	);
</script>

<div class="flex items-center gap-1">
	<Tooltip>
		<TooltipTrigger>
			{#snippet child({ props })}
				<Badge variant={connectivity.apiOnline ? 'secondary' : 'destructive'} {...props}>
					<span
						class="mr-1 inline-block size-2 rounded-full {connectivity.apiOnline
							? 'bg-emerald-500'
							: 'bg-current'}"
					></span>
					API
				</Badge>
			{/snippet}
		</TooltipTrigger>
		<TooltipContent>
			{connectivity.apiOnline ? 'Backend dapat dihubungi' : 'Backend tidak dapat dihubungi'}
		</TooltipContent>
	</Tooltip>

	<Tooltip>
		<TooltipTrigger>
			{#snippet child({ props })}
				<Badge variant={stream.sseConnected ? 'outline' : 'outline'} class="text-muted-foreground" {...props}>
					<span
						class="mr-1 inline-block size-2 rounded-full {stream.sseConnected
							? 'bg-emerald-500'
							: 'bg-amber-500'}"
					></span>
					{realtimeLabel}
				</Badge>
			{/snippet}
		</TooltipTrigger>
		<TooltipContent>Pembaruan terakhir: {lastUpdate}</TooltipContent>
	</Tooltip>
</div>
