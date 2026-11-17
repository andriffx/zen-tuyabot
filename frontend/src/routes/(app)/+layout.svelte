<script lang="ts">
	import { page } from '$app/state';
	import {
		Sidebar,
		SidebarContent,
		SidebarGroup,
		SidebarGroupContent,
		SidebarGroupLabel,
		SidebarHeader,
		SidebarMenu,
		SidebarMenuButton,
		SidebarMenuItem,
		SidebarProvider,
		SidebarTrigger
	} from '#lib/components/ui/sidebar';
	import ThemeToggle from '#lib/components/theme-toggle.svelte';
	import ConnectionBadge from '#lib/components/connection-badge.svelte';
	import UserMenu from '#lib/components/user-menu.svelte';
	import { nav } from '#lib/nav';
	import { auth } from '#lib/stores/auth.svelte';
	import { connectivity } from '#lib/stores/connectivity.svelte';
	import { stream } from '#lib/stores/stream.svelte';
	import {
		Activity,
		AlertTriangle,
		Archive,
		Bot,
		Gauge,
		List,
		Plug,
		Send,
		Shield,
		Sliders,
		Users,
		Zap
	} from '@lucide/svelte';
	import { onMount } from 'svelte';

	let { children } = $props();

	const icons = { gauge: Gauge, plug: Plug, zap: Zap, list: List, alert: AlertTriangle,
		sliders: Sliders, users: Users, send: Send, shield: Shield, bot: Bot,
		archive: Archive, activity: Activity } as const;

	const visible = $derived(nav.visibleItems((permission) => auth.can(permission)));
	const pathname = $derived(page.url.pathname);

	function isActive(href: string): boolean {
		if (href === '/') return pathname === '/';
		return pathname === href || pathname.startsWith(`${href}/`);
	}

	onMount(() => {
		const detach = connectivity.attach();
		stream.start();
		void auth.refresh();
		return () => {
			stream.stop();
			detach();
		};
	});
</script>

<SidebarProvider>
	<Sidebar>
		<SidebarHeader>
			<div class="flex items-center gap-2 px-2 py-1">
				<span class="text-sm font-semibold">Zen Tuyabot</span>
			</div>
		</SidebarHeader>
		<SidebarContent>
			<SidebarGroup>
				<SidebarGroupLabel>Menu</SidebarGroupLabel>
				<SidebarGroupContent>
					<SidebarMenu>
						{#each visible as item (item.href)}
							{@const Icon = icons[item.icon as keyof typeof icons] ?? Gauge}
							<SidebarMenuItem>
								<SidebarMenuButton isActive={isActive(item.href)}>
									{#snippet child({ props })}
										<a {...props} href={item.href} data-sveltekit-preload-data="hover">
											<Icon class="size-4" />
											<span>{item.label}</span>
										</a>
									{/snippet}
								</SidebarMenuButton>
							</SidebarMenuItem>
						{/each}
					</SidebarMenu>
				</SidebarGroupContent>
			</SidebarGroup>
		</SidebarContent>
	</Sidebar>

	<main class="flex min-h-svh flex-1 flex-col">
		<header class="sticky top-0 z-10 flex h-14 items-center gap-3 border-b bg-background/95 px-4 backdrop-blur">
			<SidebarTrigger />
			<div class="ml-auto flex items-center gap-2">
				<ConnectionBadge />
				<ThemeToggle />
				<UserMenu />
			</div>
		</header>
		<div class="flex-1 p-4 md:p-6">
			{@render children()}
		</div>
	</main>
</SidebarProvider>
