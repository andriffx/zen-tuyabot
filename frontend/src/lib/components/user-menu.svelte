<script lang="ts">
	import { goto } from '$app/navigation';
	import { Button } from '#lib/components/ui/button';
	import {
		DropdownMenu,
		DropdownMenuContent,
		DropdownMenuItem,
		DropdownMenuLabel,
		DropdownMenuSeparator,
		DropdownMenuTrigger
	} from '#lib/components/ui/dropdown-menu';
	import PasswordDialog from '#lib/components/password-dialog.svelte';
	import { auth } from '#lib/stores/auth.svelte';
	import { LogOut, UserRound } from '@lucide/svelte';
	import { toast } from 'svelte-sonner';

	let passwordOpen = $state(false);

	async function logout() {
		await auth.logout();
		toast.success('Berhasil keluar');
		await goto('/login', { replaceState: true });
	}
</script>

<DropdownMenu>
	<DropdownMenuTrigger>
		{#snippet child({ props })}
			<Button variant="ghost" size="icon" aria-label="Akun" {...props}>
				<UserRound class="size-4" />
			</Button>
		{/snippet}
	</DropdownMenuTrigger>
	<DropdownMenuContent align="end" class="w-48">
		<DropdownMenuLabel>
			<div class="text-sm font-medium">{auth.me?.username}</div>
			<div class="text-xs text-muted-foreground">{auth.me?.role?.name ?? '-'}</div>
		</DropdownMenuLabel>
		<DropdownMenuSeparator />
		<DropdownMenuItem onclick={() => (passwordOpen = true)}>Ubah password</DropdownMenuItem>
		<DropdownMenuSeparator />
		<DropdownMenuItem onclick={logout}>
			<LogOut class="size-4" />
			Keluar
		</DropdownMenuItem>
	</DropdownMenuContent>
</DropdownMenu>

<PasswordDialog bind:open={passwordOpen} />
