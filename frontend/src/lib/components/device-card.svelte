<script lang="ts">
	import { Badge } from '#lib/components/ui/badge';
	import { Button } from '#lib/components/ui/button';
	import { Card, CardContent, CardHeader, CardTitle } from '#lib/components/ui/card';
	import { format } from '#lib/format';
	import { devices, type DeviceView } from '#lib/devices';
	import { Power, PowerOff } from '@lucide/svelte';

	let {
		device,
		canControl = false,
		busy = false,
		compact = false,
		onToggle
	}: {
		device: DeviceView;
		canControl?: boolean;
		busy?: boolean;
		compact?: boolean;
		onToggle: (device: DeviceView, on: boolean) => void;
	} = $props();

	const online = $derived(devices.onlineOf(device));
	const switchOn = $derived(devices.switchOf(device));
	const hasPower = $derived('power' in (device.dps ?? {}));
	const typeLabel = $derived(
		device.type === 'bulb' ? 'Lampu' : device.type === 'plug' ? 'Smart plug' : device.type
	);
</script>

<Card class={compact ? 'gap-3 py-3' : ''}>
	<CardHeader class="flex flex-row items-start justify-between gap-2">
		<div class="min-w-0">
			<CardTitle class="flex items-center gap-2 truncate text-base">
				<span
					class="inline-block size-2 shrink-0 rounded-full {online ? 'bg-emerald-500' : 'bg-muted-foreground/40'}"
					aria-hidden="true"
				></span>
				{device.label}
			</CardTitle>
			<p class="mt-1 truncate text-xs text-muted-foreground">
				{device.name} · {typeLabel}
				{#if device.ip}· {device.ip}{/if}
			</p>
		</div>
		{#if switchOn !== null}
			<Badge variant={switchOn ? 'default' : 'secondary'}>{switchOn ? 'NYALA' : 'MATI'}</Badge>
		{:else}
			<Badge variant="outline">tidak diketahui</Badge>
		{/if}
	</CardHeader>

	<CardContent class="space-y-3">
		{#if hasPower}
			<div class="grid grid-cols-3 gap-2 text-sm">
				<div>
					<div class="text-xs text-muted-foreground">Daya</div>
					<div class="font-mono">{format.watts(device.live?.power_w)}</div>
				</div>
				<div>
					<div class="text-xs text-muted-foreground">Tegangan</div>
					<div class="font-mono">{format.volts(device.live?.voltage_v)}</div>
				</div>
				<div>
					<div class="text-xs text-muted-foreground">Arus</div>
					<div class="font-mono">{format.amps(device.live?.current_a)}</div>
				</div>
			</div>
		{/if}

		<p class="text-xs text-muted-foreground">
			{online
				? `Diperbarui ${format.age(device.live?.age_seconds)}`
				: devices.statusText({ success: online, online })}
		</p>

		{#if !compact}
			<div class="flex gap-2">
				<Button
					size="sm"
					variant={switchOn ? 'outline' : 'default'}
					disabled={!canControl || busy || !online}
					onclick={() => onToggle(device, true)}
				>
					<Power class="size-4" />
					Nyalakan
				</Button>
				<Button
					size="sm"
					variant="destructive"
					disabled={!canControl || busy || !online}
					onclick={() => onToggle(device, false)}
				>
					<PowerOff class="size-4" />
					Matikan
				</Button>
				<Button size="sm" variant="ghost" href="/devices/{device.id}">Detail</Button>
			</div>
		{/if}
	</CardContent>
</Card>
