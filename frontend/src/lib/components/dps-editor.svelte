<script lang="ts">
	import { Input } from '#lib/components/ui/input';
	import { Label } from '#lib/components/ui/label';
	import type { DeviceTemplates } from '#lib/api/types';

	let {
		dps = $bindable<Record<string, number>>({}),
		templates,
		type = $bindable('plug')
	}: {
		dps?: Record<string, number>;
		templates: DeviceTemplates | null;
		type?: string;
	} = $props();

	const template = $derived(templates?.templates?.[type as keyof DeviceTemplates['templates']] ?? {});

	function resetToTemplate() {
		dps = { ...template };
	}

	function update(key: string, raw: string) {
		const value = raw === '' ? Number.NaN : Number(raw);
		const next = { ...dps };
		if (Number.isInteger(value) && value >= 0) next[key] = value;
		else delete next[key];
		dps = next;
	}
</script>

<div class="space-y-3">
	<div class="flex items-center justify-between">
		<p class="text-sm font-medium">Pemetaan DPS</p>
		<button type="button" class="text-xs underline underline-offset-2" onclick={resetToTemplate}>
			Reset ke template {type}
		</button>
	</div>
	<p class="text-xs text-muted-foreground">
		Isi nomor DP dari perangkat. Kosongkan yang tidak dipakai.
	</p>

	<div class="grid grid-cols-2 gap-3">
		{#each Object.keys(template.length ? template : { switch: 1 }) as key (key)}
			<div class="space-y-1">
				<Label for="dps-{key}" class="text-xs">{key}</Label>
				<Input
					id="dps-{key}"
					type="number"
					min="0"
					step="1"
					value={dps[key] ?? ''}
					oninput={(event) => update(key, (event.currentTarget as HTMLInputElement).value)}
				/>
			</div>
		{/each}
	</div>
	{#if Object.keys(dps).length === 0}
		<p class="text-xs text-amber-600">Belum ada DP yang dipetakan; perangkat tidak bisa dikontrol.</p>
	{/if}
</div>
