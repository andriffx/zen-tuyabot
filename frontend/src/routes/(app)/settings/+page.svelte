<script lang="ts">
	import { Card, CardContent, CardHeader, CardTitle } from '#lib/components/ui/card';
	import { Button } from '#lib/components/ui/button';
	import { Skeleton } from '#lib/components/ui/skeleton';
	import SettingField from '#lib/components/setting-field.svelte';
	import { settingsApi } from '#lib/api';
	import { ApiError } from '#lib/api/errors';
	import { settingsForm, type SettingsForm } from '#lib/settings-form';
	import { auth } from '#lib/stores/auth.svelte';
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { RotateCcw, Save } from '@lucide/svelte';

	let form = $state<SettingsForm | null>(null);
	let loading = $state(true);
	let saving = $state(false);
	let loadError = $state<string | null>(null);
	let changes = $state(0);

	const canEdit = $derived(auth.can('settings.edit'));

	async function load() {
		loading = true;
		loadError = null;
		try {
			const response = await settingsApi.get();
			form = settingsForm.fromSchema(response.schema, response.values);
			changes = form.dirty.length;
		} catch (error) {
			loadError =
				error instanceof ApiError ? error.detail : 'Gagal memuat settings. Coba lagi.';
		} finally {
			loading = false;
		}
	}

	function update(key: string, value: unknown) {
		form?.set(key, value);
		changes = form?.dirty.length ?? 0;
	}

	function discard() {
		form?.reset();
		changes = 0;
	}

	async function save() {
		if (!form) return;

		const errors = form.validate();
		if (errors.length) {
			form.setFieldErrors(errors);
				toast.error('Periksa kembali nilai yang tidak valid');
			return;
		}

		const payload = form.toPayload();
		if (Object.keys(payload).length === 0) {
			toast.info('Tidak ada perubahan');
			return;
		}

		saving = true;
		try {
			const result = await settingsApi.patch(payload);
			const restarted = Object.keys(result.changed).some(
				(key) => form?.fields.find((field) => field.key === key)?.apply === 'telegram_restart'
			);
			toast.success(
				restarted
					? `Tersimpan. ${Object.keys(result.changed).length} setting diubah; bot dibangun ulang.`
					: `Tersimpan. ${Object.keys(result.changed).length} setting diubah.`
			);
			await load();
		} catch (error) {
			if (error instanceof ApiError) {
				form.setFieldErrors(error.fieldErrors);
						toast.error(error.detail);
			} else {
				toast.error('Gagal menyimpan settings');
			}
		} finally {
			saving = false;
		}
	}

	onMount(load);
</script>

<div class="space-y-4 pb-20">
	<div>
		<h1 class="text-xl font-semibold">Settings</h1>
		<p class="text-sm text-muted-foreground">
			Konfigurasi tersimpan di database. Badge "restart bot" menandai setting yang membangun
			ulang bot Telegram saat disimpan.
		</p>
	</div>

	{#if loadError}
		<div class="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm">
			{loadError}
			<Button variant="link" size="sm" onclick={load}>Coba lagi</Button>
		</div>
	{:else if loading || !form}
		<div class="grid gap-4 md:grid-cols-2">
			{#each Array(4) as _, index (index)}
				<Skeleton class="h-48 w-full rounded-xl" />
			{/each}
		</div>
	{:else}
		<div class="grid gap-4 md:grid-cols-2">
			{#each form.groups as group, groupIndex (group.name)}
				<Card>
					<CardHeader><CardTitle class="text-base">{group.name}</CardTitle></CardHeader>
					<CardContent class="space-y-4">
						{#each group.fields as field (field.key)}
							<SettingField {field} onChange={update} />
						{/each}
					</CardContent>
				</Card>
			{/each}
		</div>
	{/if}
</div>

{#if form && canEdit}
	<div
		class="fixed inset-x-0 bottom-0 z-20 border-t bg-background/95 px-4 py-3 backdrop-blur md:left-[var(--sidebar-width,0)]"
	>
		<div class="mx-auto flex max-w-6xl items-center justify-between gap-3">
			<p class="text-sm text-muted-foreground">
				{changes === 0 ? 'Tidak ada perubahan' : `${changes} setting berubah`}
			</p>
			<div class="flex gap-2">
				<Button variant="outline" onclick={discard} disabled={changes === 0 || saving}>
					<RotateCcw class="size-4" />
					Batalkan
				</Button>
				<Button onclick={save} disabled={changes === 0 || saving}>
					<Save class="size-4" />
					{saving ? 'Menyimpan…' : 'Simpan'}
				</Button>
			</div>
		</div>
	</div>
{/if}
