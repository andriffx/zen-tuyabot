<script lang="ts">
	import { goto } from '$app/navigation';
	import { Button } from '#lib/components/ui/button';
	import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '#lib/components/ui/card';
	import { Input } from '#lib/components/ui/input';
	import { Label } from '#lib/components/ui/label';
	import { toast } from 'svelte-sonner';
	import { ApiError } from '#lib/api/errors';
	import { auth } from '#lib/stores/auth.svelte';

	let step = $state<1 | 2>(1);
	let username = $state('');
	let password = $state('');
	let confirm = $state('');
	let pending = $state(false);
	let fieldErrors = $state<Record<string, string>>({});
	let formError = $state<string | null>(null);

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		fieldErrors = {};

		if (password !== confirm) {
			fieldErrors.confirm = 'Konfirmasi password tidak sama';
			return;
		}

		pending = true;
		formError = null;
		try {
			await auth.setup(username, password);
			toast.success('Akun Superadmin dibuat');
			step = 2;
		} catch (error) {
			if (error instanceof ApiError) {
				formError = error.detail;
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
	<Card class="w-full max-w-md">
		<CardHeader>
			<CardTitle>{step === 1 ? 'Setup awal' : 'Setup selesai'}</CardTitle>
			<CardDescription>
				{step === 1
					? 'Buat akun Superadmin pertama. Langkah ini hanya bisa dilakukan sekali.'
					: 'Akun Superadmin aktif. Tambahkan bot Telegram dan perangkat dari dashboard.'}
			</CardDescription>
		</CardHeader>
		<CardContent>
			{#if step === 1}
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
							autocomplete="new-password"
							required
						/>
						<p class="text-xs text-muted-foreground">Minimal 8 karakter.</p>
						{#if fieldErrors.password}
							<p class="text-sm text-destructive">{fieldErrors.password}</p>
						{/if}
					</div>
					<div class="space-y-2">
						<Label for="confirm">Ulangi password</Label>
						<Input id="confirm" type="password" bind:value={confirm} autocomplete="new-password" required />
						{#if fieldErrors.confirm}
							<p class="text-sm text-destructive">{fieldErrors.confirm}</p>
						{/if}
					</div>
					{#if formError}
						<p class="text-sm text-destructive" role="alert">{formError}</p>
					{/if}
					<Button type="submit" class="w-full" disabled={pending}>
						{pending ? 'Membuat akun…' : 'Buat akun Superadmin'}
					</Button>
				</form>
			{:else}
				<div class="flex flex-col gap-2">
					<Button onclick={() => goto('/bots')}>Tambah bot Telegram</Button>
					<Button variant="outline" onclick={() => goto('/devices')}>Tambah perangkat</Button>
					<Button variant="ghost" onclick={() => goto('/')}>Lewati, buka dashboard</Button>
				</div>
			{/if}
		</CardContent>
	</Card>
</div>
