<script lang="ts">
	import { Button } from '#lib/components/ui/button';
	import { Card, CardContent, CardHeader, CardTitle } from '#lib/components/ui/card';
	import { Input } from '#lib/components/ui/input';
	import { Skeleton } from '#lib/components/ui/skeleton';
	import { Textarea } from '#lib/components/ui/textarea';
	import { botMessagesApi, categoryLabel, groupByCategory, type BotMessage } from '#lib/api/bot-messages';
	import { ApiError } from '#lib/api/errors';
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { Eye, RotateCcw, Save } from '@lucide/svelte';

	let messages = $state<BotMessage[]>([]);
	let drafts = $state<Record<string, string>>({});
	let previews = $state<Record<string, string>>({});
	let loading = $state(true);
	let error = $state<string | null>(null);
	let savingKey = $state<string | null>(null);

	const grouped = $derived(groupByCategory(messages));

	async function load() {
		loading = true;
		error = null;
		try {
			messages = (await botMessagesApi.list()).messages;
			drafts = Object.fromEntries(messages.map((message) => [message.key, message.text]));
		} catch (failure) {
			error = failure instanceof ApiError ? failure.detail : 'Gagal memuat pesan bot.';
		} finally {
			loading = false;
		}
	}

	function isDirty(message: BotMessage): boolean {
		return drafts[message.key] !== message.text;
	}

	async function save(message: BotMessage) {
		savingKey = message.key;
		try {
			await botMessagesApi.update(message.key, drafts[message.key] ?? '');
			toast.success('Teks disimpan');
			await load();
		} catch (failure) {
			toast.error(failure instanceof ApiError ? failure.detail : 'Gagal menyimpan');
		} finally {
			savingKey = null;
		}
	}

	async function preview(message: BotMessage) {
		try {
			previews[message.key] = (await botMessagesApi.preview(message.key)).text;
		} catch (failure) {
			toast.error(failure instanceof ApiError ? failure.detail : 'Gagal pratinjau');
		}
	}

	function insertPlaceholder(message: BotMessage, placeholder: string) {
		drafts[message.key] = `${drafts[message.key] ?? ''}{${placeholder}}`;
	}

	function resetDraft(message: BotMessage) {
		drafts[message.key] = message.text;
		delete previews[message.key];
	}

	onMount(load);
</script>

<div class="space-y-4">
	<div class="flex flex-wrap items-center justify-between gap-2">
		<div>
			<h1 class="text-xl font-semibold">Pesan Bot</h1>
			<p class="text-sm text-muted-foreground">
				Teks yang diterima pengguna di chat Telegram. Perubahan langsung dipakai bot.
			</p>
		</div>
		<Button variant="outline" onclick={load} disabled={loading}>Muat ulang</Button>
	</div>

	{#if error}
		<div class="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm">{error}</div>
	{:else if loading}
		<Skeleton class="h-48 w-full rounded-xl" />
	{:else}
		{#each Object.entries(grouped) as [group, groupMessages] (group)}
			<Card>
				<CardHeader><CardTitle class="text-base">{categoryLabel(group)}</CardTitle></CardHeader>
				<CardContent class="space-y-4">
					{#each groupMessages as message (message.key)}
						<div class="space-y-2 border-b pb-4 last:border-0 last:pb-0">
							<div class="flex flex-wrap items-center justify-between gap-2">
								<code class="text-xs text-muted-foreground">{message.key}</code>
								<div class="flex gap-1">
									<Button size="sm" variant="ghost" onclick={() => preview(message)}>
										<Eye class="size-4" /> Pratinjau
									</Button>
									{#if isDirty(message)}
										<Button size="sm" variant="ghost" onclick={() => resetDraft(message)}>
											<RotateCcw class="size-4" /> Batalkan
										</Button>
									{/if}
									<Button
										size="sm"
										onclick={() => save(message)}
										disabled={!isDirty(message) || savingKey === message.key}
									>
										<Save class="size-4" /> Simpan
									</Button>
								</div>
							</div>

							<Textarea
								rows={3}
								class="font-mono text-xs"
								value={drafts[message.key] ?? ''}
								oninput={(event) => {
									drafts[message.key] = (event.currentTarget as HTMLTextAreaElement).value;
								}}
							/>

							{#if message.placeholders.length}
								<div class="flex flex-wrap items-center gap-1 text-xs">
									<span class="text-muted-foreground">Sisipkan:</span>
									{#each message.placeholders as placeholder (placeholder)}
										<Button
											size="sm"
											variant="outline"
											class="h-6 px-2 font-mono text-xs"
											onclick={() => insertPlaceholder(message, placeholder)}
										>
											{placeholder}
										</Button>
									{/each}
								</div>
							{/if}

							{#if previews[message.key]}
								<pre class="whitespace-pre-wrap rounded-md bg-muted p-2 text-xs">{previews[message.key]}</pre>
							{/if}
						</div>
					{/each}
				</CardContent>
			</Card>
		{/each}
	{/if}
</div>
