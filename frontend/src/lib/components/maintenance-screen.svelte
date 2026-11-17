<script lang="ts">
	import { Button } from '#lib/components/ui/button';
	import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#lib/components/ui/card';
	import { auth } from '#lib/stores/auth.svelte';

	let checking = $state(false);

	async function check() {
		checking = true;
		try {
			const outcome = await auth.hydrate();
			if (outcome === 'ready') window.location.reload();
		} finally {
			checking = false;
		}
	}
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
