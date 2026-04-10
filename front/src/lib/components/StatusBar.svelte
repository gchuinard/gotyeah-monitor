<script lang="ts">
	import type { CheckEntry } from '$lib/stores/monitors';

	export let history: CheckEntry[] = [];

	let windowHours = 2;
	const MIN_HOURS = 1;
	const MAX_HOURS = 12;

	function toUtcDate(s: string): Date {
		return new Date(s.endsWith('Z') || s.includes('+') ? s : s + 'Z');
	}

	$: displayed = (() => {
		const cutoff = Date.now() - windowHours * 60 * 60 * 1000;
		return history.filter((c) => toUtcDate(c.checked_at).getTime() >= cutoff);
	})();

	$: uptimePct =
		displayed.length === 0
			? null
			: Math.round((displayed.filter((c) => c.status === 'up').length / displayed.length) * 100);

	// ── Tooltip custom ────────────────────────────────────────────────────
	let tooltip: { label: string; lat: string; status: 'up' | 'down'; x: number; y: number } | null = null;
	let containerEl: HTMLDivElement;

	function onEnter(e: MouseEvent, c: CheckEntry) {
		const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
		const containerRect = containerEl.getBoundingClientRect();
		const d = toUtcDate(c.checked_at);
		const label = d.toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
		const lat = c.latency_ms !== null ? `${c.latency_ms} ms` : 'N/A';
		const x = rect.left - containerRect.left + rect.width / 2;
		const y = rect.top - containerRect.top;
		tooltip = { label, lat, status: c.status, x, y };
	}

	function onLeave() {
		tooltip = null;
	}
</script>

<div class="flex flex-col gap-1.5" bind:this={containerEl} style="position: relative;">
	<div class="flex items-center justify-between text-[11px] text-slate-400">
		<div class="flex items-center gap-1.5">
			<button
				on:click|stopPropagation={() => (windowHours = Math.max(MIN_HOURS, windowHours - 1))}
				disabled={windowHours <= MIN_HOURS}
				class="w-4 h-4 rounded flex items-center justify-center bg-slate-700/60 hover:bg-slate-600/80 disabled:opacity-30 disabled:cursor-not-allowed transition-colors leading-none"
			>−</button>
			<span class="tabular-nums">{windowHours}h</span>
			<button
				on:click|stopPropagation={() => (windowHours = Math.min(MAX_HOURS, windowHours + 1))}
				disabled={windowHours >= MAX_HOURS}
				class="w-4 h-4 rounded flex items-center justify-center bg-slate-700/60 hover:bg-slate-600/80 disabled:opacity-30 disabled:cursor-not-allowed transition-colors leading-none"
			>+</button>
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
		{#if displayed.length === 0}
			{#each Array(12) as _}
				<div class="flex-1 rounded-sm bg-slate-700/50"></div>
			{/each}
		{:else}
			{#each displayed as c (c.id)}
				{#if c.status === 'up'}
					<div
						class="flex-1 rounded-sm bg-emerald-400 hover:opacity-80 transition-opacity cursor-default"
						on:mouseenter={(e) => onEnter(e, c)}
						on:mouseleave={onLeave}
					></div>
				{:else}
					<div
						class="flex-1 rounded-sm bg-red-400 hover:opacity-80 transition-opacity cursor-default"
						on:mouseenter={(e) => onEnter(e, c)}
						on:mouseleave={onLeave}
					></div>
				{/if}
			{/each}
		{/if}
	</div>

	<div class="flex justify-between text-[10px] text-slate-500">
		<span>{displayed.length > 0 ? toUtcDate(displayed[0].checked_at).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''}</span>
		<span>{displayed.length > 0 ? toUtcDate(displayed[displayed.length - 1].checked_at).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''}</span>
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
				{#if tooltip.status === 'up'}
					<span class="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0"></span>
					<span class="text-emerald-400 font-medium font-mono">{tooltip.lat}</span>
				{:else}
					<span class="w-1.5 h-1.5 rounded-full bg-red-400 shrink-0"></span>
					<span class="text-red-400 font-medium font-mono">Offline</span>
				{/if}
			</div>
		</div>
	{/if}
</div>
