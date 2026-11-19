<script lang="ts">
	import { Button } from '#lib/components/ui/button';
	import { Skeleton } from '#lib/components/ui/skeleton';
	import ConfirmControl from '#lib/components/confirm-control.svelte';
	import DeviceCard from '#lib/components/device-card.svelte';
	import DeviceDialog from '#lib/components/device-dialog.svelte';
	import ScanDialog from '#lib/components/scan-dialog.svelte';
	import { devicesApi, rolesApi } from '#lib/api';
	import { ApiError } from '#lib/api/errors';
	import type { Device, DeviceTemplates, Role, ScanCandidate } from '#lib/api/types';
	import { devices, type DeviceView } from '#lib/devices';
	import { auth } from '#lib/stores/auth.svelte';
	import { stream } from '#lib/stores/stream.svelte';
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { Plus, Radar, RefreshCw } from '@lucide/svelte';

	let list = $state<Device[]>([]);
	let templates = $state<DeviceTemplates | null>(null);
	let roles = $state<Role[]>([]);
	let loading = $state(true);
	let loadError = $state<string | null>(null);
	let busyId = $state<number | null>(null);

	let dialogOpen = $state(false);
	let editing = $state<Device | null>(null);
	let prefill = $state<ScanCandidate | null>(null);
	let scanOpen = $state(false);

	let confirmOpen = $state(false);
	let pendingAction = $state<{ device: DeviceView; on: boolean } | null>(null);

	const views = $derived(devices.mergeStream(list, stream.devices));
	const canManage = $derived(auth.can('manage_devices'));
	const canScan = $derived(auth.can('manage_devices'));
	const canControl = $derived(auth.can('monitoring'));

	async function load() {
		loading = true;
		loadError = null;
		try {
			const [deviceList, templateList] = await Promise.all([devicesApi.list(), devicesApi.templates()]);
			list = deviceList.devices;
			templates = templateList;
			if (auth.can('manage_users')) {
				roles = (await rolesApi.list()).roles;
			}
		} catch (error) {
			loadError =
				error instanceof ApiError ? error.detail : 'Gagal memuat perangkat. Coba lagi.';
		} finally {
			loading = false;
		}
	}

	function openCreate() {
		editing = null;
		prefill = null;
		dialogOpen = true;
	}

	function openEdit(device: DeviceView) {
		editing = device;
		prefill = null;
		dialogOpen = true;
	}

	function useCandidate(candidate: ScanCandidate) {
		editing = null;
		prefill = candidate;
		dialogOpen = true;
	}

	async function toggle(device: DeviceView, on: boolean) {
		busyId = device.id;
		try {
			const result = on ? await devicesApi.on(device.id) : await devicesApi.off(device.id);
			if (result.success) {
				toast.success(`${device.label}: ${on ? 'dinyalakan' : 'dimatikan'}`);
			} else {
				toast.error(result.message || 'Perangkat tidak merespons');
			}
			await load();
		} catch (error) {
			toast.error(error instanceof ApiError ? error.detail : 'Kontrol gagal');
		} finally {
			busyId = null;
		}
	}

	function requestToggle(device: DeviceView, on: boolean) {
		if (devices.requiresConfirm(device)) {
			pendingAction = { device, on };
			confirmOpen = true;
			return;
		}
		void toggle(device, on);
	}

	onMount(load);
</script>

<div class="space-y-4">
	<div class="flex flex-wrap items-center justify-between gap-2">
		<div>
			<h1 class="text-xl font-semibold">Devices</h1>
			<p class="text-sm text-muted-foreground">
				{views.length} perangkat · {views.filter((view) => devices.onlineOf(view)).length} online
			</p>
		</div>
		<div class="flex gap-2">
			<Button variant="outline" onclick={load}>
				<RefreshCw class="size-4" />
				Segarkan
			</Button>
			{#if canScan}
				<Button variant="outline" onclick={() => (scanOpen = true)}>
					<Radar class="size-4" />
					Scan LAN
				</Button>
			{/if}
			{#if canManage}
				<Button onclick={openCreate}>
					<Plus class="size-4" />
					Tambah device
				</Button>
			{/if}
		</div>
	</div>

	{#if loadError}
		<div class="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm">
			{loadError}
			<Button variant="link" size="sm" onclick={load}>Coba lagi</Button>
		</div>
	{:else if loading}
		<div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
			{#each Array(3) as _, index (index)}
				<Skeleton class="h-48 w-full rounded-xl" />
			{/each}
		</div>
	{:else if views.length === 0}
		<div class="rounded-lg border border-dashed p-10 text-center">
			<p class="text-sm text-muted-foreground">Belum ada perangkat terdaftar.</p>
			{#if canManage}
				<Button class="mt-3" onclick={openCreate}>Tambah device pertama</Button>
			{/if}
		</div>
	{:else}
		<div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
			{#each views as device (device.id)}
				<div class="space-y-2">
					<DeviceCard
						{device}
						{canControl}
						busy={busyId === device.id}
						onToggle={requestToggle}
					/>
					{#if canManage}
						<Button variant="ghost" size="sm" class="w-full" onclick={() => openEdit(device)}>
							Ubah pengaturan
						</Button>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</div>

<DeviceDialog
	bind:open={dialogOpen}
	device={editing}
	{templates}
	{roles}
	{prefill}
	onSaved={load}
/>
<ScanDialog bind:open={scanOpen} onPick={useCandidate} />
<ConfirmControl
	bind:open={confirmOpen}
	deviceLabel={pendingAction?.device.label ?? ''}
	onConfirm={() => {
		if (pendingAction) void toggle(pendingAction.device, pendingAction.on);
		pendingAction = null;
	}}
/>
