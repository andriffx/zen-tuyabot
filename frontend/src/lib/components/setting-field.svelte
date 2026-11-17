<script lang="ts">
	import { Badge } from '#lib/components/ui/badge';
	import { Input } from '#lib/components/ui/input';
	import { Label } from '#lib/components/ui/label';
	import { Switch } from '#lib/components/ui/switch';
	import { Textarea } from '#lib/components/ui/textarea';
	import type { SettingField } from '#lib/settings-form';

	let {
		field,
		onChange
	}: { field: SettingField; onChange: (key: string, value: unknown) => void } = $props();

	const hasSecret = $derived(
		field.secret && typeof field.value === 'object' && field.value !== null
	);
	const disabled = $derived(field.read_only);

	// `field` is a mutable object inside the form model, so Svelte cannot see a
	// changed `.value`. Mirror it into local reactive state, kept in sync when the
	// parent replaces the field (reload, reset, error mapping).
	let localValue = $state<unknown>(undefined);
	$effect(() => {
		localValue = field.value;
	});

	let jsonText = $state('');
	let jsonError = $state<string | null>(null);

	$effect(() => {
		if (field.type === 'json') jsonText = JSON.stringify(field.value ?? {}, null, 2);
	});

	function commitJson(text: string) {
		jsonText = text;
		try {
			jsonError = null;
			onChange(field.key, JSON.parse(text));
		} catch {
			jsonError = 'JSON tidak valid';
		}
	}
</script>

<div class="space-y-1.5">
	<div class="flex flex-wrap items-center gap-2">
		<Label for="setting-{field.key}" class="text-sm">{field.label}</Label>
		{#if field.apply === 'telegram_restart'}
			<Badge variant="outline" class="text-[10px]">restart bot</Badge>
		{:else}
			<Badge variant="secondary" class="text-[10px]">langsung</Badge>
		{/if}
		{#if field.read_only}
			<Badge variant="outline" class="text-[10px]">khusus sistem</Badge>
		{/if}
	</div>

	{#if field.secret}
		<Input
			id="setting-{field.key}"
			type="password"
			placeholder={hasSecret ? 'sudah diisi — kosongkan untuk mempertahankan' : 'belum diisi'}
			value={typeof localValue === 'string' ? localValue : ''}
			oninput={(event) => {
				const next = (event.currentTarget as HTMLInputElement).value;
				localValue = next;
				onChange(field.key, next);
			}}
			{disabled}
		/>
	{:else if field.type === 'bool'}
		<div class="flex items-center gap-2">
			<Switch
				id="setting-{field.key}"
				checked={Boolean(localValue)}
				onCheckedChange={(checked) => {
					localValue = checked;
					onChange(field.key, checked);
				}}
				{disabled}
			/>
			<span class="text-xs text-muted-foreground">{localValue ? 'aktif' : 'nonaktif'}</span>
		</div>
	{:else if field.type === 'int' || field.type === 'float'}
		<Input
			id="setting-{field.key}"
			type="number"
			step={field.type === 'int' ? '1' : '0.1'}
			min={field.minimum ?? undefined}
			max={field.maximum ?? undefined}
			value={typeof localValue === 'number' ? localValue : Number(localValue ?? 0)}
			oninput={(event) => {
				const raw = (event.currentTarget as HTMLInputElement).value;
				const next = raw === '' ? Number.NaN : Number(raw);
				localValue = next;
				onChange(field.key, next);
			}}
			{disabled}
		/>
	{:else if field.type === 'enum'}
		<select
			id="setting-{field.key}"
			class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs"
			value={String(field.value ?? '')}
			onchange={(event) =>
				onChange(field.key, (event.currentTarget as HTMLSelectElement).value)}
			{disabled}
		>
			{#each field.choices as choice (choice)}
				<option value={choice}>{choice}</option>
			{/each}
		</select>
	{:else if field.type === 'json'}
		<Textarea
			id="setting-{field.key}"
			rows={4}
			value={jsonText}
			class="font-mono text-xs"
			oninput={(event) => commitJson((event.currentTarget as HTMLTextAreaElement).value)}
			{disabled}
		/>
		{#if jsonError}
			<p class="text-xs text-destructive">{jsonError}</p>
		{/if}
	{:else}
		<Input
			id="setting-{field.key}"
			value={String(localValue ?? '')}
			oninput={(event) => {
				const next = (event.currentTarget as HTMLInputElement).value;
				localValue = next;
				onChange(field.key, next);
			}}
			{disabled}
		/>
	{/if}

	{#if field.help}
		<p class="text-xs text-muted-foreground">{field.help}</p>
	{/if}
	{#if field.error}
		<p class="text-xs text-destructive">{field.error}</p>
	{/if}
</div>
