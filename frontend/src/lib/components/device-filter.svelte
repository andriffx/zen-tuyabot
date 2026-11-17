<script lang="ts">
	import { devicesApi } from '#lib/api';
	import type { Device } from '#lib/api/types';
	import { onMount } from 'svelte';

	let {
		value = $bindable<number | null>(null),
		onChange
	}: { value?: number | null; onChange?: (deviceId: number | null) => void } = $props();

	let devices = $state<Device[]>([]);

	onMount(async () => {
		try {
			devices = (await devicesApi.list()).devices;
		} catch {
			devices = [];
		}
	});

	function change(next: string) {
		value = next === '' ? null : Number(next);
		onChange?.(value);
	}
</script>

<label class="flex items-center gap-2 text-sm">
	<span class="text-muted-foreground">Perangkat</span>
	<select
		class="h-8 rounded-md border border-input bg-transparent px-2 text-sm"
		value={value ?? ''}
		onchange={(event) => change(event.currentTarget.value)}
	>
		<option value="">Semua</option>
		{#each devices as device (device.id)}
			<option value={device.id}>{device.label}</option>
		{/each}
	</select>
</label>
