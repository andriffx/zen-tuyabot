<script lang="ts">
	import { Button } from '#lib/components/ui/button';
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
	import {
		Select,
		SelectContent,
		SelectItem,
		SelectTrigger,
		SelectValue
	} from '#lib/components/ui/select';
	import { usersApi } from '#lib/api';
	import { ApiError } from '#lib/api/errors';
	import type { Role, WebUser } from '#lib/api/types';
	import { toast } from 'svelte-sonner';

	let {
		open = $bindable(false),
		user = null,
		roles = [],
		onSaved
	}: { open?: boolean; user?: WebUser | null; roles?: Role[]; onSaved: () => void } = $props();

	const editing = $derived(Boolean(user));

	// bits-ui can only label a value it has seen; without `items` the trigger
	// renders the raw id ("2") until the menu has been opened once.
	const roleItems = $derived(roles.map((role) => ({ value: String(role.id), label: role.name })));

	let username = $state('');
	let password = $state('');
	let roleId = $state<number | null>(null);
	let fieldErrors = $state<Record<string, string>>({});
	let formError = $state<string | null>(null);
	let saving = $state(false);

	$effect(() => {
		if (!open) return;
		username = user?.username ?? '';
		password = '';
		roleId = user?.role_id ?? roles[0]?.id ?? null;
		fieldErrors = {};
		formError = null;
	});

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		fieldErrors = {};
		formError = null;

		if (roleId === null) {
			fieldErrors.role_id = 'Pilih role';
			return;
		}

		saving = true;
		try {
			if (user) {
				await usersApi.update(user.id, {
					role_id: roleId,
					...(password ? { password } : {})
				});
				toast.success('Akun diperbarui');
			} else {
				await usersApi.create({ username: username.trim(), password, role_id: roleId });
				toast.success('Akun dibuat');
			}
			open = false;
			onSaved();
		} catch (error) {
			if (error instanceof ApiError) {
				formError = error.detail;
				for (const field of error.fieldErrors) fieldErrors[field.key] = field.message;
			} else {
				formError = 'Terjadi kesalahan tak terduga.';
			}
		} finally {
			saving = false;
		}
	}
</script>

<Dialog bind:open>
	<DialogContent class="sm:max-w-md">
		<form onsubmit={submit}>
			<DialogHeader>
				<DialogTitle>{editing ? `Ubah ${user?.username}` : 'Tambah akun web'}</DialogTitle>
				<DialogDescription>
					Akun web dipakai untuk masuk ke dashboard. Berbeda dari user Telegram.
				</DialogDescription>
			</DialogHeader>

			<div class="space-y-3 py-4">
				{#if !editing}
					<div class="space-y-1">
						<Label for="user-name">Username</Label>
						<Input id="user-name" bind:value={username} autocomplete="off" required />
						{#if fieldErrors.username}
							<p class="text-xs text-destructive">{fieldErrors.username}</p>
						{/if}
					</div>
				{/if}

				<div class="space-y-1">
					<Label for="user-pass">{editing ? 'Password baru (opsional)' : 'Password'}</Label>
					<Input
						id="user-pass"
						type="password"
						bind:value={password}
						autocomplete="new-password"
						required={!editing}
					/>
					<p class="text-xs text-muted-foreground">
						Minimal 8 karakter. Mengubah password mencabut sesi akun ini.
					</p>
					{#if fieldErrors.password}
						<p class="text-xs text-destructive">{fieldErrors.password}</p>
					{/if}
				</div>

				<div class="space-y-1">
					<Label for="user-role">Role</Label>
					<Select
						type="single"
						items={roleItems}
						value={roleId === null ? '' : String(roleId)}
						onValueChange={(next) => (roleId = next ? Number(next) : null)}
					>
						<SelectTrigger id="user-role" class="w-full">
							<SelectValue placeholder="Pilih role" />
						</SelectTrigger>
						<SelectContent>
							{#each roles as role (role.id)}
								<SelectItem value={String(role.id)} label={role.name}>{role.name}</SelectItem>
							{/each}
						</SelectContent>
					</Select>
					{#if fieldErrors.role_id}
						<p class="text-xs text-destructive">{fieldErrors.role_id}</p>
					{/if}
				</div>

				{#if formError}
					<p class="text-sm text-destructive" role="alert">{formError}</p>
				{/if}
			</div>

			<DialogFooter>
				<Button type="button" variant="outline" onclick={() => (open = false)}>Batal</Button>
				<Button type="submit" disabled={saving}>{saving ? 'Menyimpan…' : 'Simpan'}</Button>
			</DialogFooter>
		</form>
	</DialogContent>
</Dialog>
