<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { Badge } from '#lib/components/ui/badge';
	import { Button } from '#lib/components/ui/button';
	import { Card, CardContent, CardHeader, CardTitle } from '#lib/components/ui/card';
	import { Skeleton } from '#lib/components/ui/skeleton';
	import {
		Table,
		TableBody,
		TableCell,
		TableHead,
		TableHeader,
		TableRow
	} from '#lib/components/ui/table';
	import { devicesApi } from '#lib/api';
	import { ApiError } from '#lib/api/errors';
	import type { Device, DeviceDiagnosis, DeviceStatus, DeviceTestResult } from '#lib/api/types';
	import { devices } from '#lib/devices';
	import { format } from '#lib/format';
	import { auth } from '#lib/stores/auth.svelte';
	import { stream } from '#lib/stores/stream.svelte';
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { ArrowLeft, FlaskConical, Stethoscope, Trash2 } from '@lucide/svelte';

	const deviceId = $derived(Number(page.params.id));

	let device = $state<Device | null>(null);
	let status = $state<DeviceStatus | null>(null);
	let test = $state<DeviceTestResult | null>(null);
	let diagnosis = $state<DeviceDiagnosis | null>(null);
	let diagnosing = $state(false);
	let loading = $state(true);
	let testing = $state(false);
	let error = $state<string | null>(null);

	async function load() {
		loading = true;
		error = null;
		try {
			const [list, current] = await Promise.all([devicesApi.list(), devicesApi.status(deviceId)]);
			device = list.devices.find((entry) => entry.id === deviceId) ?? null;
			status = current;
			if (!device) error = 'Perangkat tidak ditemukan.';
		} catch (failure) {
			error = failure instanceof ApiError ? failure.detail : 'Gagal memuat perangkat.';
		} finally {
			loading = false;
		}
	}

	async function runTest() {
		testing = true;
		try {
			test = await devicesApi.test(deviceId);
			if (test.success) toast.success('Perangkat merespons');
			else toast.error(test.message ?? 'Perangkat tidak merespons');
		} catch (failure) {
			toast.error(failure instanceof ApiError ? failure.detail : 'Test gagal');
		} finally {
			testing = false;
		}
	}

	async function runDiagnose() {
		diagnosing = true;
		try {
			diagnosis = await devicesApi.diagnose(deviceId);
		} catch (failure) {
			toast.error(failure instanceof ApiError ? failure.detail : 'Diagnosa gagal');
		} finally {
			diagnosing = false;
		}
	}

	async function remove() {
		if (!device) return;
		if (!confirm(`Hapus perangkat "${device.label}"? Tindakan ini tidak bisa dibatalkan.`)) return;
		try {
			await devicesApi.remove(device.id);
			toast.success('Perangkat dihapus');
			await goto('/devices');
		} catch (failure) {
			toast.error(failure instanceof ApiError ? failure.detail : 'Gagal menghapus');
		}
	}

	onMount(load);
</script>

<div class="space-y-4">
	<Button variant="ghost" size="sm" href="/devices">
		<ArrowLeft class="size-4" />
		Kembali
	</Button>

	{#if loading}
		<Skeleton class="h-64 w-full rounded-xl" />
	{:else if error || !device}
		<div class="rounded-md border border-destructive/40 bg-destructive/5 p-4 text-sm">{error}</div>
	{:else}
		<div class="flex flex-wrap items-start justify-between gap-2">
			<div>
				<h1 class="text-xl font-semibold">{device.label}</h1>
				<p class="text-sm text-muted-foreground">
					{device.name} · {device.type} · {device.ip ?? 'IP belum diisi'} · v{device.version}
				</p>
			</div>
			<div class="flex gap-2">
				{#if auth.can('manage_devices')}
					<Button variant="outline" onclick={runTest} disabled={testing}>
						<FlaskConical class="size-4" />
						{testing ? 'Menguji…' : 'Test koneksi'}
					</Button>
					<Button variant="outline" onclick={runDiagnose} disabled={diagnosing}>
						<Stethoscope class="size-4" />
						{diagnosing ? 'Mendiagnosa…' : 'Diagnosa jaringan'}
					</Button>
				{/if}
				{#if auth.can('manage_devices')}
					<Button variant="destructive" onclick={remove}>
						<Trash2 class="size-4" />
						Hapus
					</Button>
				{/if}
			</div>
		</div>

		<div class="grid gap-4 md:grid-cols-2">
			{#if diagnosis}
				<Card class="md:col-span-2">
					<CardHeader>
						<CardTitle class="text-base">Diagnosa jaringan</CardTitle>
					</CardHeader>
					<CardContent class="space-y-3 text-sm">
						<div class="grid gap-2 sm:grid-cols-2">
							<div>
								<p class="text-xs text-muted-foreground">Alamat container</p>
								<p class="font-mono text-xs">
									{diagnosis.container.addresses.join(', ') || 'tidak diketahui'}
								</p>
							</div>
							<div>
								<p class="text-xs text-muted-foreground">Perangkat</p>
								<p class="font-mono text-xs">
									{diagnosis.device.ip ?? 'IP belum diisi'} · v{diagnosis.device.version} ·
									key {diagnosis.device.has_local_key ? 'ada' : 'KOSONG'}
								</p>
							</div>
						</div>

						{#each diagnosis.checks as check (check.name)}
							<div class="flex items-start gap-2">
								<Badge variant={check.ok ? 'default' : 'destructive'}>
									{check.ok ? 'ok' : 'gagal'}
								</Badge>
								<div>
									<p class="font-mono text-xs">{check.target}</p>
									<p class="text-xs text-muted-foreground">{check.detail}</p>
								</div>
							</div>
						{/each}

						<ul class="list-disc space-y-1 pl-5 text-xs text-muted-foreground">
							{#each diagnosis.hints as hint (hint)}
								<li>{hint}</li>
							{/each}
						</ul>
					</CardContent>
				</Card>
			{/if}

			<Card>
				<CardHeader><CardTitle class="text-base">Status</CardTitle></CardHeader>
				<CardContent class="space-y-2 text-sm">
					<div class="flex justify-between">
						<span class="text-muted-foreground">Koneksi</span>
						<Badge variant={status?.online ? 'default' : 'destructive'}>
							{status?.online ? 'online' : 'offline'}
						</Badge>
					</div>
					<div class="flex justify-between">
						<span class="text-muted-foreground">Saklar</span>
						<span>{stream.devices[device.id]?.switch_on ? 'NYALA' : 'MATI'}</span>
					</div>
					<div class="flex justify-between">
						<span class="text-muted-foreground">Daya</span>
						<span class="font-mono">{format.watts(stream.devices[device.id]?.power_w)}</span>
					</div>
					<div class="flex justify-between">
						<span class="text-muted-foreground">Tegangan</span>
						<span class="font-mono">{format.volts(stream.devices[device.id]?.voltage_v)}</span>
					</div>
					<div class="flex justify-between">
						<span class="text-muted-foreground">Arus</span>
						<span class="font-mono">{format.amps(stream.devices[device.id]?.current_a)}</span>
					</div>
					{#if status?.message}
						<p class="text-xs text-destructive">{devices.statusText({ success: false, online: false })}</p>
					{/if}
					{#if device.last_error}
						<p class="text-xs text-destructive">Error terakhir: {device.last_error}</p>
					{/if}
				</CardContent>
			</Card>

			<Card>
				<CardHeader><CardTitle class="text-base">Pemetaan DPS</CardTitle></CardHeader>
				<CardContent>
					<Table>
						<TableHeader>
							<TableRow>
								<TableHead>Fungsi</TableHead>
								<TableHead>DP</TableHead>
								<TableHead>Nilai mentah</TableHead>
							</TableRow>
						</TableHeader>
						<TableBody>
							{#each Object.entries(device.dps) as [semantic, index] (semantic)}
								<TableRow>
									<TableCell>{semantic}</TableCell>
									<TableCell class="font-mono">{index}</TableCell>
									<TableCell class="font-mono text-xs">
										{test?.raw?.[String(index)] ?? '-'}
									</TableCell>
								</TableRow>
							{/each}
						</TableBody>
					</Table>
					{#if Object.keys(device.dps).length === 0}
						<p class="mt-2 text-xs text-amber-600">Belum ada DP dipetakan.</p>
					{/if}
				</CardContent>
			</Card>
		</div>

		{#if test}
			<Card>
				<CardHeader><CardTitle class="text-base">Hasil test koneksi</CardTitle></CardHeader>
				<CardContent class="space-y-2">
					{#if test.success}
						<p class="text-sm">Nilai terbaca (setelah dipetakan):</p>
						<pre class="overflow-x-auto rounded bg-muted p-3 text-xs">{JSON.stringify(
								test.mapped ?? {},
								null,
								2
							)}</pre>
						<p class="text-sm">DPS mentah:</p>
						<pre class="overflow-x-auto rounded bg-muted p-3 text-xs">{JSON.stringify(
								test.raw ?? {},
								null,
								2
							)}</pre>
					{:else}
						<p class="text-sm text-destructive">{test.message}</p>
					{/if}
				</CardContent>
			</Card>
		{/if}
	{/if}
</div>
