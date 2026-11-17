<script lang="ts">
	import { Button } from '#lib/components/ui/button';
	import {
		Dialog,
		DialogContent,
		DialogDescription,
		DialogFooter,
		DialogHeader,
		DialogTitle
	} from '#lib/components/ui/dialog';

	let {
		open = $bindable(false),
		deviceLabel = '',
		onConfirm
	}: {
		open?: boolean;
		deviceLabel?: string;
		onConfirm: () => void;
	} = $props();
</script>

<Dialog bind:open>
	<DialogContent class="sm:max-w-sm">
		<DialogHeader>
			<DialogTitle>Konfirmasi kontrol</DialogTitle>
			<DialogDescription>
				{deviceLabel} memiliki watchdog: perangkat ini bisa dimatikan otomatis oleh sistem.
				Lanjutkan?
			</DialogDescription>
		</DialogHeader>
		<DialogFooter>
			<Button variant="outline" onclick={() => (open = false)}>Batal</Button>
			<Button onclick={() => { open = false; onConfirm(); }}>Lanjutkan</Button>
		</DialogFooter>
	</DialogContent>
</Dialog>
