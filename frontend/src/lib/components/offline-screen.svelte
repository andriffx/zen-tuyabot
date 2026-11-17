<script lang="ts">
	import { Button } from '#lib/components/ui/button';
	import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#lib/components/ui/card';
	import { auth } from '#lib/stores/auth.svelte';

	let retrying = $state(false);

	async function retry() {
		retrying = true;
		try {
			const outcome = await auth.hydrate();
			if (outcome === 'ready' || outcome === 'login') {
				window.location.reload();
			}
		} finally {
			retrying = false;
		}
	}
</script>

<div class="flex min-h-svh items-center justify-center p-6">
	<Card class="w-full max-w-md">
		<CardHeader>
			<CardTitle>Backend tidak dapat dihubungi</CardTitle>
			<CardDescription>
				Dashboard ini membutuhkan backend Zen Tuyabot. Pastikan prosesnya berjalan dan dapat
				diakses, lalu coba lagi.
			</CardDescription>
		</CardHeader>
		<CardContent class="space-y-4">
			<dl class="space-y-1 text-sm">
				<div class="flex justify-between gap-4">
					<dt class="text-muted-foreground">Endpoint</dt>
					<dd class="font-mono text-xs">{window.location.origin}/api/health</dd>
				</div>
				{#if auth.error}
					<div class="flex justify-between gap-4">
						<dt class="text-muted-foreground">Pesan</dt>
						<dd class="text-right">{auth.error}</dd>
					</div>
				{/if}
			</dl>
			<Button onclick={retry} disabled={retrying}>
				{retrying ? 'Mencoba…' : 'Coba lagi'}
			</Button>
		</CardContent>
	</Card>
</div>
