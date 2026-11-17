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
	import { ApiError } from '#lib/api/errors';
	import { authApi } from '#lib/api';
	import { toast } from 'svelte-sonner';

	let { open = $bindable(false) } = $props();

	let currentPassword = $state('');
	let newPassword = $state('');
	let confirm = $state('');
	let pending = $state(false);
	let fieldErrors = $state<Record<string, string>>({});
	let formError = $state<string | null>(null);

	$effect(() => {
		if (!open) {
			currentPassword = '';
			newPassword = '';
			confirm = '';
			fieldErrors = {};
			formError = null;
		}
	});

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		fieldErrors = {};
		formError = null;

		if (newPassword !== confirm) {
			fieldErrors.confirm = 'Konfirmasi password tidak sama';
			return;
		}

		pending = true;
		try {
			const result = await authApi.changePassword(currentPassword, newPassword);
			toast.success(
				result.sessions_revoked > 0
					? `Password diubah. ${result.sessions_revoked} sesi lain dicabut.`
					: 'Password diubah'
			);
			open = false;
		} catch (error) {
			if (error instanceof ApiError) {
				formError = error.detail;
				for (const field of error.fieldErrors) fieldErrors[field.key] = field.message;
			} else {
				formError = 'Terjadi kesalahan tak terduga.';
			}
		} finally {
			pending = false;
		}
	}
</script>

<Dialog bind:open>
	<DialogContent class="sm:max-w-md">
		<form onsubmit={submit}>
			<DialogHeader>
				<DialogTitle>Ubah password</DialogTitle>
				<DialogDescription>
					Sesi Anda yang lain akan dicabut setelah password berubah.
				</DialogDescription>
			</DialogHeader>

			<div class="space-y-3 py-4">
				<div class="space-y-2">
					<Label for="current-password">Password saat ini</Label>
					<Input id="current-password" type="password" bind:value={currentPassword} required />
				</div>
				<div class="space-y-2">
					<Label for="new-password">Password baru</Label>
					<Input id="new-password" type="password" bind:value={newPassword} required />
					<p class="text-xs text-muted-foreground">Minimal 8 karakter.</p>
					{#if fieldErrors.new_password}
						<p class="text-sm text-destructive">{fieldErrors.new_password}</p>
					{/if}
				</div>
				<div class="space-y-2">
					<Label for="confirm-password">Ulangi password baru</Label>
					<Input id="confirm-password" type="password" bind:value={confirm} required />
					{#if fieldErrors.confirm}
						<p class="text-sm text-destructive">{fieldErrors.confirm}</p>
					{/if}
				</div>
				{#if formError}
					<p class="text-sm text-destructive" role="alert">{formError}</p>
				{/if}
			</div>

			<DialogFooter>
				<Button type="button" variant="outline" onclick={() => (open = false)}>Batal</Button>
				<Button type="submit" disabled={pending}>{pending ? 'Menyimpan…' : 'Simpan'}</Button>
			</DialogFooter>
		</form>
	</DialogContent>
</Dialog>
