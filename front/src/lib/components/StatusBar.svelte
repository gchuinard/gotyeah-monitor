<script lang="ts">
	import type { CheckEntry } from '$lib/stores/monitors';
	import { HISTORY_WINDOW_PRESETS, monitorWindowStore } from '$lib/stores/historyWindow';

	export let history: CheckEntry[] = [];
	export let monitorId: number;

	const windowStore = monitorWindowStore(monitorId);

	function toUtcDate(s: string): Date {
		return new Date(s.endsWith('Z') || s.includes('+') ? s : s + 'Z');
	}

	$: preset =
		HISTORY_WINDOW_PRESETS.find((p) => p.value === $windowStore) ?? HISTORY_WINDOW_PRESETS[0];
	$: currentIdx = HISTORY_WINDOW_PRESETS.findIndex((p) => p.value === $windowStore);
	$: atMin = currentIdx <= 0;
	$: atMax = currentIdx >= HISTORY_WINDOW_PRESETS.length - 1;

	function stepDown() {
		if (currentIdx > 0) windowStore.set(HISTORY_WINDOW_PRESETS[currentIdx - 1].value);
	}
	function stepUp() {
		if (currentIdx >= 0 && currentIdx < HISTORY_WINDOW_PRESETS.length - 1)
			windowStore.set(HISTORY_WINDOW_PRESETS[currentIdx + 1].value);
	}

	type BucketColor = 'gray' | 'green' | 'yellow' | 'red';
	type Bucket = {
		start: number;
		end: number;
		checks: CheckEntry[];
		upCount: number;
		downCount: number;
		avgLatency: number | null;
		color: BucketColor;
	};

	$: buckets = (() => {
		const bucketMs = preset.bucketMinutes * 60 * 1000;
		const windowMs = $windowStore * 60 * 60 * 1000;
		const bucketCount = Math.max(1, Math.round(windowMs / bucketMs));
		const now = Date.now();
		const withT = history.map((c) => ({ c, t: toUtcDate(c.checked_at).getTime() }));
		const result: Bucket[] = [];
		for (let i = bucketCount - 1; i >= 0; i--) {
			const end = now - i * bucketMs;
			const start = end - bucketMs;
			const inBucket = withT.filter((x) => x.t >= start && x.t < end).map((x) => x.c);
			const upCount = inBucket.filter((c) => c.status === 'up').length;
			const downCount = inBucket.length - upCount;
			const lats = inBucket
				.map((c) => c.latency_ms)
				.filter((l): l is number => typeof l === 'number');
			const avgLatency =
				lats.length > 0 ? Math.round(lats.reduce((a, b) => a + b, 0) / lats.length) : null;
			let color: BucketColor;
			if (inBucket.length === 0) color = 'gray';
			else if (downCount === 0) color = 'green';
			else if (upCount === 0) color = 'red';
			else color = 'yellow';
			result.push({ start, end, checks: inBucket, upCount, downCount, avgLatency, color });
		}
		return result;
	})();

	$: allChecks = buckets.flatMap((b) => b.checks);
	$: uptimePct =
		allChecks.length === 0
			? null
			: Math.round((allChecks.filter((c) => c.status === 'up').length / allChecks.length) * 100);

	// ── Tooltip ───────────────────────────────────────────────────────────
	let tooltip: {
		label: string;
		detail: string;
		color: Exclude<BucketColor, 'gray'>;
		x: number;
		y: number;
	} | null = null;
	let containerEl: HTMLDivElement;

	function formatBucketLabel(b: Bucket): string {
		const start = new Date(b.start);
		const end = new Date(b.end);
		const span = preset.bucketMinutes;
		if (span <= 10) {
			return start.toLocaleString('fr-FR', {
				day: '2-digit',
				month: '2-digit',
				hour: '2-digit',
				minute: '2-digit'
			});
		}
		if (span < 1440) {
			const left = start.toLocaleString('fr-FR', {
				day: '2-digit',
				month: '2-digit',
				hour: '2-digit',
				minute: '2-digit'
			});
			const right = end.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
			return `${left} → ${right}`;
		}
		return start.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' });
	}

	function onEnter(e: MouseEvent, b: Bucket) {
		if (b.color === 'gray') return;
		const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
		const containerRect = containerEl.getBoundingClientRect();
		const label = formatBucketLabel(b);
		let detail: string;
		if (b.checks.length === 1) {
			detail = b.color === 'red' ? 'Offline' : b.avgLatency !== null ? `${b.avgLatency} ms` : 'N/A';
		} else if (b.color === 'green') {
			detail = `${b.checks.length} OK · ${b.avgLatency ?? '?'} ms`;
		} else if (b.color === 'yellow') {
			detail = `${b.downCount}/${b.checks.length} KO · ${b.avgLatency ?? '?'} ms`;
		} else {
			detail = `${b.checks.length} KO`;
		}
		const x = rect.left - containerRect.left + rect.width / 2;
		const y = rect.top - containerRect.top;
		tooltip = { label, detail, color: b.color, x, y };
	}

	function onLeave() {
		tooltip = null;
	}

	const BAR_CLASS: Record<BucketColor, string> = {
		gray: 'bg-slate-700/40',
		green: 'bg-emerald-400 hover:opacity-80 transition-opacity cursor-default',
		yellow: 'bg-yellow-400 hover:opacity-80 transition-opacity cursor-default',
		red: 'bg-red-400 hover:opacity-80 transition-opacity cursor-default'
	};

	$: firstCheck = allChecks[0];
	$: lastCheck = allChecks[allChecks.length - 1];
</script>

<div class="flex flex-col gap-1.5" bind:this={containerEl} style="position: relative;">
	<div class="flex items-center justify-between text-[11px] text-slate-400">
		<div class="flex items-center gap-1.5">
			<button
				on:click|stopPropagation={stepDown}
				disabled={atMin}
				class="w-4 h-4 rounded flex items-center justify-center bg-slate-700/60 hover:bg-slate-600/80 disabled:opacity-30 disabled:cursor-not-allowed transition-colors leading-none"
				aria-label="Réduire la fenêtre d'historique">−</button
			>
			<select
				bind:value={$windowStore}
				on:click|stopPropagation
				on:mousedown|stopPropagation
				aria-label="Fenêtre d'historique"
				class="tabular-nums text-[11px] text-slate-300 bg-slate-700/60 hover:bg-slate-600/80 rounded px-1 h-4 leading-none border-0 focus:outline-none focus:ring-1 focus:ring-cyan-400/60 cursor-pointer appearance-none text-center"
			>
				{#each HISTORY_WINDOW_PRESETS as p (p.value)}
					<option value={p.value} class="bg-slate-800 text-slate-200">{p.label}</option>
				{/each}
			</select>
			<button
				on:click|stopPropagation={stepUp}
				disabled={atMax}
				class="w-4 h-4 rounded flex items-center justify-center bg-slate-700/60 hover:bg-slate-600/80 disabled:opacity-30 disabled:cursor-not-allowed transition-colors leading-none"
				aria-label="Agrandir la fenêtre d'historique">+</button
			>
		</div>
		{#if uptimePct !== null}
			{#if uptimePct === 100}
				<span class="text-emerald-400">{uptimePct}% uptime</span>
			{:else if uptimePct >= 90}
				<span class="text-yellow-400">{uptimePct}% uptime</span>
			{:else}
				<span class="text-red-400">{uptimePct}% uptime</span>
			{/if}
		{/if}
	</div>

	<div class="flex gap-[2px] items-stretch h-7 w-full">
		{#each buckets as b, i (i)}
			<div
				class="flex-1 rounded-sm {BAR_CLASS[b.color]}"
				on:mouseenter={(e) => onEnter(e, b)}
				on:mouseleave={onLeave}
				role="presentation"
			></div>
		{/each}
	</div>

	<div class="flex justify-between text-[10px] text-slate-500">
		<span
			>{firstCheck
				? toUtcDate(firstCheck.checked_at).toLocaleString('fr-FR', {
						day: '2-digit',
						month: '2-digit',
						hour: '2-digit',
						minute: '2-digit'
					})
				: ''}</span
		>
		<span
			>{lastCheck
				? toUtcDate(lastCheck.checked_at).toLocaleString('fr-FR', {
						day: '2-digit',
						month: '2-digit',
						hour: '2-digit',
						minute: '2-digit'
					})
				: ''}</span
		>
	</div>

	<!-- Tooltip custom, instantané -->
	{#if tooltip}
		{@const left = Math.max(0, tooltip.x - 56)}
		<div
			class="absolute z-10 pointer-events-none px-2.5 py-1.5 rounded-lg
				   bg-slate-800 border border-slate-700 shadow-lg text-xs leading-tight
				   -translate-y-full"
			style="top: {tooltip.y - 6}px; left: {left}px; min-width: 112px;"
		>
			<div class="text-slate-400 font-mono">{tooltip.label}</div>
			<div class="flex items-center gap-1.5 mt-0.5">
				{#if tooltip.color === 'green'}
					<span class="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0"></span>
					<span class="text-emerald-400 font-medium font-mono">{tooltip.detail}</span>
				{:else if tooltip.color === 'yellow'}
					<span class="w-1.5 h-1.5 rounded-full bg-yellow-400 shrink-0"></span>
					<span class="text-yellow-400 font-medium font-mono">{tooltip.detail}</span>
				{:else}
					<span class="w-1.5 h-1.5 rounded-full bg-red-400 shrink-0"></span>
					<span class="text-red-400 font-medium font-mono">{tooltip.detail}</span>
				{/if}
			</div>
		</div>
	{/if}
</div>
