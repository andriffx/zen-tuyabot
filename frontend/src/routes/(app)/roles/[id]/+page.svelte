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

	const roleId = $derived(Number(page.params.id));

	let role = $state<Role | null>(null);
	let catalog = $state<PermissionCatalog | null>(null);
	let selected = $state<string[]>([]);
	let saved = $state<string[]>([]);
	let loading = $state(true);
	let saving = $state(false);
	let error = $state<string | null>(null);

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
			const [roleList, catalogData] = await Promise.all([rolesApi.list(), rolesApi.catalog()]);
			role = roleList.roles.find((entry) => entry.id === roleId) ?? null;
			catalog = catalogData;
			selected = role ? [...role.permissions] : [];
			saved = [...selected];
			if (!role) error = 'Role tidak ditemukan.';
		} catch (failure) {
			error = failure instanceof ApiError ? failure.detail : 'Gagal memuat role.';
		} finally {
			loading = false;
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

		<p class="text-xs text-muted-foreground">
			{selected.length} permission dipilih · {role.user_count} pemakai
		</p>
	{/if}
</div>
