<script lang="ts">
	import AuditTable from '#lib/components/audit-table.svelte';
	import HealthCards from '#lib/components/health-cards.svelte';
	import { Alert, AlertDescription, AlertTitle } from '#lib/components/ui/alert';
	import { Button } from '#lib/components/ui/button';
	import { Card, CardContent, CardHeader, CardTitle } from '#lib/components/ui/card';
	import { Input } from '#lib/components/ui/input';
	import { Label } from '#lib/components/ui/label';
	import { Skeleton } from '#lib/components/ui/skeleton';
	import { Switch } from '#lib/components/ui/switch';
	import { systemApi } from '#lib/api';
	import { ApiError } from '#lib/api/errors';
	import type { Health, Stats } from '#lib/api/types';
	import { format } from '#lib/format';
	import { auth } from '#lib/stores/auth.svelte';
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { RotateCw } from '@lucide/svelte';

	let health = $state<Health | null>(null);
	let stats = $state<Stats | null>(null);
	let maintenance = $state(false);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let toggling = $state(false);
	let reason = $state('');
	let autoOff = $state(60);

	const canMaintenance = $derived(auth.can('system.maintenance'));
	const canAudit = $derived(auth.can('audit.view'));

	async function load() {
		loading = true;
		error = null;

		// The maintenance flag comes from an endpoint the middleware never blocks,
		// so it is read on its own: while maintenance is on, /api/stats and
		// /api/health answer 503, and a Promise.all would leave the toggle
		// showing a stale "off" — the operator could then not turn it back off.
		try {
			maintenance = (await systemApi.maintenanceStatus()).maintenance;
		} catch {
			// Leave the previous value; the screen still renders.
		}

		const [healthResult, statsResult] = await Promise.allSettled([
			systemApi.health(),
			systemApi.stats()
		]);

		if (healthResult.status === 'fulfilled') health = healthResult.value;
		if (statsResult.status === 'fulfilled') stats = statsResult.value;

		const failures = [healthResult, statsResult].filter(
			(result) => result.status === 'rejected'
		) as PromiseRejectedResult[];
		// 503 during maintenance is expected, not an error worth a banner.
		const realFailures = failures.filter(
			(result) => !(result.reason instanceof ApiError && result.reason.isMaintenance)
		);
		if (realFailures.length) {
			error =
				realFailures[0].reason instanceof ApiError
					? realFailures[0].reason.detail
					: 'Gagal memuat status sistem.';
		}

		loading = false;
	}

	async function toggleMaintenance(enabled: boolean) {
		toggling = true;
		try {
			await systemApi.setMaintenance({
				enabled,
				reason: reason || undefined,
				auto_off_minutes: enabled ? autoOff : undefined
			});
			maintenance = enabled;
			toast.success(enabled ? 'Maintenance diaktifkan' : 'Maintenance dinonaktifkan');
			await load();
		} catch (failure) {
			toast.error(failure instanceof ApiError ? failure.detail : 'Gagal mengubah maintenance');
		} finally {
			toggling = false;
		}
	}

	onMount(load);
</script>

<div class="space-y-4">
	<div class="flex flex-wrap items-center justify-between gap-2">
		<div>
			<h1 class="text-xl font-semibold">System</h1>
			<p class="text-sm text-muted-foreground">
				Kesehatan, statistik database, maintenance, dan audit log.
			</p>
		</div>
		<Button variant="outline" onclick={load} disabled={loading}>
			<RotateCw class="size-4" />
			Segarkan
		</Button>
	</div>

	{#if error}
		<Alert variant="destructive">
			<AlertTitle>Gagal memuat</AlertTitle>
			<AlertDescription>{error}</AlertDescription>
		</Alert>
	{:else if loading}
		<Skeleton class="h-28 w-full rounded-xl" />
	{:else}
		<HealthCards {health} />
	{/if}

	{#if maintenance}
		<Alert>
			<AlertTitle>Maintenance aktif</AlertTitle>
			<AlertDescription>
				Permintaan selain auth dan halaman ini ditolak dengan 503 sampai maintenance
				dinonaktifkan.
			</AlertDescription>
		</Alert>
	{/if}

	<div class="grid gap-4 lg:grid-cols-2">
		<Card>
			<CardHeader><CardTitle class="text-base">Statistik database</CardTitle></CardHeader>
			<CardContent class="space-y-2 text-sm">
				{#if stats}
					<div class="flex justify-between gap-4">
						<span class="text-muted-foreground">Path</span>
						<span class="truncate font-mono text-xs">{stats.database.path}</span>
					</div>
					<div class="flex justify-between">
						<span class="text-muted-foreground">Ukuran</span>
						<span class="font-mono">{format.bytes(stats.database.size_bytes)}</span>
					</div>
					<div class="flex justify-between">
						<span class="text-muted-foreground">Versi skema</span>
						<span class="font-mono">{stats.database.schema_version}</span>
					</div>
					<div class="flex justify-between">
						<span class="text-muted-foreground">Backup terakhir</span>
						<span>{stats.backup.last ?? 'belum ada'}</span>
					</div>
					<details class="pt-2">
						<summary class="cursor-pointer text-xs text-muted-foreground">Jumlah baris</summary>
						<ul class="mt-1 space-y-1 text-xs">
							{#each Object.entries(stats.rows) as [table, count] (table)}
								<li class="flex justify-between">
									<span class="font-mono">{table}</span>
									<span class="tabular-nums">{count}</span>
								</li>
							{/each}
						</ul>
					</details>
				{:else}
					<p class="text-muted-foreground">Statistik tidak tersedia.</p>
				{/if}
			</CardContent>
		</Card>

		<Card>
			<CardHeader><CardTitle class="text-base">Maintenance</CardTitle></CardHeader>
			<CardContent class="space-y-3 text-sm">
				{#if canMaintenance}
					<div class="flex items-center gap-2">
						<Switch
							checked={maintenance}
							disabled={toggling}
							onCheckedChange={(checked) => toggleMaintenance(checked === true)}
						/>
						<span class="text-xs text-muted-foreground">
							{maintenance ? 'aktif' : 'nonaktif'}
						</span>
					</div>
					<div class="space-y-1">
						<Label for="maint-reason">Alasan</Label>
						<Input id="maint-reason" bind:value={reason} placeholder="mis. pemeliharaan singkat" />
					</div>
					<div class="space-y-1">
						<Label for="maint-auto">Auto-off (menit)</Label>
						<Input id="maint-auto" type="number" min="5" bind:value={autoOff} />
						<p class="text-xs text-muted-foreground">
							Berlaku saat mengaktifkan; mencegah lupa mematikan maintenance.
						</p>
					</div>
				{:else}
					<p class="text-muted-foreground">
						Role Anda tidak memiliki izin mengubah maintenance.
					</p>
				{/if}
			</CardContent>
		</Card>
	</div>

	{#if canAudit}
		<Card>
			<CardHeader><CardTitle class="text-base">Audit log</CardTitle></CardHeader>
			<CardContent><AuditTable /></CardContent>
		</Card>
	{/if}
</div>
