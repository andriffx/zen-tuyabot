<script lang="ts">
	import { Alert, AlertDescription, AlertTitle } from '#lib/components/ui/alert';
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
	import RestoreDialog from '#lib/components/restore-dialog.svelte';
	import { backupApi } from '#lib/api';
	import { ApiError } from '#lib/api/errors';
	import type { BackupRun } from '#lib/api/types';
	import { format } from '#lib/format';
	import { auth } from '#lib/stores/auth.svelte';
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { DatabaseBackup, Download, RefreshCw } from '@lucide/svelte';

	let backups = $state<BackupRun[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let busyId = $state<number | null>(null);
	let creating = $state(false);
	let restoreOpen = $state(false);

	const canCreate = $derived(auth.can('manage_devices'));
	const canRestore = $derived(auth.can('manage_devices'));

	async function load() {
		loading = true;
		error = null;
		try {
			backups = (await backupApi.list()).backups;
		} catch (failure) {
			error = failure instanceof ApiError ? failure.detail : 'Gagal memuat daftar backup.';
		} finally {
			loading = false;
		}
	}

	async function create() {
		creating = true;
		try {
			const result = await backupApi.create();
			toast.success(`Backup dibuat: ${result.filename}`);
			await load();
		} catch (failure) {
			toast.error(failure instanceof ApiError ? failure.detail : 'Gagal membuat backup');
		} finally {
			creating = false;
		}
	}

	async function download(run: BackupRun) {
		busyId = run.id;
		try {
			await backupApi.download(run.id, run.filename);
		} catch (failure) {
			toast.error(failure instanceof ApiError ? failure.detail : 'Gagal mengunduh backup');
		} finally {
			busyId = null;
		}
	}

	const kindLabel: Record<BackupRun['kind'], string> = {
		auto: 'otomatis',
		manual: 'manual',
		pre_restore: 'sebelum restore'
	};

	onMount(load);
</script>

<div class="space-y-4">
	<div class="flex flex-wrap items-center justify-between gap-2">
		<div>
			<h1 class="text-xl font-semibold">Backup</h1>
			<p class="text-sm text-muted-foreground">
				Salinan konsisten database. Unduhan berisi seluruh data termasuk rahasia.
			</p>
		</div>
		<div class="flex gap-2">
			<Button variant="outline" onclick={load}><RefreshCw class="size-4" />Segarkan</Button>
			{#if canCreate}
				<Button onclick={create} disabled={creating}>
					<DatabaseBackup class="size-4" />
					{creating ? 'Membuat…' : 'Buat backup'}
				</Button>
			{/if}
		</div>
	</div>

	{#if canRestore}
		<Alert>
			<AlertTitle>Restore tersedia</AlertTitle>
			<AlertDescription class="flex flex-wrap items-center justify-between gap-2">
				<span>
					Mengganti seluruh database dengan isi backup. Sistem masuk maintenance dan semua sesi
					dicabut.
				</span>
				<Button variant="destructive" size="sm" onclick={() => (restoreOpen = true)}>
					Restore…
				</Button>
			</AlertDescription>
		</Alert>
	{/if}

	{#if error}
		<Alert variant="destructive">
			<AlertTitle>Gagal memuat</AlertTitle>
			<AlertDescription>{error}</AlertDescription>
		</Alert>
	{:else if loading}
		<Skeleton class="h-48 w-full rounded-xl" />
	{:else if backups.length === 0}
		<div class="rounded-lg border border-dashed p-10 text-center text-sm text-muted-foreground">
			Belum ada backup. Backup otomatis berjalan sesuai interval di Settings.
		</div>
	{:else}
		<div class="overflow-x-auto rounded-md border">
			<Table>
				<TableHeader>
					<TableRow>
						<TableHead>File</TableHead>
						<TableHead>Jenis</TableHead>
						<TableHead class="text-right">Ukuran</TableHead>
						<TableHead>Dibuat</TableHead>
						<TableHead class="text-right">Aksi</TableHead>
					</TableRow>
				</TableHeader>
				<TableBody>
					{#each backups as run (run.id)}
						<TableRow>
							<TableCell class="font-mono text-xs">{run.filename}</TableCell>
							<TableCell>
								<Badge variant={run.kind === 'pre_restore' ? 'outline' : 'secondary'}>
									{kindLabel[run.kind]}
								</Badge>
							</TableCell>
							<TableCell class="text-right font-mono">{format.bytes(run.size_bytes)}</TableCell>
							<TableCell class="text-xs">{format.dateTime(run.created_at)}</TableCell>
							<TableCell class="text-right">
								{#if canRestore}
									<Button
										size="sm"
										variant="outline"
										disabled={busyId === run.id}
										onclick={() => download(run)}
									>
										<Download class="size-4" />
										Unduh
									</Button>
								{:else}
									<span class="text-xs text-muted-foreground">perlu izin restore</span>
								{/if}
							</TableCell>
						</TableRow>
					{/each}
				</TableBody>
			</Table>
		</div>
	{/if}
</div>

<RestoreDialog bind:open={restoreOpen} onRestored={load} />
