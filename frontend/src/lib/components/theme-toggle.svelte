<script lang="ts">
	import { mode, setMode } from 'mode-watcher';

type ThemeMode = 'light' | 'dark' | 'system';
	import { Button } from '#lib/components/ui/button';
	import {
		DropdownMenu,
		DropdownMenuContent,
		DropdownMenuItem,
		DropdownMenuTrigger
	} from '#lib/components/ui/dropdown-menu';
	import { Moon, Sun, Monitor } from '@lucide/svelte';

	const options: { value: ThemeMode; label: string; icon: typeof Sun }[] = [
		{ value: 'light', label: 'Terang', icon: Sun },
		{ value: 'dark', label: 'Gelap', icon: Moon },
		{ value: 'system', label: 'Sistem', icon: Monitor }
	];

	const current = $derived(options.find((option) => option.value === mode.current) ?? options[2]);
</script>

<DropdownMenu>
	<DropdownMenuTrigger>
		{#snippet child({ props })}
			<Button variant="ghost" size="icon" aria-label="Tema" {...props}>
				<current.icon class="size-4" />
			</Button>
		{/snippet}
	</DropdownMenuTrigger>
	<DropdownMenuContent align="end">
		{#each options as option (option.value)}
			<DropdownMenuItem onclick={() => setMode(option.value)}>
				<option.icon class="size-4" />
				{option.label}
				{#if option.value === current.value}
					<span class="ml-auto text-xs text-muted-foreground">aktif</span>
				{/if}
			</DropdownMenuItem>
		{/each}
	</DropdownMenuContent>
</DropdownMenu>
