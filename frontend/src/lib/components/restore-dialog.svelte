<script lang="ts">
	import { Alert, AlertDescription, AlertTitle } from '#lib/components/ui/alert';
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
	import { backupApi } from '#lib/api';
	import { ApiError } from '#lib/api/errors';
	import { backupForm, restoreStageText, type RestoreForm } from '#lib/backup-form';
	import { toast } from 'svelte-sonner';

	let {
		open = $bindable(false),
		onRestored
	}: { open?: boolean; onRestored: () => void } = $props();

	const form = backupForm.restore();
	// `form` mutates in place, so Svelte cannot see `valid` change. Mirror the
	// inputs into reactive state and derive validity from those.
	let password = $state('');
	let confirm = $state('');
	let fileName = $state<string | null>(null);

	let submitError = $state<string | null>(null);
	let stage = $state<string | null>(null);
	let uploading = $state(false);

	const valid = $derived(
		Boolean(fileName) &&
			password.length > 0 &&
			confirm.trim().toUpperCase() === 'RESTORE'
	);

	$effect(() => {
		if (!open) {
			form.reset();
			password = '';
			confirm = '';
			fileName = null;
			submitError = null;
			stage = null;
			uploading = false;
		}
	});

	function pickFile(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		const file = input.files?.[0] ?? null;
		const problem = form.setFile(file);
		if (problem) {
			fileName = null;
			toast.error(problem);
			return;
		}
		fileName = file?.name ?? null;
	}

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		submitError = null;
		stage = null;

		if (!valid || !form.file) {
			submitError = 'Pilih file, isi password, dan ketik RESTORE untuk konfirmasi.';
			return;
		}

		uploading = true;
		try {
			const result = await backupApi.restore(form.toFormData());
			toast.success(
				`Restore selesai. Skema ${result.from_version} → ${result.schema_version}.`
			);
			open = false;
			onRestored();
		} catch (failure) {
			if (failure instanceof ApiError) {
				stage = failure.stage ?? null;
				submitError = stage
					? (restoreStageText[stage] ?? failure.detail)
					: failure.detail;
			} else {
				submitError = 'Restore gagal tanpa keterangan.';
			}
			// The server keeps maintenance on after a failed restore.
			toast.error('Restore gagal. Sistem tetap dalam maintenance.');
		} finally {
			uploading = false;
		}
	}
</script>

<Dialog bind:open>
	<DialogContent class="sm:max-w-md">
		<form onsubmit={submit}>
			<DialogHeader>
				<DialogTitle>Restore database</DialogTitle>
				<DialogDescription>
					Seluruh data saat ini diganti dengan isi file backup. Semua sesi dicabut dan sistem
					masuk maintenance selama proses.
				</DialogDescription>
			</DialogHeader>

			<div class="space-y-3 py-4">
				<div class="space-y-1">
					<Label for="restore-file">File backup (.db)</Label>
					<Input id="restore-file" type="file" accept=".db,application/octet-stream" onchange={pickFile} />
					<p class="text-xs text-muted-foreground">Maksimal 200 MB.</p>
					{#if form.error}
						<p class="text-xs text-destructive">{form.error}</p>
					{/if}
				</div>

				<div class="space-y-1">
					<Label for="restore-password">Password akun Anda</Label>
					<Input
						id="restore-password"
						type="password"
						autocomplete="current-password"
						value={password}
						oninput={(event) => {
							password = event.currentTarget.value;
							form.setPassword(password);
						}}
						required
					/>
				</div>

				<div class="space-y-1">
					<Label for="restore-confirm">Ketik RESTORE</Label>
					<Input
						id="restore-confirm"
						value={confirm}
						oninput={(event) => {
							confirm = event.currentTarget.value;
							form.setConfirm(confirm);
						}}
						placeholder="RESTORE"
						required
					/>
				</div>

				{#if submitError}
					<Alert variant="destructive">
						<AlertTitle>Restore gagal{stage ? ` (${stage})` : ''}</AlertTitle>
						<AlertDescription>{submitError}</AlertDescription>
					</Alert>
				{/if}
			</div>

			<DialogFooter>
				<Button type="button" variant="outline" onclick={() => (open = false)}>Batal</Button>
				<Button type="submit" variant="destructive" disabled={uploading || !valid || !form.file}>
					{uploading ? 'Memulihkan…' : 'Restore'}
				</Button>
			</DialogFooter>
		</form>
	</DialogContent>
</Dialog>
