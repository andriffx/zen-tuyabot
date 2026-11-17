<script lang="ts">
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
	import { Plus, Shield, Trash2 } from '@lucide/svelte';

	let roles = $state<Role[]>([]);
	let catalog = $state<PermissionCatalog | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);

	let dialogOpen = $state(false);
	let slug = $state('');
	let name = $state('');
	let description = $state('');
	let selected = $state<string[]>([]);
	let saving = $state(false);
	let formError = $state<string | null>(null);

	const canManage = $derived(auth.can('roles.manage'));
	const groups = $derived(catalog ? permissions.groupCatalog(catalog) : []);
	const editable = $derived(
		catalog ? permissions.editable(catalog, [...(auth.me?.permissions ?? [])]) : []
	);

	async function load() {
		loading = true;
		error = null;
		try {
			const [roleList, catalogData] = await Promise.all([rolesApi.list(), rolesApi.catalog()]);
			roles = roleList.roles;
			catalog = catalogData;
		} catch (failure) {
			error = failure instanceof ApiError ? failure.detail : 'Gagal memuat role.';
		} finally {
			loading = false;
		}
	}

	function openCreate() {
		slug = '';
		name = '';
		description = '';
		selected = ['devices.view'];
		formError = null;
		dialogOpen = true;
	}

	async function create(event: SubmitEvent) {
		event.preventDefault();
		formError = null;
		saving = true;
		try {
			await rolesApi.create({
				slug: slug.trim(),
				name: name.trim() || slug.trim(),
				description: description.trim() || null,
				permissions: selected
			});
			toast.success('Role dibuat');
			dialogOpen = false;
			await load();
		} catch (failure) {
			formError = failure instanceof ApiError ? failure.detail : 'Gagal membuat role';
		} finally {
			saving = false;
		}
	}

	async function remove(role: Role) {
		if (!confirm(`Hapus role "${role.name}"?`)) return;
		try {
			await rolesApi.remove(role.id);
			toast.success('Role dihapus');
			await load();
		} catch (failure) {
			toast.error(failure instanceof ApiError ? failure.detail : 'Gagal menghapus role');
		}
	}

	onMount(load);
</script>

<div class="space-y-4">
	<div class="flex flex-wrap items-center justify-between gap-2">
		<div>
			<h1 class="text-xl font-semibold">Roles</h1>
			<p class="text-sm text-muted-foreground">
				Role dipakai bersama oleh akun web dan user Telegram.
			</p>
		</div>
		{#if canManage}
			<Button onclick={openCreate}><Plus class="size-4" />Tambah role</Button>
		{/if}
	</div>

	{#if error}
		<div class="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm">
			{error}
			<Button variant="link" size="sm" onclick={load}>Coba lagi</Button>
		</div>
	{:else if loading}
		<div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
			{#each Array(4) as _, index (index)}
				<Skeleton class="h-36 w-full rounded-xl" />
			{/each}
		</div>
	{:else}
		<div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
			{#each roles as role (role.id)}
				<Card>
					<CardHeader class="flex flex-row items-start justify-between gap-2">
						<div>
							<CardTitle class="flex items-center gap-2 text-base">
								<Shield class="size-4" />
								{role.name}
							</CardTitle>
							<p class="mt-1 font-mono text-xs text-muted-foreground">{role.slug}</p>
						</div>
						{#if role.is_protected}
							<Badge variant="outline">terlindungi</Badge>
						{/if}
					</CardHeader>
					<CardContent class="space-y-3 text-sm">
						<p class="text-muted-foreground">
							{role.permissions.length} permission · {role.user_count} pemakai
						</p>
						<div class="flex gap-2">
							<Button size="sm" variant="outline" href="/roles/{role.id}">
								{canManage ? 'Ubah izin' : 'Lihat izin'}
							</Button>
							{#if canManage && !role.is_protected}
								<Button size="sm" variant="ghost" onclick={() => remove(role)}>
									<Trash2 class="size-4" />
								</Button>
							{/if}
						</div>
					</CardContent>
				</Card>
			{/each}
		</div>
	{/if}
</div>

{#if dialogOpen}
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
		<form
			class="max-h-[90svh] w-full max-w-2xl space-y-4 overflow-y-auto rounded-xl bg-background p-6"
			onsubmit={create}
		>
			<div>
				<h2 class="text-lg font-semibold">Tambah role</h2>
				<p class="text-sm text-muted-foreground">Pilih izin yang boleh diberikan.</p>
			</div>

			<div class="grid gap-3 sm:grid-cols-2">
				<label class="space-y-1 text-sm">
					<span class="font-medium">Slug</span>
					<input
						class="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
						bind:value={slug}
						placeholder="tamu"
						required
					/>
				</label>
				<label class="space-y-1 text-sm">
					<span class="font-medium">Nama</span>
					<input
						class="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
						bind:value={name}
						placeholder="Tamu"
					/>
				</label>
			</div>
			<label class="block space-y-1 text-sm">
				<span class="font-medium">Deskripsi</span>
				<input
					class="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
					bind:value={description}
				/>
			</label>

			<PermissionMatrix {groups} {selected} {editable} onChange={(next) => (selected = next)} />

			{#if formError}
				<p class="text-sm text-destructive" role="alert">{formError}</p>
			{/if}

			<div class="flex justify-end gap-2">
				<Button type="button" variant="outline" onclick={() => (dialogOpen = false)}>Batal</Button>
				<Button type="submit" disabled={saving}>{saving ? 'Menyimpan…' : 'Simpan'}</Button>
			</div>
		</form>
	</div>
{/if}
