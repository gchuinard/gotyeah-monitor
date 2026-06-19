<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';

	const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

	type PublicMonitor = {
		name: string;
		status: string;
		uptime_24h: number | null;
		uptime_30d: number | null;
		has_open_incident: boolean;
	};

	let loaded = false;
	let notFound = false;
	let error = '';
	let title = '';
	let monitors: PublicMonitor[] = [];

	$: slug = $page.params.slug;

	// Charge la page de statut publique par slug (GET /public/{slug}) : titre + moniteurs publics, gère 404/erreur.
	onMount(async () => {
		// fetch direct (endpoint public, sans token) — pas d'apiFetch (qui redirige sur 401).
		try {
			const res = await fetch(`${API_URL}/public/${slug}`);
			if (res.status === 404) {
				notFound = true;
				return;
			}
			if (res.ok) {
				const data = await res.json();
				title = data.title;
				monitors = data.monitors;
			} else {
				error = `Erreur ${res.status}`;
			}
		} catch {
			error = 'Impossible de contacter le serveur.';
		} finally {
			loaded = true;
		}
	});

	function uptimeColor(p: number | null) {
		if (p === null) return 'text-slate-500';
		return p >= 99.5 ? 'text-emerald-400' : p >= 95 ? 'text-yellow-400' : 'text-rose-400';
	}

	$: allUp = monitors.length > 0 && monitors.every((m) => m.status === 'up');
	$: anyDown = monitors.some((m) => m.status === 'down');
</script>

<svelte:head>
	<title>{title || 'Statut'} — GotYeah Monitor</title>
</svelte:head>

<div class="max-w-2xl mx-auto px-4 py-12">
	{#if !loaded}
		<p class="text-slate-400">Chargement…</p>
	{:else if notFound}
		<p class="text-slate-400">Page de statut introuvable.</p>
	{:else if error}
		<p class="text-rose-400">{error}</p>
	{:else}
		<header class="mb-8">
			<h1 class="text-2xl font-semibold">{title}</h1>
			<p
				class="mt-2 text-sm {anyDown
					? 'text-rose-400'
					: allUp
						? 'text-emerald-400'
						: 'text-slate-400'}"
			>
				{anyDown
					? 'Incident en cours'
					: allUp
						? 'Tous les services sont opérationnels'
						: 'Statut des services'}
			</p>
		</header>

		{#if monitors.length === 0}
			<p class="text-slate-400 text-sm">Aucun service public pour le moment.</p>
		{:else}
			<div class="flex flex-col gap-2.5">
				{#each monitors as m (m.name)}
					<div
						class="flex items-center gap-3 rounded-xl px-4 py-3 bg-slate-900/60 border border-slate-800 shadow-soft"
					>
						<span class="text-lg"
							>{m.status === 'up' ? '🟢' : m.status === 'down' ? '🔴' : '⚪'}</span
						>
						<span class="font-medium">{m.name}</span>
						{#if m.has_open_incident}
							<span
								class="text-[11px] px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/30"
								>incident</span
							>
						{/if}
						<span class="ml-auto text-xs flex items-center gap-3 tabular-nums">
							{#if m.uptime_24h !== null}
								<span class="text-slate-400"
									>24h <strong class={uptimeColor(m.uptime_24h)}>{m.uptime_24h}%</strong></span
								>
							{/if}
							{#if m.uptime_30d !== null}
								<span class="text-slate-400"
									>30j <strong class={uptimeColor(m.uptime_30d)}>{m.uptime_30d}%</strong></span
								>
							{/if}
						</span>
					</div>
				{/each}
			</div>
		{/if}

		<footer class="mt-10 text-center text-[11px] text-slate-600">
			Propulsé par GotYeah Monitor
		</footer>
	{/if}
</div>
