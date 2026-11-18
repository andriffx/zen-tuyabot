<script lang="ts">
	import { devicesApi } from '#lib/api';
	import type { Device } from '#lib/api/types';
	import { onMount } from 'svelte';
	import {
		Select,
		SelectContent,
		SelectItem,
		SelectTrigger,
		SelectValue
	} from '#lib/components/ui/select';


	let {
		value = $bindable<number | null>(null),
		onChange
	}: { value?: number | null; onChange?: (deviceId: number | null) => void } = $props();

	let devices = $state<Device[]>([]);

	// The device list is not known until load finishes, so the label list has to be
	// derived: without `items` the trigger would render the device's id, not its label.
	const items = $derived([
		{ value: 'all', label: 'Semua' },
		...devices.map((device) => ({ value: String(device.id), label: device.label }))
	]);

	onMount(async () => {
		try {
			devices = (await devicesApi.list()).devices;
		} catch {
			devices = [];
		}
	});

	function change(next: string) {
		value = next === 'all' ? null : Number(next);
		onChange?.(value);
	}
</script>

<label class="flex items-center gap-2 text-sm">
	<span class="text-muted-foreground">Perangkat</span>
	<Select
		type="single"
		{items}
		value={value === null ? 'all' : String(value)}
		onValueChange={(next) => change(next ?? 'all')}
	>
		<SelectTrigger size="sm" class="min-w-40">
			<SelectValue placeholder="Semua" />
		</SelectTrigger>
		<SelectContent>
			<SelectItem value="all" label="Semua">Semua</SelectItem>
			{#each devices as device (device.id)}
				<SelectItem value={String(device.id)} label={device.label}>{device.label}</SelectItem>
			{/each}
		</SelectContent>
	</Select>
</label>
