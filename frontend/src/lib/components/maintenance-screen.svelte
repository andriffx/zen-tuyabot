<script lang="ts">
	import { Button } from '#lib/components/ui/button';
	import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#lib/components/ui/card';
	import { onDestroy } from 'svelte';
	import { systemApi } from '#lib/api';
	import { auth } from '#lib/stores/auth.svelte';

	let checking = $state(false);

	async function check() {
		checking = true;
		try {
			// /api/maintenance/status is not blocked by the middleware, and it
			// answers with the flag we need even while maintenance is on. Using
			// hydrate() here would return 'maintenance' forever.
			const status = await systemApi.maintenanceStatus();
			if (!status.maintenance) {
				window.location.reload();
				return;
			}
			// Still on: refresh auth state so a session that ended is handled.
			await auth.hydrate();
		} catch {
			// Backend unreachable; the next tick tries again.
		} finally {
			checking = false;
		}
	}

	// Poll so the screen recovers on its own once maintenance is turned off in
	// another tab; the operator should not have to guess when to press retry.
	const timer = setInterval(() => void check(), 15_000);
	onDestroy(() => clearInterval(timer));
</script>

<div class="flex min-h-svh items-center justify-center p-6">
	<Card class="w-full max-w-md">
		<CardHeader>
			<CardTitle>Sistem dalam maintenance</CardTitle>
			<CardDescription>
				Dashboard sementara tidak melayani permintaan. Operator dapat mengakhiri maintenance dari
				halaman System setelah masuk.
			</CardDescription>
		</CardHeader>
		<CardContent class="flex gap-2">
			<Button onclick={check} disabled={checking}>
				{checking ? 'Memeriksa…' : 'Periksa lagi'}
			</Button>
		</CardContent>
	</Card>
</div>
