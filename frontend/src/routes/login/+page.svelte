<script lang="ts">
	import { asset } from '$app/paths';
	import { goto } from '$app/navigation';
	import { Button } from '#lib/components/ui/button';
	import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#lib/components/ui/card';
	import { Input } from '#lib/components/ui/input';
	import { Label } from '#lib/components/ui/label';
	import { toast } from 'svelte-sonner';
	import { ApiError } from '#lib/api/errors';
	import { auth } from '#lib/stores/auth.svelte';

	let username = $state('');
	let password = $state('');
	let pending = $state(false);
	let fieldErrors = $state<Record<string, string>>({});
	let formError = $state<string | null>(null);
	let retryAfter = $state<number | null>(null);

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		pending = true;
		fieldErrors = {};
		formError = null;
		retryAfter = null;

		try {
			await auth.login(username, password);
			toast.success('Berhasil masuk');
			await goto('/', { replaceState: true });
		} catch (error) {
			if (error instanceof ApiError) {
				if (error.status === 429) {
					formError = 'Terlalu banyak percobaan masuk. Coba lagi nanti.';
					retryAfter = Number(error.detail.match(/\d+/)?.[0] ?? 0) || null;
				} else if (error.status === 401) {
					formError = 'Username atau password salah.';
				} else {
					formError = error.detail;
				}
				for (const field of error.fieldErrors) fieldErrors[field.key] = field.message;
			} else {
				formError = 'Terjadi kesalahan tak terduga.';
			}
		} finally {
			pending = false;
		}
	}
</script>

<div class="flex min-h-svh items-center justify-center p-6">
	<Card class="w-full max-w-sm">
		<CardHeader>
			<div class="mb-2 flex items-center gap-2">
				<img src={asset('favicon.svg')} alt="" class="size-8" />
				<span class="text-sm font-semibold tracking-tight">Zen Tuyabot</span>
			</div>
			<CardTitle>Masuk</CardTitle>
			<CardDescription>Dashboard Zen Tuyabot</CardDescription>
		</CardHeader>
		<CardContent>
			<form class="space-y-4" onsubmit={submit}>
				<div class="space-y-2">
					<Label for="username">Username</Label>
					<Input id="username" bind:value={username} autocomplete="username" required />
					{#if fieldErrors.username}
						<p class="text-sm text-destructive">{fieldErrors.username}</p>
					{/if}
				</div>
				<div class="space-y-2">
					<Label for="password">Password</Label>
					<Input
						id="password"
						type="password"
						bind:value={password}
						autocomplete="current-password"
						required
					/>
					{#if fieldErrors.password}
						<p class="text-sm text-destructive">{fieldErrors.password}</p>
					{/if}
				</div>
				{#if formError}
					<p class="text-sm text-destructive" role="alert">
						{formError}
						{#if retryAfter}
							<span class="text-muted-foreground">(coba lagi dalam {retryAfter} detik)</span>
						{/if}
					</p>
				{/if}
				<Button type="submit" class="w-full" disabled={pending}>
					{pending ? 'Memproses…' : 'Masuk'}
				</Button>
			</form>
		</CardContent>
	</Card>
</div>
