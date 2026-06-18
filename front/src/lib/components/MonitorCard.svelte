<script lang="ts">
	import { onMount } from 'svelte';
	import StatusBar from '$lib/components/StatusBar.svelte';
	import type { CheckEntry } from '$lib/stores/monitors';

	export let id: number;
	export let groupId: number | null = null;
	export let groups: { id: number; name: string }[] = [];
	export let onAssignGroup: ((monitorId: number, groupId: number | null) => void) | undefined =
		undefined;
	export let name: string;
	export let url: string;
	export let status: 'up' | 'down' | 'checking';
	export let type: string = 'Service';
	export let latency: number | null = null;
	export let history: CheckEntry[] = [];
	export let lastCheckedAt: string | null = null;
	export let createdAt: string;
	export let expectedStatusCode: number;
	export let lastStatusCode: number | null;
	export let sslExpiryAt: string | null = null;
	export let uptime24h: number | null = null;
	export let uptime7d: number | null = null;
	export let uptime30d: number | null = null;
	export let uptime90d: number | null = null;
	export let onDeleted: (() => void) | undefined;
	export let onToggleDetails: () => void = () => {};
	export let showDetails = false;
	export let compact = false;
	// M1 : champs de config étendus (passés via {...m}, affichage optionnel)
	export let checkIntervalSeconds: number | null = null;
	export let keyword: string | null = null;
	export let keywordMode: 'present' | 'absent' | null = null;
	export let latencyThresholdMs: number | null = null;
	export let port: number | null = null;
	export let inMaintenance = false;

	let prevStatus: typeof status;
	let animationClass = '';
	let mounted = false;

	onMount(() => setTimeout(() => (mounted = true), 20));

	// Flash au changement de statut. Réactif sur `status` (l'assignation de prevStatus
	// dans la fonction appelée n'est pas tracée → pas de boucle), remplace beforeUpdate.
	$: flashOnStatusChange(status);
	function flashOnStatusChange(s: typeof status) {
		if (prevStatus !== undefined && s !== prevStatus) {
			animationClass = s === 'up' ? 'animate-flashGreen' : 'animate-flashRed';
			setTimeout(() => (animationClass = ''), 600);
		}
		prevStatus = s;
	}

	const statusColor = {
		up: 'text-emerald-400',
		down: 'text-red-400',
		checking: 'text-sky-300 animate-pulse'
	};

	const statusIcon = { up: '🟢', down: '🔴', checking: '⏳' };

	function toUtcDate(s: string): Date {
		return new Date(s.endsWith('Z') || s.includes('+') ? s : s + 'Z');
	}

	function formatRelative(dateStr: string | null): string {
		if (!dateStr) return 'Jamais vérifié';
		const d = toUtcDate(dateStr);
		if (Number.isNaN(d.getTime())) return 'Inconnu';
		const sec = Math.round((Date.now() - d.getTime()) / 1000);
		if (sec < 60) return `il y a ${sec}s`;
		const min = Math.round(sec / 60);
		if (min < 60) return `il y a ${min} min`;
		const h = Math.round(min / 60);
		if (h < 24) return `il y a ${h} h`;
		return `il y a ${Math.round(h / 24)} j`;
	}

	function latencyColor(lat: number | null) {
		if (lat === null) return 'text-gray-400';
		if (lat < 150) return 'text-emerald-400';
		if (lat < 400) return 'text-yellow-400';
		return 'text-red-500';
	}

	function uptimeColor(pct: number) {
		if (pct >= 99.5) return 'text-emerald-400';
		if (pct >= 95) return 'text-yellow-400';
		return 'text-red-400';
	}
</script>

<div
	role="button"
	tabindex="0"
	on:click={onToggleDetails}
	on:keydown={(e) => e.key === 'Enter' && onToggleDetails()}
	class={`relative rounded-3xl border cursor-pointer select-none
		bg-white/80 dark:bg-slate-950/80 backdrop-blur-xl shadow-soft
		hover:shadow-[0_16px_44px_-18px_rgba(56,189,248,0.32)] hover:-translate-y-0.5
		transition-all duration-300
		${mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-3'}
		${animationClass}
		p-4 flex flex-col gap-3
		${status === 'up' ? 'border-cyan-400/70' : status === 'down' ? 'border-rose-400/70' : 'border-sky-300/70'}`}
>
	{#if compact}
		<div class="flex items-center gap-4">
			<div class="flex flex-col items-center gap-0.5 shrink-0">
				<span class="text-lg">{statusIcon[status]}</span>
				<span class={`text-[10px] ${statusColor[status]}`}>
					{status === 'up' ? 'Online' : status === 'down' ? 'Offline' : '...'}
				</span>
			</div>
			<div class="flex flex-col gap-0.5 flex-1 min-w-0">
				<div class="flex items-center gap-2">
					<h2 class="font-semibold text-sm text-slate-900 dark:text-slate-50 truncate">{name}</h2>
					{#if inMaintenance}<span
							class="px-1.5 py-0.5 text-[10px] rounded-md bg-orange-500/20 text-orange-300 border border-orange-500/30 shrink-0"
							>🔧</span
						>{/if}
					<span
						class="px-1.5 py-0.5 text-[10px] rounded-md bg-gotyeah-600/20 text-gotyeah-200 border border-gotyeah-600/30 shrink-0"
						>{type}</span
					>
				</div>
				<div class="flex items-center gap-4 text-xs text-slate-400 flex-wrap">
					<span class={`font-medium tabular-nums ${latencyColor(latency)}`}
						>{latency !== null ? `${latency} ms` : 'N/A'}</span
					>
					<span class="truncate text-cyan-600">{url}</span>
					<span class="text-slate-500">{formatRelative(lastCheckedAt)}</span>
				</div>
			</div>
		</div>
	{:else}
		<div class="flex items-center justify-between">
			<div class="flex items-center gap-2">
				<span class="text-xl">{statusIcon[status]}</span>
				<h2 class="font-semibold text-lg text-slate-900 dark:text-slate-50">{name}</h2>
				{#if inMaintenance}<span
						class="px-2 py-0.5 text-[10px] rounded-md bg-orange-500/20 text-orange-300 border border-orange-500/30"
						>🔧 maintenance</span
					>{/if}
			</div>
			<span
				class="px-2 py-1 text-xs rounded-md bg-gotyeah-600/20 text-gotyeah-200 border border-gotyeah-600/30"
				>{type}</span
			>
		</div>

		<div class="flex items-center gap-3 text-sm">
			<span class={statusColor[status]}>
				{status === 'up' ? 'Online' : status === 'down' ? 'Offline' : 'Checking...'}
			</span>
			<span class="text-slate-500 text-xs">·</span>
			<span class={`font-medium tabular-nums ${latencyColor(latency)}`}>
				{latency !== null ? `${latency} ms` : 'N/A'}
			</span>
		</div>

		<div class="flex flex-col gap-1 text-xs text-slate-500 dark:text-slate-400">
			<a
				href={url}
				target="_blank"
				rel="noreferrer"
				class="inline-flex items-center gap-1 max-w-full min-w-0 self-start rounded-md
					border border-cyan-500/20 bg-cyan-500/10 px-2 py-0.5
					text-cyan-600 dark:text-cyan-400
					hover:bg-cyan-500/20 hover:border-cyan-500/40 hover:underline transition-colors"
				title={url}
				on:click|stopPropagation
			>
				<svg
					class="h-3 w-3 shrink-0"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					viewBox="0 0 24 24"
					aria-hidden="true"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"
					/>
				</svg>
				<span class="truncate">{url}</span>
			</a>
			<span>{formatRelative(lastCheckedAt)}</span>
		</div>
	{/if}

	{#if uptime24h !== null || uptime7d !== null || uptime30d !== null || uptime90d !== null}
		<div class="flex items-center gap-3 text-[11px] text-slate-500 dark:text-slate-400">
			<span class="eyebrow">Uptime</span>
			{#if uptime24h !== null}
				<span class="tabular-nums"
					>24h <strong class={uptimeColor(uptime24h)}>{uptime24h}%</strong></span
				>
			{/if}
			{#if uptime7d !== null}
				<span class="tabular-nums"
					>7j <strong class={uptimeColor(uptime7d)}>{uptime7d}%</strong></span
				>
			{/if}
			{#if uptime30d !== null}
				<span class="tabular-nums"
					>30j <strong class={uptimeColor(uptime30d)}>{uptime30d}%</strong></span
				>
			{/if}
			{#if uptime90d !== null}
				<span class="tabular-nums"
					>90j <strong class={uptimeColor(uptime90d)}>{uptime90d}%</strong></span
				>
			{/if}
		</div>
	{/if}

	{#if groups.length > 0 && onAssignGroup}
		<select
			class="self-start text-[11px] rounded-md border border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-slate-800 px-2 py-1 text-slate-600 dark:text-slate-300 focus:outline-none focus:ring-1 focus:ring-cyan-500"
			value={groupId == null ? '' : String(groupId)}
			on:click|stopPropagation
			on:change={(e) =>
				onAssignGroup(id, e.currentTarget.value === '' ? null : Number(e.currentTarget.value))}
		>
			<option value="">Sans groupe</option>
			{#each groups as g (g.id)}<option value={String(g.id)}>{g.name}</option>{/each}
		</select>
	{/if}
	<StatusBar {history} monitorId={id} />
</div>
