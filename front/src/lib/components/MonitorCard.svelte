<script lang="ts">
	import { onMount, beforeUpdate } from 'svelte';
	import StatusBar from '$lib/components/StatusBar.svelte';
	import type { CheckEntry } from '$lib/stores/monitors';

	export let id: number;
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
	export let onDeleted: (() => void) | undefined;
	export let onToggleDetails: () => void = () => {};
	export let showDetails = false;
	export let compact = false;

	let prevStatus: typeof status;
	let animationClass = '';
	let mounted = false;

	onMount(() => setTimeout(() => (mounted = true), 20));

	beforeUpdate(() => {
		if (prevStatus && status !== prevStatus) {
			animationClass = status === 'up' ? 'animate-flashGreen' : 'animate-flashRed';
			setTimeout(() => (animationClass = ''), 600);
		}
		prevStatus = status;
	});

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
</script>

<div
	role="button"
	tabindex="0"
	on:click={onToggleDetails}
	on:keydown={(e) => e.key === 'Enter' && onToggleDetails()}
	class={`relative rounded-3xl border cursor-pointer select-none
		bg-white/80 dark:bg-slate-950/80 backdrop-blur-2xl
		shadow-[0_0_35px_rgba(56,189,248,0.28)] dark:shadow-[0_0_45px_rgba(56,189,248,0.4)]
		hover:shadow-[0_0_55px_rgba(56,189,248,0.45)] hover:-translate-y-0.5 hover:scale-[1.01]
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
					<span class="px-1.5 py-0.5 text-[10px] rounded bg-gotyeah-600/20 text-gotyeah-200 border border-gotyeah-600/30 shrink-0">{type}</span>
				</div>
				<div class="flex items-center gap-4 text-xs text-slate-400 flex-wrap">
					<span class={`font-medium ${latencyColor(latency)}`}>{latency !== null ? `${latency} ms` : 'N/A'}</span>
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
			</div>
			<span class="px-2 py-1 text-xs rounded bg-gotyeah-600/20 text-gotyeah-200 border border-gotyeah-600/30">{type}</span>
		</div>

		<div class="flex items-center gap-3 text-sm">
			<span class={statusColor[status]}>
				{status === 'up' ? 'Online' : status === 'down' ? 'Offline' : 'Checking...'}
			</span>
			<span class="text-slate-500 text-xs">·</span>
			<span class={`font-medium ${latencyColor(latency)}`}>
				{latency !== null ? `${latency} ms` : 'N/A'}
			</span>
		</div>

		<div class="text-xs text-slate-500 dark:text-slate-400">
			<a href={url} target="_blank" rel="noreferrer"
				class="truncate text-cyan-600 hover:text-cyan-500 hover:underline block"
				title={url} on:click|stopPropagation>{url}</a>
			<span class="mt-0.5 block">{formatRelative(lastCheckedAt)}</span>
		</div>
	{/if}

	<StatusBar {history} />
</div>
