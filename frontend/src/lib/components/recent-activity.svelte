<script lang="ts">
	import { Card, CardContent, CardHeader, CardTitle } from '#lib/components/ui/card';
	import { Badge } from '#lib/components/ui/badge';
	import { format } from '#lib/format';

	type ActivityRow = {
		id: number;
		device_label: string | null;
		action: string;
		status: string;
		created_at: string;
		actor: string;
	};

	let { items = [] }: { items: ActivityRow[] } = $props();

	const actorLabel: Record<string, string> = {
		ui: 'Dashboard',
		bot: 'Bot',
		api: 'API',
		system: 'Sistem'
	};
</script>

<Card>
	<CardHeader><CardTitle class="text-base">Aktivitas terbaru</CardTitle></CardHeader>
	<CardContent>
		{#if items.length === 0}
			<p class="text-sm text-muted-foreground">Belum ada aktivitas.</p>
		{:else}
			<ul class="divide-y">
				{#each items as item (item.id)}
					<li class="flex items-center justify-between gap-3 py-2 text-sm">
						<div class="min-w-0">
							<div class="truncate">
								<span class="font-medium">{item.device_label ?? 'Sistem'}</span>
								— {item.action}
							</div>
							<div class="text-xs text-muted-foreground">
								{actorLabel[item.actor] ?? item.actor} · {format.dateTime(item.created_at)}
							</div>
						</div>
						<Badge variant={item.status === 'success' ? 'secondary' : 'destructive'}>
							{item.status}
						</Badge>
					</li>
				{/each}
			</ul>
		{/if}
	</CardContent>
</Card>
