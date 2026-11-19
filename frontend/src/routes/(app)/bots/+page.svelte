<script lang="ts">
	import { Badge } from '#lib/components/ui/badge';
	import { Button } from '#lib/components/ui/button';
	import { Card, CardContent, CardHeader, CardTitle } from '#lib/components/ui/card';
	import { Skeleton } from '#lib/components/ui/skeleton';
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
	import { Switch } from '#lib/components/ui/switch';
	import { botsApi } from '#lib/api';
	import { ApiError } from '#lib/api/errors';
	import type { Bot } from '#lib/api/types';
	import { format } from '#lib/format';
	import { auth } from '#lib/stores/auth.svelte';
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { Plus, RefreshCw, Trash2 } from '@lucide/svelte';

	let bots = $state<Bot[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let busyId = $state<number | null>(null);

	let createOpen = $state(false);
	let tokenOpen = $state(false);
	let tokenTarget = $state<Bot | null>(null);
	let label = $state('');
	let token = $state('');
	let saving = $state(false);
	let formError = $state<string | null>(null);

	const canManage = $derived(auth.can('manage_devices'));

	async function load() {
		loading = true;
		error = null;
		try {
			bots = (await botsApi.list()).bots;
		} catch (failure) {
			error = failure instanceof ApiError ? failure.detail : 'Gagal memuat bot.';
		} finally {
			loading = false;
		}
	}

	async function create(event: SubmitEvent) {
		event.preventDefault();
		formError = null;
		saving = true;
		try {
			await botsApi.create(label.trim() || 'Bot', token.trim());
			toast.success('Bot ditambahkan (nonaktif). Aktifkan setelah token dipastikan benar.');
			createOpen = false;
			label = '';
			token = '';
			await load();
		} catch (failure) {
			formError = failure instanceof ApiError ? failure.detail : 'Gagal menambah bot';
		} finally {
			saving = false;
		}
	}

	function openToken(bot: Bot) {
		tokenTarget = bot;
		token = '';
		formError = null;
		tokenOpen = true;
	}

	async function replaceToken(event: SubmitEvent) {
		event.preventDefault();
		if (!tokenTarget) return;
		formError = null;
		saving = true;
		try {
			await botsApi.update(tokenTarget.id, { token: token.trim() });
			toast.success('Token diganti. Bot dibangun ulang.');
			tokenOpen = false;
			await load();
		} catch (failure) {
			formError = failure instanceof ApiError ? failure.detail : 'Gagal mengganti token';
		} finally {
			saving = false;
		}
	}

	async function toggle(bot: Bot, enabled: boolean) {
		busyId = bot.id;
		try {
			const result = enabled ? await botsApi.enable(bot.id) : await botsApi.disable(bot.id);
			toast.success(`Bot ${enabled ? 'diaktifkan' : 'dinonaktifkan'} (${result.status})`);
			await load();
		} catch (failure) {
			toast.error(failure instanceof ApiError ? failure.detail : 'Gagal mengubah status bot');
		} finally {
			busyId = null;
		}
	}

	async function test(bot: Bot) {
		busyId = bot.id;
		try {
			const result = await botsApi.test(bot.id);
			if (result.ok) toast.success(`Token valid: @${result.username}`);
			else toast.error(result.message ?? 'Token tidak valid');
		} catch (failure) {
			toast.error(failure instanceof ApiError ? failure.detail : 'Uji token gagal');
		} finally {
			busyId = null;
		}
	}

	async function remove(bot: Bot) {
		if (!confirm(`Hapus bot "${bot.label}"? Token tidak bisa dipulihkan.`)) return;
		try {
			await botsApi.remove(bot.id);
			toast.success('Bot dihapus');
			await load();
		} catch (failure) {
			toast.error(failure instanceof ApiError ? failure.detail : 'Gagal menghapus bot');
		}
	}

	const statusVariant = (status: string): 'default' | 'secondary' | 'destructive' | 'outline' => {
		if (status === 'running') return 'default';
		if (status === 'error') return 'destructive';
		if (status === 'starting' || status === 'stopping') return 'secondary';
		return 'outline';
	};

	onMount(load);
</script>

<div class="space-y-4">
	<div class="flex flex-wrap items-center justify-between gap-2">
		<div>
			<h1 class="text-xl font-semibold">Bots</h1>
			<p class="text-sm text-muted-foreground">
				Beberapa bot dapat aktif bersamaan. Token hanya bisa ditulis, tidak pernah ditampilkan.
			</p>
		</div>
		<div class="flex gap-2">
			<Button variant="outline" onclick={load}><RefreshCw class="size-4" />Segarkan</Button>
			{#if canManage}
				<Button onclick={() => (createOpen = true)}><Plus class="size-4" />Tambah bot</Button>
			{/if}
		</div>
	</div>

	{#if error}
		<div class="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm">
			{error}
			<Button variant="link" size="sm" onclick={load}>Coba lagi</Button>
		</div>
	{:else if loading}
		<div class="grid gap-4 md:grid-cols-2">
			{#each Array(2) as _, index (index)}
				<Skeleton class="h-44 w-full rounded-xl" />
			{/each}
		</div>
	{:else if bots.length === 0}
		<div class="rounded-lg border border-dashed p-10 text-center">
			<p class="text-sm text-muted-foreground">Belum ada bot Telegram.</p>
			{#if canManage}
				<Button class="mt-3" onclick={() => (createOpen = true)}>Tambah bot pertama</Button>
			{/if}
		</div>
	{:else}
		<div class="grid gap-4 md:grid-cols-2">
			{#each bots as bot (bot.id)}
				<Card>
					<CardHeader class="flex flex-row items-start justify-between gap-2">
						<div class="min-w-0">
							<CardTitle class="truncate text-base">{bot.label}</CardTitle>
							<p class="mt-1 text-xs text-muted-foreground">
								{bot.bot_username ?? 'username belum diketahui'}
							</p>
						</div>
						<Badge variant={statusVariant(bot.runtime_status)}>{bot.runtime_status}</Badge>
					</CardHeader>
					<CardContent class="space-y-3 text-sm">
						<div class="flex items-center gap-2">
							<Switch
								checked={bot.enabled}
								disabled={!canManage || busyId === bot.id}
								onCheckedChange={(checked) => toggle(bot, checked === true)}
							/>
							<span class="text-xs text-muted-foreground">
								{bot.enabled ? 'aktif' : 'nonaktif'}
							</span>
							<span class="ml-auto text-xs text-muted-foreground">
								OK terakhir: {format.dateTime(bot.last_ok_at)}
							</span>
						</div>

						{#if bot.last_error}
							<details class="rounded bg-destructive/5 p-2">
								<summary class="cursor-pointer text-xs font-medium text-destructive">
									Error terakhir
								</summary>
								<pre class="mt-1 overflow-x-auto whitespace-pre-wrap font-mono text-[11px]">{bot.last_error}</pre>
							</details>
						{/if}

						{#if canManage}
							<div class="flex flex-wrap gap-2">
								<Button size="sm" variant="outline" onclick={() => test(bot)} disabled={busyId === bot.id}>
									Uji
								</Button>
								<Button size="sm" variant="outline" onclick={() => openToken(bot)}>Ganti token</Button>
								<Button size="sm" variant="ghost" onclick={() => remove(bot)}>
									<Trash2 class="size-4" />
								</Button>
							</div>
						{/if}
					</CardContent>
				</Card>
			{/each}
		</div>
	{/if}
</div>

<Dialog bind:open={createOpen}>
	<DialogContent class="sm:max-w-md">
		<form onsubmit={create}>
			<DialogHeader>
				<DialogTitle>Tambah bot</DialogTitle>
				<DialogDescription>
					Token dari @BotFather. Bot ditambahkan nonaktif agar bisa diuji dulu.
				</DialogDescription>
			</DialogHeader>
			<div class="space-y-3 py-4">
				<div class="space-y-1">
					<Label for="bot-label">Label</Label>
					<Input id="bot-label" bind:value={label} placeholder="produksi" />
				</div>
				<div class="space-y-1">
					<Label for="bot-token">Token</Label>
					<Input id="bot-token" type="password" bind:value={token} required />
					<p class="text-xs text-muted-foreground">Tidak bisa dibaca kembali setelah disimpan.</p>
				</div>
				{#if formError}
					<p class="text-sm text-destructive" role="alert">{formError}</p>
				{/if}
			</div>
			<DialogFooter>
				<Button type="button" variant="outline" onclick={() => (createOpen = false)}>Batal</Button>
				<Button type="submit" disabled={saving}>{saving ? 'Menyimpan…' : 'Simpan'}</Button>
			</DialogFooter>
		</form>
	</DialogContent>
</Dialog>

<Dialog bind:open={tokenOpen}>
	<DialogContent class="sm:max-w-md">
		<form onsubmit={replaceToken}>
			<DialogHeader>
				<DialogTitle>Ganti token — {tokenTarget?.label}</DialogTitle>
				<DialogDescription>
					Token lama tidak bisa ditampilkan. Menyimpan token baru akan membangun ulang bot ini
					saja.
				</DialogDescription>
			</DialogHeader>
			<div class="space-y-3 py-4">
				<div class="space-y-1">
					<Label for="new-token">Token baru</Label>
					<Input id="new-token" type="password" bind:value={token} required />
				</div>
				{#if formError}
					<p class="text-sm text-destructive" role="alert">{formError}</p>
				{/if}
			</div>
			<DialogFooter>
				<Button type="button" variant="outline" onclick={() => (tokenOpen = false)}>Batal</Button>
				<Button type="submit" disabled={saving}>{saving ? 'Menyimpan…' : 'Ganti token'}</Button>
			</DialogFooter>
		</form>
	</DialogContent>
</Dialog>
