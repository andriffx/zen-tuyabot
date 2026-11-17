<script lang="ts">
	import { TooltipProvider } from '#lib/components/ui/tooltip';
	import { ModeWatcher } from 'mode-watcher';
	import { Toaster } from '#lib/components/ui/sonner';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import MaintenanceScreen from '#lib/components/maintenance-screen.svelte';
	import OfflineScreen from '#lib/components/offline-screen.svelte';
	import { outcomeToLocation, type HydrateOutcome } from '#lib/guard';
	import { onUnauthorized } from '#lib/api';
	import { auth } from '#lib/stores/auth.svelte';
	import { connectivity } from '#lib/stores/connectivity.svelte';
	import '../app.css';

	let { children } = $props();

	let outcome = $state<HydrateOutcome | null>(null);
	let redirecting = false;

	async function boot() {
		const result = await auth.hydrate();
		outcome = result;

		const decision = outcomeToLocation(result, page.url.pathname);
		if (decision.redirect) {
			redirecting = true;
			await goto(decision.redirect, { replaceState: true });
			redirecting = false;
		}
	}

	onMount(() => {
		const detach = connectivity.attach();

		// One listener for the whole app: a protected 401 resets auth once.
		onUnauthorized(() => {
			if (redirecting) return;
			auth.reset();
			outcome = 'login';
			void goto('/login', { replaceState: true });
		});

		void boot();

		return () => {
			onUnauthorized(null);
			detach();
		};
	});

	// Re-hydrate after navigation when the session was dropped elsewhere.
	$effect(() => {
		void page.url.pathname;
		if (outcome === 'ready' && !auth.me) void boot();
	});

	const view = $derived(outcome ? outcomeToLocation(outcome, page.url.pathname) : {});
</script>

<ModeWatcher />
<TooltipProvider>
	<Toaster richColors position="top-right" />

	{#if outcome === null}
		<div class="flex min-h-svh items-center justify-center">
			<p class="text-sm text-muted-foreground">Memuat…</p>
		</div>
	{:else if view.render === 'offline'}
		<OfflineScreen />
	{:else if view.render === 'maintenance'}
		<MaintenanceScreen />
	{:else}
		{@render children()}
	{/if}
</TooltipProvider>
