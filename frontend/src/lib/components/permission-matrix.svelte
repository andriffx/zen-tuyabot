<script lang="ts">
	import { Checkbox } from '#lib/components/ui/checkbox';
	import { Badge } from '#lib/components/ui/badge';
	import { Lock } from '@lucide/svelte';
	import { permissions, type GroupedPermissions } from '#lib/permissions';

	let {
		groups = [],
		selected = [],
		editable = [],
		onChange,
		lockedKeys = []
	}: {
		groups?: GroupedPermissions[];
		selected?: string[];
		editable?: string[];
		onChange: (selected: string[]) => void;
		/** Keys the editor may not remove (protected role). */
		lockedKeys?: string[];
	} = $props();

	const editableSet = $derived(new Set(editable));
	const lockedSet = $derived(new Set(lockedKeys));

	function toggle(key: string, checked: boolean) {
		if (!editableSet.has(key) || lockedSet.has(key)) return;
		onChange(checked ? [...new Set([...selected, key])] : selected.filter((entry) => entry !== key));
	}

	function toggleGroup(group: GroupedPermissions, checked: boolean) {
		const grantable = group.permissions
			.map((permission) => permission.key)
			.filter((key) => editableSet.has(key) && !lockedSet.has(key));
		const next = checked
			? [...new Set([...selected, ...grantable])]
			: selected.filter((key) => !grantable.includes(key));
		onChange(next);
	}

	function groupState(group: GroupedPermissions): boolean | 'indeterminate' {
		const grantable = group.permissions
			.map((permission) => permission.key)
			.filter((key) => editableSet.has(key) && !lockedSet.has(key));
		if (grantable.length === 0) return false;
		const held = grantable.filter((key) => selected.includes(key)).length;
		if (held === 0) return false;
		return held === grantable.length ? true : 'indeterminate';
	}
</script>

<div class="space-y-4">
	{#each groups as group (group.name)}
		<div class="rounded-md border p-3">
			<label class="flex items-center gap-2 border-b pb-2 text-sm font-medium">
				<Checkbox
					checked={groupState(group) === true}
					indeterminate={groupState(group) === 'indeterminate'}
					onCheckedChange={(checked) => toggleGroup(group, checked === true)}
				/>
				{group.name}
				<span class="ml-auto text-xs font-normal text-muted-foreground">
					{group.permissions.filter((entry) => selected.includes(entry.key)).length}/
					{group.permissions.length}
				</span>
			</label>

			<div class="mt-2 grid gap-2 sm:grid-cols-2">
				{#each group.permissions as permission (permission.key)}
					{@const locked = lockedSet.has(permission.key)}
					{@const grantable = editableSet.has(permission.key)}
					<label
						class="flex items-start gap-2 text-sm {locked || !grantable
							? 'opacity-60'
							: 'cursor-pointer'}"
						title={locked
							? 'Izin inti role terlindungi'
							: grantable
								? permission.key
								: 'Anda tidak memiliki izin ini'}
					>
						<Checkbox
							checked={selected.includes(permission.key)}
							disabled={!grantable || locked}
							onCheckedChange={(checked) => toggle(permission.key, checked === true)}
						/>
						<span class="flex flex-col">
							<span class="flex items-center gap-1">
								{permission.label}
								{#if locked}
									<Lock class="size-3 text-muted-foreground" />
								{/if}
							</span>
							<span class="font-mono text-[10px] text-muted-foreground">{permission.key}</span>
						</span>
					</label>
				{/each}
			</div>
		</div>
	{/each}

	{#if groups.length === 0}
		<p class="text-sm text-muted-foreground">Katalog permission tidak tersedia.</p>
	{/if}

	{#if editable.length < groups.flatMap((group) => group.permissions).length}
		<Badge variant="outline" class="text-xs">
			Hanya izin yang Anda miliki yang bisa diberikan
		</Badge>
	{/if}
</div>
