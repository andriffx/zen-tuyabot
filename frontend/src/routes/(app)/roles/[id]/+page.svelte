<script lang="ts">
	import { page } from '$app/state';
	import { Badge } from '#lib/components/ui/badge';
	import { Button } from '#lib/components/ui/button';
	import { Card, CardContent, CardHeader, CardTitle } from '#lib/components/ui/card';
	import { Skeleton } from '#lib/components/ui/skeleton';
	import PermissionMatrix from '#lib/components/permission-matrix.svelte';
	import { rolesApi } from '#lib/api';
	import { ApiError } from '#lib/api/errors';
	import type { PermissionCatalog, Role } from '#lib/api/types';
	import { permissions } from '#lib/permissions';
	import { auth } from '#lib/stores/auth.svelte';
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { ArrowLeft, Save } from '@lucide/svelte';
	import { devicesApi } from '#lib/api';

	const roleId = $derived(Number(page.params.id));

	let role = $state<Role | null>(null);
	let catalog = $state<PermissionCatalog | null>(null);
	let selected = $state<string[]>([]);
	let saved = $state<string[]>([]);
	let loading = $state(true);
	let saving = $state(false);
	let error = $state<string | null>(null);

	// Per-device access: one row per device, three independent rights.
	let devices = $state<{ id: number; label: string }[]>([]);
	let access = $state<Record<number, { can_view: boolean; can_on: boolean; can_off: boolean }>>({});
	let savedAccess = $state('');
	let savingDevices = $state(false);

	const canManage = $derived(auth.can('roles.manage'));
	const groups = $derived(catalog ? permissions.groupCatalog(catalog) : []);
	const editable = $derived(
		catalog ? permissions.editable(catalog, [...(auth.me?.permissions ?? [])]) : []
	);
	const locked = $derived(
		role?.is_protected ? [...permissions.PROTECTED_REQUIRED] : []
	);
	const changed = $derived(
		JSON.stringify([...selected].sort()) !== JSON.stringify([...saved].sort())
	);

	async function load() {
		loading = true;
		error = null;
		try {
			const [roleList, catalogData, deviceList, accessData] = await Promise.all([
				rolesApi.list(),
				rolesApi.catalog(),
				devicesApi.list(),
				rolesApi.devices(roleId)
			]);
			role = roleList.roles.find((entry) => entry.id === roleId) ?? null;
			catalog = catalogData;
			devices = deviceList.devices.map((device) => ({ id: device.id, label: device.label }));
			access = Object.fromEntries(
				devices.map((device) => [
					device.id,
					accessData.entries.find((entry) => entry.device_id === device.id) ?? {
						can_view: false,
						can_on: false,
						can_off: false
					}
				])
			);
			savedAccess = JSON.stringify(access);
			selected = role ? [...role.permissions] : [];
			saved = [...selected];
			if (!role) error = 'Role tidak ditemukan.';
		} catch (failure) {
			error = failure instanceof ApiError ? failure.detail : 'Gagal memuat role.';
		} finally {
			loading = false;
		}
	}

	const accessChanged = $derived(JSON.stringify(access) !== savedAccess);

	async function saveDevices() {
		if (!role) return;
		savingDevices = true;
		try {
			const entries = devices
				.filter((device) => {
					const row = access[device.id];
					return row && (row.can_view || row.can_on || row.can_off);
				})
				.map((device) => ({ device_id: device.id, ...access[device.id] }));
			await rolesApi.setDevices(role.id, entries);
			savedAccess = JSON.stringify(access);
			toast.success('Akses perangkat disimpan');
		} catch (failure) {
			toast.error(failure instanceof ApiError ? failure.detail : 'Gagal menyimpan akses');
		} finally {
			savingDevices = false;
		}
	}

	async function save() {
		if (!role) return;
		saving = true;
		try {
			const updated = await rolesApi.update(role.id, { permissions: selected });
			role = updated;
			saved = [...selected];
			toast.success('Izin disimpan. Sesi pengguna role ini dicabut dan harus login ulang.');
			await auth.refresh();
		} catch (failure) {
			toast.error(failure instanceof ApiError ? failure.detail : 'Gagal menyimpan izin');
		} finally {
			saving = false;
		}
	}

	onMount(load);
</script>

<div class="space-y-4">
	<Button variant="ghost" size="sm" href="/roles">
		<ArrowLeft class="size-4" />
		Kembali
	</Button>

	{#if loading}
		<Skeleton class="h-96 w-full rounded-xl" />
	{:else if error || !role}
		<div class="rounded-md border border-destructive/40 bg-destructive/5 p-4 text-sm">
			{error}
		</div>
	{:else}
		<div class="flex flex-wrap items-start justify-between gap-2">
			<div>
				<h1 class="flex items-center gap-2 text-xl font-semibold">
					{role.name}
					{#if role.is_protected}<Badge variant="outline">terlindungi</Badge>{/if}
				</h1>
				<p class="font-mono text-xs text-muted-foreground">{role.slug}</p>
			</div>
			{#if canManage}
				<Button onclick={save} disabled={!changed || saving}>
					<Save class="size-4" />
					{saving ? 'Menyimpan…' : 'Simpan izin'}
				</Button>
			{/if}
		</div>

		{#if canManage}
			<Card class="border-amber-500/40 bg-amber-50 dark:bg-amber-950/20">
				<CardContent class="pt-4 text-sm">
					Menyimpan izin mencabut sesi semua pengguna dengan role ini dan menonaktifkan API key
					yang memakainya. Mereka harus login ulang.
				</CardContent>
			</Card>
		{/if}

		<Card>
			<CardHeader><CardTitle class="text-base">Permission</CardTitle></CardHeader>
			<CardContent>
				<PermissionMatrix
					{groups}
					{selected}
					{editable}
					lockedKeys={locked}
					onChange={(next) => {
						if (!canManage) return;
						selected = locked.length
							? [...new Set([...next, ...locked])]
							: next;
					}}
				/>
			</CardContent>
		</Card>

		<Card>
			<CardHeader class="flex flex-row items-center justify-between gap-2">
				<CardTitle class="text-base">Akses perangkat</CardTitle>
				{#if canManage}
					<Button size="sm" onclick={saveDevices} disabled={!accessChanged || savingDevices}>
						<Save class="size-4" />
						{savingDevices ? 'Menyimpan…' : 'Simpan akses'}
					</Button>
				{/if}
			</CardHeader>
			<CardContent>
				{#if devices.length === 0}
					<p class="text-sm text-muted-foreground">Belum ada perangkat.</p>
				{:else}
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b text-left text-xs text-muted-foreground">
								<th class="pb-2">Perangkat</th>
								<th class="pb-2 text-center">Lihat</th>
								<th class="pb-2 text-center">Nyalakan</th>
								<th class="pb-2 text-center">Matikan</th>
							</tr>
						</thead>
						<tbody>
							{#each devices as device (device.id)}
								<tr class="border-b last:border-0">
									<td class="py-2">{device.label}</td>
									{#each ['can_view', 'can_on', 'can_off'] as right (right)}
										<td class="py-2 text-center">
											<input
												type="checkbox"
												class="size-4"
												checked={access[device.id]?.[right as 'can_view']}
												disabled={!canManage}
												onchange={(event) => {
													access[device.id] = {
														...access[device.id],
														[right]: (event.currentTarget as HTMLInputElement).checked
													};
												}}
											/>
										</td>
									{/each}
								</tr>
							{/each}
						</tbody>
					</table>
					<p class="mt-2 text-xs text-muted-foreground">
						Tanpa centang, perangkat tidak muncul untuk role ini. Nyalakan dan Matikan bisa
						dipisah: role boleh menyalakan tanpa boleh mematikan.
					</p>
				{/if}
			</CardContent>
		</Card>

		<p class="text-xs text-muted-foreground">
			{selected.length} permission dipilih · {role.user_count} pemakai
		</p>
	{/if}
</div>
