<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import MaintenanceScreen from '#lib/components/maintenance-screen.svelte';
	import OfflineScreen from '#lib/components/offline-screen.svelte';
	import { outcomeToLocation, type HydrateOutcome } from '#lib/guard';
	import { onUnauthorized } from '#lib/api';
	import { auth } from '#lib/stores/auth.svelte';

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
		// One listener for the whole app: the API client reports any protected
		// 401 here, and we reset once so parallel failures cannot loop.
		onUnauthorized(() => {
			if (redirecting) return;
			auth.reset();
			outcome = 'login';
			void goto('/login', { replaceState: true });
		});

		void boot();
		return () => onUnauthorized(null);
	});

	// Re-check on navigation so a session that died on another tab is caught.
	$effect(() => {
		void page.url.pathname;
		if (outcome === 'ready' && !auth.me) {
			void boot();
		}
	});
</script>

{#if outcome === null}
	<div class="flex min-h-svh items-center justify-center">
		<p class="text-sm text-muted-foreground">Memuat…</p>
	</div>
{:else if outcomeToLocation(outcome, page.url.pathname).render === 'offline'}
	<OfflineScreen />
{:else if outcomeToLocation(outcome, page.url.pathname).render === 'maintenance'}
	<MaintenanceScreen />
{:else}
	{@render children()}
{/if}
