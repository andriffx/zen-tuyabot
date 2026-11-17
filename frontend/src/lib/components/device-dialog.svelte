<script lang="ts">
	import { Button } from '#lib/components/ui/button';
	import { Checkbox } from '#lib/components/ui/checkbox';
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
	import DpsEditor from '#lib/components/dps-editor.svelte';
	import {
		Select,
		SelectContent,
		SelectItem,
		SelectTrigger,
		SelectValue
	} from '#lib/components/ui/select';

	import { devicesApi } from '#lib/api';
	import { ApiError } from '#lib/api/errors';
	import type { Device, DeviceTemplates, Role, ScanCandidate } from '#lib/api/types';
	import { devices, type DeviceFormPayload } from '#lib/devices';
	import { toast } from 'svelte-sonner';

	let {
		open = $bindable(false),
		device = null,
		templates = null,
		roles = [],
		prefill = null,
		onSaved
	}: {
		open?: boolean;
		device?: Device | null;
		templates?: DeviceTemplates | null;
		roles?: Role[];
		prefill?: ScanCandidate | null;
		onSaved: () => void;
	} = $props();

	const editing = $derived(Boolean(device));

	let name = $state('');
	let label = $state('');
	let tuyaId = $state('');
	let localKey = $state('');
	let ip = $state('');
	let version = $state('3.5');
	let type = $state('plug');
	let dps = $state<Record<string, number>>({});
	let features = $state<Record<string, boolean>>({});
	let accessRoles = $state<number[]>([]);
	let fieldErrors = $state<Record<string, string>>({});
	let formError = $state<string | null>(null);
	let saving = $state(false);

	$effect(() => {
		if (!open) return;
		if (device) {
			name = device.name;
			label = device.label;
			ip = device.ip ?? '';
			version = String(device.version);
			type = device.type;
			dps = { ...device.dps };
			features = { ...device.features };
			accessRoles = [...device.access_roles];
			tuyaId = '';
			localKey = '';
		} else {
			name = '';
			label = '';
			ip = prefill?.ip ?? '';
			version = prefill?.version ? String(prefill.version) : '3.5';
			type = 'plug';
			dps = { ...(templates?.templates.plug ?? {}) };
			features = {};
			accessRoles = [];
			tuyaId = prefill?.tuya_id ?? '';
			localKey = '';
		}
		fieldErrors = {};
		formError = null;
	});

	function toggleFeature(key: string) {
		features = { ...features, [key]: !features[key] };
	}

	function toggleRole(roleId: number) {
		accessRoles = accessRoles.includes(roleId)
			? accessRoles.filter((id) => id !== roleId)
			: [...accessRoles, roleId];
	}

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		fieldErrors = {};
		formError = null;

		const payload: DeviceFormPayload = {
			name: name.trim() || undefined,
			label: label.trim() || undefined,
			tuya_id: tuyaId.trim() || undefined,
			local_key: localKey.trim() || undefined,
			ip: ip.trim() || undefined,
			version: Number(version),
			type,
			dps,
			features,
			access_roles: accessRoles
		};

		const errors = devices.validation(payload, { editing });
		if (errors.length) {
			for (const error of errors) fieldErrors[error.key] = error.message;
			return;
		}

		saving = true;
		try {
			if (device) {
				const body = { ...payload };
				if (!body.local_key) delete body.local_key;
				delete body.name; // the slug is immutable once created
				await devicesApi.update(device.id, body);
				toast.success('Perangkat diperbarui');
			} else {
				await devicesApi.create(payload);
				toast.success('Perangkat ditambahkan');
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
	<DialogContent class="max-h-[90svh] overflow-y-auto sm:max-w-2xl">
		<form onsubmit={submit}>
			<DialogHeader>
				<DialogTitle>{editing ? `Ubah ${device?.label}` : 'Tambah device'}</DialogTitle>
				<DialogDescription>
					{editing
						? 'Kosongkan local key bila tidak ingin mengubahnya.'
						: 'Data diambil dari perangkat atau hasil scan LAN.'}
				</DialogDescription>
			</DialogHeader>

			<div class="grid gap-4 py-4 sm:grid-cols-2">
				<div class="space-y-1">
					<Label for="dev-name">Nama (slug)</Label>
					<Input id="dev-name" bind:value={name} disabled={editing} placeholder="pompa" />
					{#if fieldErrors.name}<p class="text-xs text-destructive">{fieldErrors.name}</p>{/if}
				</div>
				<div class="space-y-1">
					<Label for="dev-label">Label</Label>
					<Input id="dev-label" bind:value={label} placeholder="Pompa Air" />
				</div>

				{#if !editing}
					<div class="space-y-1">
						<Label for="dev-tuya">Tuya ID</Label>
						<Input id="dev-tuya" bind:value={tuyaId} />
						{#if fieldErrors.tuya_id}<p class="text-xs text-destructive">{fieldErrors.tuya_id}</p>{/if}
					</div>
				{/if}

				<div class="space-y-1">
					<Label for="dev-key">Local key {editing ? '(opsional)' : ''}</Label>
					<Input
						id="dev-key"
						type="password"
						bind:value={localKey}
						placeholder={editing ? 'biarkan kosong untuk mempertahankan' : ''}
					/>
					{#if fieldErrors.local_key}<p class="text-xs text-destructive">{fieldErrors.local_key}</p>{/if}
				</div>

				<div class="space-y-1">
					<Label for="dev-ip">IP</Label>
					<Input id="dev-ip" bind:value={ip} placeholder="192.168.1.50" />
				</div>
				<div class="space-y-1">
					<Label for="dev-ver">Versi protokol</Label>
					<Input id="dev-ver" bind:value={version} placeholder="3.5" />
					{#if fieldErrors.version}<p class="text-xs text-destructive">{fieldErrors.version}</p>{/if}
				</div>

				<div class="space-y-1 sm:col-span-2">
					<Label for="dev-type">Tipe</Label>
					<Select
						type="single"
						value={type}
						onValueChange={(next) => {
							if (!next) return;
							type = next;
							dps = { ...(templates?.templates[next as 'plug'] ?? {}) };
						}}
					>
						<SelectTrigger id="dev-type" class="w-full">
							<SelectValue placeholder="Pilih tipe" />
						</SelectTrigger>
						<SelectContent>
							{#each templates?.types ?? ['plug', 'bulb', 'switch', 'sensor'] as option (option)}
								<SelectItem value={option} label={option}>{option}</SelectItem>
							{/each}
						</SelectContent>
					</Select>
				</div>

				<div class="sm:col-span-2">
					<DpsEditor bind:dps {templates} {type} />
					{#if fieldErrors.dps}<p class="text-xs text-destructive">{fieldErrors.dps}</p>{/if}
				</div>

				<div class="space-y-2 sm:col-span-2">
					<p class="text-sm font-medium">Fitur</p>
					<div class="flex flex-wrap gap-4">
						{#each templates?.features ?? ['power_logging', 'watchdog'] as feature (feature)}
							<label class="flex items-center gap-2 text-sm">
								<Checkbox
									checked={Boolean(features[feature])}
									onCheckedChange={() => toggleFeature(feature)}
								/>
								{feature === 'power_logging' ? 'Catat daya' : 'Watchdog auto-off'}
							</label>
						{/each}
					</div>
				</div>

				<div class="space-y-2 sm:col-span-2">
					<p class="text-sm font-medium">Role yang boleh mengakses</p>
					<p class="text-xs text-muted-foreground">
						Kosong berarti semua role dengan izin melihat perangkat.
					</p>
					<div class="flex flex-wrap gap-4">
						{#each roles as role (role.id)}
							<label class="flex items-center gap-2 text-sm">
								<Checkbox
									checked={accessRoles.includes(role.id)}
									onCheckedChange={() => toggleRole(role.id)}
								/>
								{role.name}
							</label>
						{/each}
					</div>
					{#if fieldErrors.access_roles}
						<p class="text-xs text-destructive">{fieldErrors.access_roles}</p>
					{/if}
				</div>

				{#if formError}
					<p class="text-sm text-destructive sm:col-span-2" role="alert">{formError}</p>
				{/if}
			</div>

			<DialogFooter>
				<Button type="button" variant="outline" onclick={() => (open = false)}>Batal</Button>
				<Button type="submit" disabled={saving}>{saving ? 'Menyimpan…' : 'Simpan'}</Button>
			</DialogFooter>
		</form>
	</DialogContent>
</Dialog>
