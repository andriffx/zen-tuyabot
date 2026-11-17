<script lang="ts">
	import { Badge } from '#lib/components/ui/badge';
	import { Button } from '#lib/components/ui/button';
	import { Card, CardContent, CardHeader, CardTitle } from '#lib/components/ui/card';
	import {
		Dialog,
		DialogContent,
		DialogDescription,
		DialogFooter,
		DialogHeader,
		DialogTitle
	} from '#lib/components/ui/dialog';
	import { Input } from '#lib/components/ui/input';
	import { Label } from '#lib/components/ui/label';
	import { Skeleton } from '#lib/components/ui/skeleton';
	import {
		Table,
		TableBody,
		TableCell,
		TableHead,
		TableHeader,
		TableRow
	} from '#lib/components/ui/table';
	import { rolesApi, telegramUsersApi } from '#lib/api';
	import { ApiError } from '#lib/api/errors';
	import type { Role, TelegramUser } from '#lib/api/types';
	import { format } from '#lib/format';
	import { permissions } from '#lib/permissions';
	import { auth } from '#lib/stores/auth.svelte';
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { Plus, RefreshCw } from '@lucide/svelte';

	let users = $state<TelegramUser[]>([]);
	let roles = $state<Role[]>([]);
	let allowedRoleIds = $state<number[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let dialogOpen = $state(false);
	let saving = $state(false);

	let telegramId = $state('');
	let label = $state('');
	let roleId = $state<number | null>(null);
	let formError = $state<string | null>(null);
	let fieldErrors = $state<Record<string, string>>({});

	const canManage = $derived(auth.can('telegram_users.manage'));

	async function load() {
		loading = true;
		error = null;
		try {
			const [userList, roleList, catalog] = await Promise.all([
				telegramUsersApi.list(),
				rolesApi.list(),
				rolesApi.catalog()
			]);
			users = userList.telegram_users;
			roles = roleList.roles;
			const editable = new Set(permissions.editable(catalog, [...(auth.me?.permissions ?? [])]));
			allowedRoleIds = roles.filter((role) => role.permissions.every((key) => editable.has(key) || !auth.can('roles.manage'))).map((role) => role.id);
			roleId = allowedRoleIds[0] ?? roles[0]?.id ?? null;
		} catch (failure) {
			error = failure instanceof ApiError ? failure.detail : 'Gagal memuat user Telegram.';
		} finally {
			loading = false;
		}
	}

	async function create(event: SubmitEvent) {
		event.preventDefault();
		fieldErrors = {};
		formError = null;

		const parsed = Number(telegramId);
		if (!Number.isInteger(parsed) || parsed <= 0) {
			fieldErrors.telegram_id = 'Telegram ID harus angka positif';
			return;
		}
		if (roleId === null) {
			fieldErrors.role_id = 'Pilih role';
			return;
		}

		saving = true;
		try {
			await telegramUsersApi.create({
				telegram_id: parsed,
				label: label.trim() || null,
				role_id: roleId
			});
			toast.success('User Telegram didaftarkan');
			dialogOpen = false;
			telegramId = '';
			label = '';
			await load();
			await auth.refresh();
		} catch (failure) {
			if (failure instanceof ApiError) {
				formError = failure.detail;
				for (const field of failure.fieldErrors) fieldErrors[field.key] = field.message;
			} else {
				formError = 'Terjadi kesalahan tak terduga.';
			}
		} finally {
			saving = false;
		}
	}

	async function changeRole(user: TelegramUser, newRoleId: number) {
		try {
			await telegramUsersApi.update(user.telegram_id, { role_id: newRoleId });
			toast.success('Role diperbarui');
			await load();
		} catch (failure) {
			toast.error(failure instanceof ApiError ? failure.detail : 'Gagal mengubah role');
		}
	}

	async function toggleActive(user: TelegramUser) {
		try {
			await telegramUsersApi.update(user.telegram_id, { is_active: !user.is_active });
			await load();
		} catch (failure) {
			toast.error(failure instanceof ApiError ? failure.detail : 'Gagal mengubah status');
		}
	}

	async function remove(user: TelegramUser) {
		if (!confirm(`Hapus user Telegram ${user.telegram_id}?`)) return;
		try {
			await telegramUsersApi.remove(user.telegram_id);
			toast.success('User dihapus');
			await load();
		} catch (failure) {
			toast.error(failure instanceof ApiError ? failure.detail : 'Gagal menghapus');
		}
	}

	onMount(load);
</script>

<div class="space-y-4">
	<div class="flex flex-wrap items-center justify-between gap-2">
		<div>
			<h1 class="text-xl font-semibold">Telegram Users</h1>
			<p class="text-sm text-muted-foreground">
				Identitas bot, bukan akun web. Tidak bisa login ke dashboard.
			</p>
		</div>
		<div class="flex gap-2">
			<Button variant="outline" onclick={load}><RefreshCw class="size-4" />Segarkan</Button>
			{#if canManage}
				<Button onclick={() => (dialogOpen = true)}><Plus class="size-4" />Daftarkan</Button>
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
		<Card>
			<CardHeader><CardTitle class="text-base">Belum ada user Telegram</CardTitle></CardHeader>
			<CardContent class="text-sm text-muted-foreground">
				User yang belum terdaftar hanya mendapat /start dan /help.
			</CardContent>
		</Card>
	{:else}
		<div class="rounded-md border">
			<Table>
				<TableHeader>
					<TableRow>
						<TableHead>Telegram ID</TableHead>
						<TableHead>Label</TableHead>
						<TableHead>Role</TableHead>
						<TableHead>Status</TableHead>
						<TableHead>Terakhir aktif</TableHead>
						<TableHead class="text-right">Aksi</TableHead>
					</TableRow>
				</TableHeader>
				<TableBody>
					{#each users as user (user.telegram_id)}
						<TableRow>
							<TableCell class="font-mono text-xs">{user.telegram_id}</TableCell>
							<TableCell>{user.label ?? '-'}</TableCell>
							<TableCell>
								{#if canManage}
									<select
										class="h-8 rounded-md border border-input bg-transparent px-2 text-sm"
										value={user.role_id}
										onchange={(event) => changeRole(user, Number(event.currentTarget.value))}
									>
										{#each roles as role (role.id)}
											<option value={role.id}>{role.name}</option>
										{/each}
									</select>
								{:else}
									{user.role_name}
								{/if}
							</TableCell>
							<TableCell>
								<Badge variant={user.is_active ? 'secondary' : 'outline'}>
									{user.is_active ? 'aktif' : 'nonaktif'}
								</Badge>
							</TableCell>
							<TableCell class="text-xs text-muted-foreground">
								{format.dateTime(user.last_seen_at)}
							</TableCell>
							<TableCell class="text-right">
								{#if canManage}
									<div class="flex justify-end gap-1">
										<Button size="sm" variant="ghost" onclick={() => toggleActive(user)}>
											{user.is_active ? 'Nonaktifkan' : 'Aktifkan'}
										</Button>
										<Button size="sm" variant="ghost" onclick={() => remove(user)}>Hapus</Button>
									</div>
								{/if}
							</TableCell>
						</TableRow>
					{/each}
				</TableBody>
			</Table>
		</div>
	{/if}
</div>

<Dialog bind:open={dialogOpen}>
	<DialogContent class="sm:max-w-md">
		<form onsubmit={create}>
			<DialogHeader>
				<DialogTitle>Daftarkan user Telegram</DialogTitle>
				<DialogDescription>
					Minta pengguna mengirim /whoami ke bot untuk mengetahui Telegram ID-nya.
				</DialogDescription>
			</DialogHeader>

			<div class="space-y-3 py-4">
				<div class="space-y-1">
					<Label for="tg-id">Telegram ID</Label>
					<Input id="tg-id" bind:value={telegramId} inputmode="numeric" placeholder="123456789" />
					{#if fieldErrors.telegram_id}
						<p class="text-xs text-destructive">{fieldErrors.telegram_id}</p>
					{/if}
				</div>
				<div class="space-y-1">
					<Label for="tg-label">Label</Label>
					<Input id="tg-label" bind:value={label} placeholder="Nama panggilan" />
				</div>
				<div class="space-y-1">
					<Label for="tg-role">Role</Label>
					<select
						id="tg-role"
						class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs"
						value={roleId ?? ''}
						onchange={(event) => (roleId = Number(event.currentTarget.value))}
					>
						{#each roles.filter((role) => allowedRoleIds.includes(role.id)) as role (role.id)}
							<option value={role.id}>{role.name}</option>
						{/each}
					</select>
					{#if fieldErrors.role_id}
						<p class="text-xs text-destructive">{fieldErrors.role_id}</p>
					{/if}
				</div>
				{#if formError}
					<p class="text-sm text-destructive" role="alert">{formError}</p>
				{/if}
			</div>

			<DialogFooter>
				<Button type="button" variant="outline" onclick={() => (dialogOpen = false)}>Batal</Button>
				<Button type="submit" disabled={saving}>{saving ? 'Menyimpan…' : 'Daftarkan'}</Button>
			</DialogFooter>
		</form>
	</DialogContent>
</Dialog>
