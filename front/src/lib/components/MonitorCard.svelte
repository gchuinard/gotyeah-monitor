<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import Sparkline from '$lib/components/Sparkline.svelte';

	export let id: number;
	export let name: string;
	export let url: string;
	export let status: 'up' | 'down' | 'checking';
	export let type: string = 'Service';
	export let latency: number | null = null;
	export let history: number[] = [];
	export let lastCheckedAt: string | null = null;
	export let createdAt: string;
	export let expectedStatusCode: number;
	export let lastStatusCode: number | null;
	export let onDeleted: (() => void) | undefined;
	export let compact = false;

	let showDetails = false;
	let mode = 1;

	// Animations UP/DOWN
	let prevStatus: typeof status;
	let animationClass = '';

	onMount(() => {
		prevStatus = status;
		setTimeout(() => (mounted = true), 20);
	});

	$: if (prevStatus && status !== prevStatus) {
		animationClass = status === 'up' ? 'animate-flashGreen' : 'animate-flashRed';
		prevStatus = status;
		setTimeout(() => (animationClass = ''), 600);
	}
	const statusColor = {
		up: 'text-gotyeah-400',
		down: 'text-red-400',
		checking: 'text-gotyeah-200 animate-pulse'
	};

	const statusIcon = {
		up: '🟢',
		down: '🔴',
		checking: '⏳'
	};

	function formatRelative(dateStr: string | null): string {
		if (!dateStr) return 'Jamais vérifié';
		const d = new Date(dateStr);
		if (Number.isNaN(d.getTime())) return 'Inconnu';

		const diffMs = Date.now() - d.getTime();
		const diffSec = Math.round(diffMs / 1000);
		if (diffSec < 60) return `il y a ${diffSec}s`;
		const diffMin = Math.round(diffSec / 60);
		if (diffMin < 60) return `il y a ${diffMin} min`;
		const diffH = Math.round(diffMin / 60);
		if (diffH < 24) return `il y a ${diffH} h`;
		const diffD = Math.round(diffH / 24);
		return `il y a ${diffD} j`;
	}

	function formatDate(dateStr: string): string {
		const d = new Date(dateStr);
		if (Number.isNaN(d.getTime())) return 'Inconnu';
		return d.toLocaleString();
	}

	function latencyColor(lat: number | null) {
		if (lat === null) return 'text-gray-400';
		if (lat < 150) return 'text-gotyeah-400';
		if (lat < 400) return 'text-yellow-400';
		return 'text-red-500';
	}

	// Animation fade+slide
	let mounted = false;
	let deleting = false;
	let showConfirmDelete = false;

	const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

	function openDeleteConfirm() {
		if (deleting) return;
		showConfirmDelete = true;
	}

	function closeDeleteConfirm() {
		if (deleting) return;
		showConfirmDelete = false;
	}

	async function confirmDelete() {
		if (deleting) return;
		deleting = true;

		try {
			const stored = typeof localStorage !== 'undefined' ? localStorage.getItem('auth') : null;
			const token = stored ? (JSON.parse(stored).token as string | null) : null;

			const res = await fetch(`${API_URL}/monitors/${id}`, {
				method: 'DELETE',
				headers: {
					...(token ? { Authorization: `Bearer ${token}` } : {})
				}
			});

			if (!res.ok && res.status !== 204) {
				const text = await res.text().catch(() => '');
				throw new Error(text || `HTTP ${res.status}`);
			}

			showConfirmDelete = false;
			onDeleted?.();
		} catch (e) {
			alert(e instanceof Error ? e.message : 'Erreur inconnue');
		} finally {
			deleting = false;
		}
	}
</script>

<!-- CARD -->
<div
	class={`relative rounded-3xl overflow-hidden border 
    bg-white/80 dark:bg-slate-950/80 backdrop-blur-2xl 
    shadow-[0_0_35px_rgba(56,189,248,0.28)] dark:shadow-[0_0_45px_rgba(56,189,248,0.4)]
    ${showConfirmDelete ? '' : 'hover:shadow-[0_0_55px_rgba(56,189,248,0.45)] hover:-translate-y-0.5 hover:scale-[1.01]'}
    transition-all duration-300
    ${mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-3'}
    ${animationClass}
    ${compact ? 'p-4 flex items-center gap-6' : 'p-5 flex flex-col gap-3'}
    ${
			status === 'up'
				? 'border-cyan-400/70'
				: status === 'down'
					? 'border-rose-400/70'
					: 'border-sky-300/70'
		}`}
>
	{#if compact}
		<!-- Layout horizontal compact (mode liste) -->
		<div class="flex items-start gap-3 flex-1 min-w-0">
			<div class="flex flex-col items-center gap-1">
				<span class="text-xl">{statusIcon[status]}</span>
				<span class={`text-xs ${statusColor[status]}`}>
					{status === 'up' ? 'Online' : status === 'down' ? 'Offline' : 'Checking...'}
				</span>
			</div>

			<div class="flex flex-col gap-1 flex-1 min-w-0">
				<div class="flex items-center justify-between gap-2">
					<h2 class="font-semibold text-base text-slate-900 dark:text-slate-50 truncate">
						{name}
					</h2>
					<span
						class="px-2 py-0.5 text-[11px] rounded bg-gotyeah-600/20 text-gotyeah-200 border border-gotyeah-600/30 shrink-0"
					>
						{type}
					</span>
				</div>

				<div class="flex items-center gap-6 text-xs text-slate-400 dark:text-slate-300 flex-wrap">
					<div class="flex items-center gap-1">
						<span class="text-gray-400">Latence :</span>
						<span class={`font-medium ${latencyColor(latency)}`}>
							{latency !== null ? `${latency} ms` : 'N/A'}
						</span>
					</div>
					<div>
						Code HTTP :
						<span
							class={lastStatusCode === expectedStatusCode ? 'text-gotyeah-300' : 'text-red-400'}
						>
							{lastStatusCode ?? 'N/A'}
						</span>
						<span class="text-gray-500"> / {expectedStatusCode}</span>
					</div>
					<div class="truncate max-w-xs">
						<a
							href={url}
							target="_blank"
							rel="noreferrer"
							class="text-cyan-500 hover:text-cyan-400 hover:underline"
							title={url}
						>
							{url}
						</a>
					</div>
				</div>

				<div
					class="flex items-center gap-4 text-[11px] text-slate-500 dark:text-slate-400 flex-wrap"
				>
					<span>Dernier check : {formatRelative(lastCheckedAt)}</span>
					<span>Créé le : {formatDate(createdAt)}</span>
				</div>
			</div>
		</div>

		<div class="flex flex-col items-end justify-between gap-2 self-stretch">
			<button
				class="text-gray-400 hover:text-white transition flex items-center gap-1 text-xs"
				on:click={() => (showDetails = !showDetails)}
			>
				{#if showDetails}
					🙈 <span>Cacher</span>
				{:else}
					👁️ <span>Détails</span>
				{/if}
			</button>

			<div class="flex items-center gap-2">
				<button class="btn btn-sm btn-primary" type="button" on:click={() => goto(`/edit/${id}`)}>
					Modifier
				</button>

				<button
					class="btn btn-sm btn-danger disabled:opacity-50"
					type="button"
					on:click={openDeleteConfirm}
					disabled={deleting}
				>
					{deleting ? 'Suppression...' : 'Supprimer'}
				</button>
			</div>
			{#if showConfirmDelete}
				<div class="mt-2 flex items-center justify-end gap-2 text-xs text-slate-300">
					<span class="mr-auto text-[11px] text-slate-400">
						Supprimer <span class="font-semibold text-gotyeah-300">"{name}"</span> ?
					</span>
					<button
						type="button"
						class="btn btn-sm btn-secondary"
						on:click={closeDeleteConfirm}
						disabled={deleting}
					>
						Annuler
					</button>
					<button
						type="button"
						class="btn btn-sm btn-danger disabled:opacity-50"
						on:click={confirmDelete}
						disabled={deleting}
					>
						{deleting ? 'Oui…' : 'Confirmer'}
					</button>
				</div>
			{/if}
		</div>
	{:else}
		<!-- Layout original (mode grille) -->
		<!-- HEADER -->
		<div class="flex items-center justify-between">
			<div class="flex items-center gap-2">
				<span class="text-xl">{statusIcon[status]}</span>
				<h2 class="font-semibold text-lg text-slate-900 dark:text-slate-50">{name}</h2>
			</div>

			<span
				class="px-2 py-1 text-xs rounded bg-gotyeah-600/20 text-gotyeah-200 border border-gotyeah-600/30"
			>
				{type}
			</span>
		</div>

		<!-- STATUS -->
		<div class="flex items-center gap-2">
			<span class={statusColor[status]}>
				{status === 'up' ? 'Online' : status === 'down' ? 'Offline' : 'Checking...'}
			</span>
		</div>

		<!-- LATENCY -->
		<div class="flex flex-col gap-0.5 text-sm">
			<div class="flex items-center">
				<span class="text-gray-400">Latence :</span>
				<span class={`ml-2 font-medium ${latencyColor(latency)}`}>
					{latency !== null ? `${latency} ms` : 'N/A'}
				</span>
			</div>
			<div class="text-xs text-gray-400">
				Code HTTP reçu :
				<span class={lastStatusCode === expectedStatusCode ? 'text-gotyeah-300' : 'text-red-400'}>
					{lastStatusCode ?? 'N/A'}
				</span>
				<span class="text-gray-500"> (attendu {expectedStatusCode})</span>
			</div>
		</div>

		<!-- URL + métadonnées -->
		<div class="flex flex-col gap-1 text-xs text-slate-500 dark:text-slate-400">
			<a
				href={url}
				target="_blank"
				rel="noreferrer"
				class="truncate text-cyan-600 hover:text-cyan-500 hover:underline"
				title={url}
			>
				{url}
			</a>
			<div class="flex flex-wrap gap-x-4 gap-y-1">
				<span>Dernier check : {formatRelative(lastCheckedAt)}</span>
				<span>Créé le : {formatDate(createdAt)}</span>
			</div>
		</div>

		<!-- DETAILS SECTION -->
		<div class="mt-2 border-t border-white/10 pt-3">
			<div class="flex items-center justify-between gap-3">
				<button
					class="text-gray-400 hover:text-white transition flex items-center gap-1 text-sm"
					on:click={() => (showDetails = !showDetails)}
				>
					{#if showDetails}
						🙈 <span>Cacher détails</span>
					{:else}
						👁️ <span>Voir détails</span>
					{/if}
				</button>

				<button class="btn btn-sm btn-primary" type="button" on:click={() => goto(`/edit/${id}`)}>
					Modifier
				</button>

				<button
					class="btn btn-sm btn-danger disabled:opacity-50"
					type="button"
					on:click={openDeleteConfirm}
					disabled={deleting}
				>
					{deleting ? 'Suppression...' : 'Supprimer'}
				</button>
			</div>

			{#if showDetails}
				<div class="mt-3 flex flex-col gap-4">
					<!-- TOGGLE 0 / 1 / 2 -->
					<div class="flex items-center gap-3 text-xs text-gray-300">
						<span>Affichage :</span>

						<div class="relative w-40 h-8 bg-gray-700 rounded-full flex items-center px-1">
							<button
								class={`flex-1 h-full flex items-center justify-center rounded-full transition
                ${mode === 0 ? 'bg-gotyeah-500 text-white' : 'text-gray-400'}`}
								on:click={() => (mode = 0)}
							>
								Spark
							</button>

							<button
								class={`flex-1 h-full flex items-center justify-center rounded-full transition
                ${mode === 1 ? 'bg-gotyeah-500 text-white' : 'text-gray-400'}`}
								on:click={() => (mode = 1)}
							>
								Les deux
							</button>

							<button
								class={`flex-1 h-full flex items-center justify-center rounded-full transition
                ${mode === 2 ? 'bg-gotyeah-500 text-white' : 'text-gray-400'}`}
								on:click={() => (mode = 2)}
							>
								Historique
							</button>
						</div>
					</div>

					<!-- SPARKLINE -->
					{#if mode === 0 || mode === 1}
						<div class="mt-2">
							<Sparkline values={history} />
						</div>
					{/if}

					<!-- HISTORIQUE LISTE -->
					{#if mode === 1 || mode === 2}
						<div class="text-xs text-gray-400 flex flex-wrap gap-1 leading-relaxed">
							{#each history as h, i (i)}
								<span class="px-2 py-1 bg-gray-800/70 rounded border border-gray-600/30">
									{h} ms
								</span>
							{/each}
						</div>
					{/if}
				</div>
			{/if}
		</div>
	{/if}

	{#if showConfirmDelete && !compact}
		<!-- Modal de confirmation de suppression -->
		<div class="fixed inset-0 z-40 flex items-center justify-center bg-black/70">
			<div
				class="w-full max-w-xs rounded-3xl bg-slate-950/95 border border-slate-800
           shadow-[0_0_28px_rgba(56,189,248,0.55)] px-5 py-4 text-slate-100"
			>
				<h2 class="text-base font-semibold mb-1">Supprimer ce monitor ?</h2>
				<p class="text-xs text-slate-300 mb-3 leading-relaxed">
					Tu es sur le point de supprimer
					<span class="font-semibold text-gotyeah-300">"{name}"</span>. Cette action est définitive.
				</p>

				<div class="flex items-center justify-end gap-2 mt-3">
					<button
						type="button"
						class="btn btn-sm btn-secondary"
						on:click={closeDeleteConfirm}
						disabled={deleting}
					>
						Annuler
					</button>
					<button
						type="button"
						class="btn btn-sm btn-danger disabled:opacity-50"
						on:click={confirmDelete}
						disabled={deleting}
					>
						{deleting ? 'Suppression...' : 'Supprimer'}
					</button>
				</div>
			</div>
		</div>
	{/if}
</div>
