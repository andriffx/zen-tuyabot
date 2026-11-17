<script lang="ts">
	import { Badge } from '#lib/components/ui/badge';
	import { Button } from '#lib/components/ui/button';
	import { Skeleton } from '#lib/components/ui/skeleton';
	import {
		Table,
		TableBody,
		TableCell,
		TableHead,
		TableHeader,
		TableRow
	} from '#lib/components/ui/table';
	import UserDialog from '#lib/components/user-dialog.svelte';
	import { rolesApi, usersApi } from '#lib/api';
	import { ApiError } from '#lib/api/errors';
	import type { Role, WebUser } from '#lib/api/types';
	import { format } from '#lib/format';
	import { auth } from '#lib/stores/auth.svelte';
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { Plus, RefreshCw } from '@lucide/svelte';

	let users = $state<WebUser[]>([]);
	let roles = $state<Role[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let rowError = $state<Record<number, string>>({});

	let dialogOpen = $state(false);
	let editing = $state<WebUser | null>(null);

	const canManage = $derived(auth.can('users.manage'));

	async function load() {
		loading = true;
		error = null;
		try {
			const [userList, roleList] = await Promise.all([usersApi.list(), rolesApi.list()]);
			users = userList.users;
			roles = roleList.roles;
		} catch (failure) {
			error = failure instanceof ApiError ? failure.detail : 'Gagal memuat akun.';
		} finally {
			loading = false;
		}
	}

	async function toggleActive(user: WebUser) {
		rowError = { ...rowError, [user.id]: '' };
		try {
			await usersApi.update(user.id, { is_active: !user.is_active });
			toast.success(user.is_active ? 'Akun dinonaktifkan' : 'Akun diaktifkan');
			await load();
			// Permissions may have changed for the current account.
			await auth.refresh();
		} catch (failure) {
			const message = failure instanceof ApiError ? failure.detail : 'Gagal mengubah status';
			rowError = { ...rowError, [user.id]: message };
		}
	}

	async function remove(user: WebUser) {
		if (!confirm(`Hapus akun "${user.username}"?`)) return;
		try {
			await usersApi.remove(user.id);
			toast.success('Akun dihapus');
			await load();
		} catch (failure) {
			toast.error(failure instanceof ApiError ? failure.detail : 'Gagal menghapus');
		}
	}

	function openCreate() {
		editing = null;
		dialogOpen = true;
	}

	function openEdit(user: WebUser) {
		editing = user;
		dialogOpen = true;
	}

	onMount(load);
</script>

<div class="space-y-4">
	<div class="flex flex-wrap items-center justify-between gap-2">
		<div>
			<h1 class="text-xl font-semibold">Users</h1>
			<p class="text-sm text-muted-foreground">
				Akun web untuk dashboard. User Telegram dikelola terpisah.
			</p>
		</div>
		<div class="flex gap-2">
			<Button variant="outline" onclick={load}><RefreshCw class="size-4" />Segarkan</Button>
			{#if canManage}
				<Button onclick={openCreate}><Plus class="size-4" />Tambah akun</Button>
			{/if}
		</div>
	</div>

	{#if error}
		<div class="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm">
			{error}
			<Button variant="link" size="sm" onclick={load}>Coba lagi</Button>
		</div>
	{:else if loading}
		<Skeleton class="h-48 w-full rounded-xl" />
	{:else if users.length === 0}
		<div class="rounded-lg border border-dashed p-10 text-center text-sm text-muted-foreground">
			Belum ada akun web.
		</div>
	{:else}
		<div class="rounded-md border">
			<Table>
				<TableHeader>
					<TableRow>
						<TableHead>Username</TableHead>
						<TableHead>Role</TableHead>
						<TableHead>Status</TableHead>
						<TableHead>Login terakhir</TableHead>
						<TableHead class="text-right">Aksi</TableHead>
					</TableRow>
				</TableHeader>
				<TableBody>
					{#each users as user (user.id)}
						<TableRow>
							<TableCell class="font-medium">{user.username}</TableCell>
							<TableCell>{user.role?.name ?? '-'}</TableCell>
							<TableCell>
								<Badge variant={user.is_active ? 'secondary' : 'outline'}>
									{user.is_active ? 'aktif' : 'nonaktif'}
								</Badge>
							</TableCell>
							<TableCell class="text-xs text-muted-foreground">
								{format.dateTime(user.last_login_at)}
							</TableCell>
							<TableCell class="text-right">
								{#if canManage}
									<div class="flex justify-end gap-1">
										<Button size="sm" variant="ghost" onclick={() => openEdit(user)}>Ubah</Button>
										<Button size="sm" variant="ghost" onclick={() => toggleActive(user)}>
											{user.is_active ? 'Nonaktifkan' : 'Aktifkan'}
										</Button>
										<Button size="sm" variant="ghost" onclick={() => remove(user)}>Hapus</Button>
									</div>
									{#if rowError[user.id]}
										<p class="mt-1 text-xs text-destructive">{rowError[user.id]}</p>
									{/if}
								{:else}
									<span class="text-xs text-muted-foreground">-</span>
								{/if}
							</TableCell>
						</TableRow>
					{/each}
				</TableBody>
			</Table>
		</div>
	{/if}
</div>

<UserDialog bind:open={dialogOpen} user={editing} {roles} onSaved={load} />
