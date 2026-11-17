<script lang="ts">
	import { format } from '#lib/format';

	let {
		points = [],
		max = 0,
		height = 140
	}: { points?: { at: string; watts: number }[]; max?: number; height?: number } = $props();

	const width = 720;
	const padding = 8;

	const path = $derived.by(() => {
		if (points.length < 2) return '';
		const peak = max || Math.max(...points.map((point) => point.watts), 1);
		const stepX = (width - padding * 2) / (points.length - 1);
		return points
			.map((point, index) => {
				const x = padding + index * stepX;
				const y = height - padding - (point.watts / peak) * (height - padding * 2);
				return `${index === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
			})
			.join(' ');
	});

	const area = $derived(
		path ? `${path} L${width - padding},${height - padding} L${padding},${height - padding} Z` : ''
	);

	const peakPoint = $derived(
		points.length
			? points.reduce((best, point) => (point.watts > best.watts ? point : best), points[0])
			: null
	);

	const first = $derived(points[0]?.at ?? '');
	const last = $derived(points.at(-1)?.at ?? '');
</script>

{#if points.length < 2}
	<div
		class="flex items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground"
		style="height: {height}px"
	>
		Belum ada data daya
	</div>
{:else}
	<figure class="space-y-1">
		<svg
			viewBox="0 0 {width} {height}"
			class="w-full text-primary"
			role="img"
			aria-label="Grafik konsumsi daya"
		>
			<title>Konsumsi daya, puncak {format.watts(max)}</title>
			<path d={area} class="fill-primary/15" />
			<path d={path} class="fill-none stroke-current" stroke-width="2" stroke-linejoin="round" />
			{#if peakPoint}
				<circle cx={padding} cy={padding} r="0" />
			{/if}
		</svg>
		<figcaption class="flex flex-wrap justify-between gap-2 text-xs text-muted-foreground">
			<span>{format.dateTime(first)}</span>
			<span>Puncak {format.watts(max)}</span>
			<span>{format.dateTime(last)}</span>
		</figcaption>
	</figure>
{/if}
