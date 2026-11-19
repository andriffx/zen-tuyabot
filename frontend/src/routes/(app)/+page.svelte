<script lang="ts">
	import { goto } from '$app/navigation';
	import { Button } from '#lib/components/ui/button';
	import { Card, CardContent, CardHeader, CardTitle } from '#lib/components/ui/card';
	import { Alert, AlertDescription, AlertTitle } from '#lib/components/ui/alert';
	import { Skeleton } from '#lib/components/ui/skeleton';
	import PowerSparkline from '#lib/components/power-sparkline.svelte';
	import RecentActivity from '#lib/components/recent-activity.svelte';
	import StatTile from '#lib/components/stat-tile.svelte';
	import { devicesApi, logsApi, systemApi } from '#lib/api';
	import { ApiError } from '#lib/api/errors';
	import type { ActivityLog, Device, Health, PowerLog, Stats } from '#lib/api/types';
	import { format } from '#lib/format';
	import { overview } from '#lib/overview';
	import { auth } from '#lib/stores/auth.svelte';
	import { stream } from '#lib/stores/stream.svelte';
	import { onMount } from 'svelte';
	import { RotateCw } from '@lucide/svelte';

	let stats = $state<Stats | null>(null);
	let health = $state<Health | null>(null);
	let devices = $state<Pick<Device, 'id' | 'label' | 'last_error'>[]>([]);
	let activities = $state<ActivityLog[]>([]);
	let powerRows = $state<PowerLog[]>([]);
	let loading = $state(true);
	let partialErrors = $state<string[]>([]);

	const model = $derived(
		stats
			? overview.build({
					stats,
					health: health ?? { status: 'ok' },
					devices,
					stream: { devices: stream.devices, sseConnected: stream.sseConnected },
					activities,
					powerRows
				})
			: null
	);

	async function load() {
		loading = true;
		partialErrors = [];

		// Each source fails independently so one broken tile never blanks the page.
		const [statsResult, healthResult, devicesResult, activityResult, powerResult] =
			await Promise.allSettled([
				systemApi.stats(),
				systemApi.health(),
				devicesApi.list(),
				logsApi.activities({ limit: 12 }),
				logsApi.power({ limit: 120 })
			]);

		const failures: string[] = [];
		if (statsResult.status === 'fulfilled') stats = statsResult.value;
		else failures.push('statistik');

		if (healthResult.status === 'fulfilled') health = healthResult.value;
		else failures.push('kesehatan');

		if (devicesResult.status === 'fulfilled') devices = devicesResult.value.devices;
		else failures.push('perangkat');

		if (activityResult.status === 'fulfilled') activities = activityResult.value.items;
		else failures.push('aktivitas');

		if (powerResult.status === 'fulfilled') powerRows = powerResult.value.items;
		else failures.push('log daya');

		const offline = [statsResult, healthResult, devicesResult, activityResult, powerResult].some(
			(result) => result.status === 'rejected' && result.reason instanceof ApiError && result.reason.isOffline
		);
		if (offline) await auth.hydrate();

		partialErrors = failures;
		loading = false;
	}

	onMount(load);
</script>

<div class="space-y-4">
	<div class="flex flex-wrap items-center justify-between gap-2">
		<div>
			<h1 class="text-xl font-semibold">Overview</h1>
			<p class="text-sm text-muted-foreground">
				Ringkasan perangkat, konsumsi daya, dan aktivitas terakhir.
			</p>
		</div>
		<Button variant="outline" onclick={load} disabled={loading}>
			<RotateCw class="size-4" />
			Segarkan
		</Button>
	</div>

	{#if partialErrors.length}
		<Alert variant="destructive">
			<AlertTitle>Sebagian data gagal dimuat</AlertTitle>
			<AlertDescription>
				Bagian berikut tidak dapat dimuat: {partialErrors.join(', ')}.
				<Button variant="link" size="sm" class="px-0" onclick={load}>Coba lagi</Button>
			</AlertDescription>
		</Alert>
	{/if}

	{#if model?.alerts.length}
		<div class="space-y-2">
			{#each model.alerts as alert, index (index)}
				<Alert variant={alert.level === 'error' ? 'destructive' : 'default'}>
					<AlertDescription>{alert.text}</AlertDescription>
				</Alert>
			{/each}
		</div>
	{/if}

	<div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
		<StatTile
			label="Perangkat online"
			value={model ? `${model.tiles.devicesOnline}/${model.tiles.devicesTotal}` : '--'}
			hint={model && model.tiles.devicesTotal - model.tiles.devicesOnline > 0
				? `${model.tiles.devicesTotal - model.tiles.devicesOnline} offline`
				: 'semua online'}
			{loading}
		/>
		<StatTile
			label="Daya sekarang"
			value={format.watts(model?.tiles.powerNow)}
			hint="dari perangkat yang melaporkan"
			{loading}
		/>
		<StatTile
			label="Backup terakhir"
			value={model?.tiles.lastBackup ?? 'belum ada'}
			hint={stats?.backup.last_at ? format.dateTime(stats.backup.last_at) : ''}
			{loading}
		/>
		<StatTile
			label="Status sistem"
			value={health?.status ?? '--'}
			hint={health ? `${health.devices_fresh}/${health.devices_total} data segar` : ''}
			{loading}
		/>
	</div>

	<div class="grid gap-4 lg:grid-cols-3">
		<Card class="lg:col-span-2">
			<CardHeader><CardTitle class="text-base">Konsumsi daya</CardTitle></CardHeader>
			<CardContent>
				{#if loading}
					<Skeleton class="h-36 w-full" />
				{:else}
					<PowerSparkline points={model?.power.points ?? []} max={model?.power.max ?? 0} />
				{/if}
			</CardContent>
		</Card>

		<Card>
			<CardHeader class="flex flex-row items-center justify-between">
				<CardTitle class="text-base">Aksi cepat</CardTitle>
			</CardHeader>
			<CardContent class="flex flex-col gap-2">
				{#if auth.can('monitoring')}
					<Button variant="outline" onclick={() => goto('/devices')}>Buka Devices</Button>
				{/if}
				{#if auth.can('manage_devices')}
					<Button variant="outline" onclick={() => goto('/backup')}>Kelola Backup</Button>
				{/if}
				{#if auth.can('manage_devices')}
					<Button variant="outline" onclick={() => goto('/settings')}>Ubah Settings</Button>
				{/if}
				{#if auth.can('monitoring')}
					<Button variant="outline" onclick={() => goto('/system')}>Lihat System</Button>
				{/if}
				{#if !auth.can('monitoring') && !auth.can('manage_devices') && !auth.can('monitoring')}
					<p class="text-sm text-muted-foreground">Tidak ada aksi untuk role Anda.</p>
				{/if}
			</CardContent>
		</Card>
	</div>

	<RecentActivity items={model?.activity ?? []} />
</div>
