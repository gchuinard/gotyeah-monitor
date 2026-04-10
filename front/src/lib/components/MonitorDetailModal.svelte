<script lang="ts">
	import Sparkline from '$lib/components/Sparkline.svelte';
	import StatusBar from '$lib/components/StatusBar.svelte';
	import { auth } from '$lib/stores/auth';
	import type { MonitorCardData } from '$lib/stores/monitors';

	export let monitor: MonitorCardData;
	export let onClose: () => void;
	export let onDeleted: () => void;

	const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

	let mode = 1;
	let deleting = false;
	let showConfirmDelete = false;

	// ── Mode édition ───────────────────────────────────────────────────────
	let editing = false;
	let editName = '';
	let editUrl = '';
	let editType = 'http';
	let editExpectedCode = 200;
	let submitting = false;
	let editError: string | null = null;

	function openEdit() {
		editName = monitor.name;
		editUrl = monitor.url;
		editType = monitor.type;
		editExpectedCode = monitor.expectedStatusCode;
		editError = null;
		editing = true;
	}

	async function saveEdit() {
		submitting = true;
		editError = null;
		try {
			const res = await fetch(`${API_URL}/monitors/${monitor.id}`, {
				method: 'PUT',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${$auth.token ?? ''}`
				},
				body: JSON.stringify({
					name: editName,
					url: editUrl,
					type: editType,
					expected_status_code: editExpectedCode
				})
			});
			if (!res.ok) throw new Error(await res.text().catch(() => `HTTP ${res.status}`));
			editing = false;
			onDeleted(); // rafraîchit la liste
		} catch (err) {
			editError = err instanceof Error ? err.message : 'Erreur inconnue';
		} finally {
			submitting = false;
		}
	}

	$: latencyValues = monitor.history
		.map((c) => c.latency_ms)
		.filter((v): v is number => v !== null);

	function toUtcDate(s: string): Date {
		return new Date(s.endsWith('Z') || s.includes('+') ? s : s + 'Z');
	}

	function formatRelative(dateStr: string | null): string {
		if (!dateStr) return 'Jamais vérifié';
		const d = toUtcDate(dateStr);
		if (Number.isNaN(d.getTime())) return 'Inconnu';
		const diffMs = Date.now() - d.getTime();
		const diffSec = Math.round(diffMs / 1000);
		if (diffSec < 60) return `il y a ${diffSec}s`;
		const diffMin = Math.round(diffSec / 60);
		if (diffMin < 60) return `il y a ${diffMin} min`;
		const diffH = Math.round(diffMin / 60);
		if (diffH < 24) return `il y a ${diffH} h`;
		return `il y a ${Math.round(diffH / 24)} j`;
	}

	function formatDate(dateStr: string): string {
		const d = toUtcDate(dateStr);
		return Number.isNaN(d.getTime()) ? 'Inconnu' : d.toLocaleString();
	}

	function latencyColor(lat: number | null) {
		if (lat === null) return 'text-gray-400';
		if (lat < 150) return 'text-emerald-400';
		if (lat < 400) return 'text-yellow-400';
		return 'text-red-500';
	}

	function sslStatus(expiryStr: string | null): { label: string; color: string } {
		if (!expiryStr) return { label: 'N/A', color: 'text-slate-400' };
		const daysLeft = Math.ceil((toUtcDate(expiryStr).getTime() - Date.now()) / 86400000);
		if (daysLeft < 0) return { label: 'Expiré', color: 'text-rose-500' };
		if (daysLeft < 14) return { label: `${daysLeft}j restants`, color: 'text-rose-400' };
		if (daysLeft < 30) return { label: `${daysLeft}j restants`, color: 'text-amber-400' };
		return { label: `${daysLeft}j restants`, color: 'text-emerald-400' };
	}

	const statusColor = {
		up: 'text-emerald-400',
		down: 'text-red-400',
		checking: 'text-sky-300 animate-pulse'
	};

	const statusIcon = { up: '🟢', down: '🔴', checking: '⏳' };

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onClose();
	}

	async function confirmDelete() {
		if (deleting) return;
		deleting = true;
		try {
			const res = await fetch(`${API_URL}/monitors/${monitor.id}`, {
				method: 'DELETE',
				headers: { Authorization: `Bearer ${$auth.token ?? ''}` }
			});
			if (!res.ok && res.status !== 204)
				throw new Error(await res.text().catch(() => `HTTP ${res.status}`));
			onClose();
			onDeleted();
		} catch (err) {
			alert(err instanceof Error ? err.message : 'Erreur inconnue');
		} finally {
			deleting = false;
		}
	}
</script>

<svelte:window on:keydown={onKeydown} />

<div
	class="fixed inset-0 z-[100] flex items-center justify-center p-4"
	style="background: rgba(0,0,0,0.6); backdrop-filter: blur(8px);"
	on:click={onClose}
	role="presentation"
>
	<div
		class="w-full max-w-lg rounded-3xl bg-slate-950 border border-slate-800
			   shadow-[0_0_80px_rgba(56,189,248,0.5)] flex flex-col gap-4 overflow-hidden"
		on:click|stopPropagation
		role="dialog"
		aria-modal="true"
	>
		{#if editing}
		<!-- ── Formulaire d'édition ───────────────────────────────────────── -->
		<div class="flex items-center justify-between px-6 pt-5">
			<h2 class="font-bold text-lg text-slate-50">Modifier le monitor</h2>
			<button
				class="h-7 w-7 flex items-center justify-center rounded-full text-slate-400 hover:text-white hover:bg-slate-800 transition"
				on:click={() => (editing = false)} aria-label="Retour"
			>
				<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
				</svg>
			</button>
		</div>

		<form class="px-6 pb-6 flex flex-col gap-4" on:submit|preventDefault={saveEdit}>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-slate-400 uppercase tracking-wide">Nom</span>
				<input
					class="px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-slate-100
						   focus:outline-none focus:ring-2 focus:ring-cyan-400/60 text-sm"
					bind:value={editName} required
				/>
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs text-slate-400 uppercase tracking-wide">URL</span>
				<input
					class="px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-slate-100
						   focus:outline-none focus:ring-2 focus:ring-cyan-400/60 text-sm"
					bind:value={editUrl} required
				/>
			</label>
			<div class="grid grid-cols-2 gap-3">
				<label class="flex flex-col gap-1">
					<span class="text-xs text-slate-400 uppercase tracking-wide">Type</span>
					<select
						class="px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-slate-100
							   focus:outline-none focus:ring-2 focus:ring-cyan-400/60 text-sm"
						bind:value={editType}
					>
						<option value="http">HTTP</option>
						<option value="ping">Ping</option>
						<option value="port">Port</option>
					</select>
				</label>
				<label class="flex flex-col gap-1">
					<span class="text-xs text-slate-400 uppercase tracking-wide">Code HTTP attendu</span>
					<input
						type="number" min="100" max="599"
						class="px-3 py-2 rounded-xl bg-slate-900 border border-slate-700 text-slate-100
							   focus:outline-none focus:ring-2 focus:ring-cyan-400/60 text-sm"
						bind:value={editExpectedCode}
					/>
				</label>
			</div>

			{#if editError}
				<p class="text-xs text-rose-400 bg-rose-900/20 border border-rose-800/50 rounded-xl px-3 py-2">
					{editError}
				</p>
			{/if}

			<div class="flex justify-end gap-2 pt-1">
				<button type="button" class="btn btn-sm btn-secondary" on:click={() => (editing = false)} disabled={submitting}>
					Annuler
				</button>
				<button type="submit" class="btn btn-sm btn-primary disabled:opacity-50" disabled={submitting}>
					{submitting ? 'Enregistrement...' : 'Enregistrer'}
				</button>
			</div>
		</form>

		{:else}
		<!-- ── Vue détail ─────────────────────────────────────────────────── -->

		<!-- Header -->
		<div class="flex items-center justify-between px-6 pt-5">
			<div class="flex items-center gap-3">
				<span class="text-2xl">{statusIcon[monitor.status]}</span>
				<div>
					<h2 class="font-bold text-lg text-slate-50 leading-tight">{monitor.name}</h2>
					<a
						href={monitor.url}
						target="_blank"
						rel="noreferrer"
						class="text-xs text-cyan-500 hover:underline block truncate max-w-xs"
					>{monitor.url}</a>
				</div>
			</div>
			<div class="flex items-center gap-2">
				<span class="px-2 py-1 text-xs rounded bg-gotyeah-600/20 text-gotyeah-200 border border-gotyeah-600/30">
					{monitor.type}
				</span>
				<button
					class="h-7 w-7 flex items-center justify-center rounded-full text-slate-400 hover:text-white hover:bg-slate-800 transition"
					on:click={onClose}
					aria-label="Fermer"
				>
					<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			</div>
		</div>

		<!-- Stats -->
		<div class="grid grid-cols-3 gap-3 px-6">
			<div class="rounded-xl bg-slate-900 border border-slate-800 px-3 py-2 flex flex-col gap-0.5">
				<span class="text-[10px] text-slate-500 uppercase tracking-wide">Statut</span>
				<span class={`text-sm font-semibold ${statusColor[monitor.status]}`}>
					{monitor.status === 'up' ? 'Online' : monitor.status === 'down' ? 'Offline' : 'Checking...'}
				</span>
			</div>
			<div class="rounded-xl bg-slate-900 border border-slate-800 px-3 py-2 flex flex-col gap-0.5">
				<span class="text-[10px] text-slate-500 uppercase tracking-wide">Latence</span>
				<span class={`text-sm font-semibold ${latencyColor(monitor.latency)}`}>
					{monitor.latency !== null ? `${monitor.latency} ms` : 'N/A'}
				</span>
			</div>
			<div class="rounded-xl bg-slate-900 border border-slate-800 px-3 py-2 flex flex-col gap-0.5">
				<span class="text-[10px] text-slate-500 uppercase tracking-wide">HTTP</span>
				<span class={`text-sm font-semibold ${monitor.lastStatusCode === monitor.expectedStatusCode ? 'text-emerald-400' : 'text-red-400'}`}>
					{monitor.lastStatusCode ?? 'N/A'}
					<span class="text-slate-500 font-normal text-xs">/ {monitor.expectedStatusCode}</span>
				</span>
			</div>
		</div>

		<!-- SSL -->
		{#if monitor.sslExpiryAt !== null}
			{@const ssl = sslStatus(monitor.sslExpiryAt)}
			<div class="px-6 flex items-center justify-between text-xs">
				<span class="text-slate-400 flex items-center gap-1.5">
					<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
					</svg>
					Certificat SSL
				</span>
				<span class={`font-medium ${ssl.color}`}>
					{ssl.label} · exp. {toUtcDate(monitor.sslExpiryAt).toLocaleDateString('fr-FR')}
				</span>
			</div>
		{/if}

		<!-- Status bar -->
		<div class="px-6">
			<StatusBar history={monitor.history} />
		</div>

		<!-- Graphiques -->
		<div class="px-6 flex flex-col gap-4">

			<!-- Tabs -->
			<div class="flex gap-1 p-1 rounded-xl bg-slate-900 border border-slate-800">
				<button
					class={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-medium transition-all duration-200
						${mode === 0 ? 'bg-slate-700 text-white shadow-sm' : 'text-slate-500 hover:text-slate-300'}`}
					on:click={() => (mode = 0)}
				>
					<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
						<polyline points="22 12 18 12 15 21 9 3 6 12 2 12" stroke-linecap="round" stroke-linejoin="round"/>
					</svg>
					Latence
				</button>
				<button
					class={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-medium transition-all duration-200
						${mode === 1 ? 'bg-slate-700 text-white shadow-sm' : 'text-slate-500 hover:text-slate-300'}`}
					on:click={() => (mode = 1)}
				>
					<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
						<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
					</svg>
					Les deux
				</button>
				<button
					class={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-medium transition-all duration-200
						${mode === 2 ? 'bg-slate-700 text-white shadow-sm' : 'text-slate-500 hover:text-slate-300'}`}
					on:click={() => (mode = 2)}
				>
					<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
						<line x1="8" y1="6" x2="21" y2="6" stroke-linecap="round"/><line x1="8" y1="12" x2="21" y2="12" stroke-linecap="round"/><line x1="8" y1="18" x2="21" y2="18" stroke-linecap="round"/><circle cx="3" cy="6" r="1.5" fill="currentColor"/><circle cx="3" cy="12" r="1.5" fill="currentColor"/><circle cx="3" cy="18" r="1.5" fill="currentColor"/>
					</svg>
					Historique
				</button>
			</div>

			{#if mode === 0 || mode === 1}
				<Sparkline
					values={latencyValues}
					timestamps={monitor.history.filter(c => c.latency_ms !== null).map(c => c.checked_at)}
					height={160}
				/>
			{/if}

			{#if mode === 1 || mode === 2}
				<div class="flex flex-col gap-1 max-h-48 overflow-y-auto pr-1">
					{#each [...monitor.history].reverse() as c (c.id)}
						<div class="flex items-center gap-2 px-3 py-1.5 bg-slate-900 rounded-lg border border-slate-800/60 text-xs">
							{#if c.status === 'up'}
								<span class="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0"></span>
							{:else}
								<span class="w-1.5 h-1.5 rounded-full bg-red-400 shrink-0"></span>
							{/if}
							<span class={`font-mono font-medium ${c.latency_ms !== null ? latencyColor(c.latency_ms) : 'text-gray-500'}`}>
								{c.latency_ms !== null ? `${c.latency_ms} ms` : '—'}
							</span>
							<span class="ml-auto text-slate-500 font-mono text-[11px]">
								{toUtcDate(c.checked_at).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
							</span>
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<!-- Footer -->
		<div class="px-6 pb-5 border-t border-slate-800 pt-4 flex items-center justify-between">
			<div class="text-[11px] text-slate-500 flex flex-col gap-0.5">
				<span>Dernier check : {formatRelative(monitor.lastCheckedAt)}</span>
				<span>Créé le : {formatDate(monitor.createdAt)}</span>
			</div>
			<div class="flex items-center gap-2">
				{#if !showConfirmDelete}
					<button class="btn btn-sm btn-primary" on:click={openEdit}>
						Modifier
					</button>
					<button
						class="btn btn-sm btn-danger disabled:opacity-50"
						on:click={() => (showConfirmDelete = true)}
						disabled={deleting}
					>
						Supprimer
					</button>
				{:else}
					<span class="text-[11px] text-slate-400 mr-1">
						Supprimer <span class="text-gotyeah-300 font-semibold">"{monitor.name}"</span> ?
					</span>
					<button class="btn btn-sm btn-secondary" on:click={() => (showConfirmDelete = false)} disabled={deleting}>
						Annuler
					</button>
					<button class="btn btn-sm btn-danger disabled:opacity-50" on:click={confirmDelete} disabled={deleting}>
						{deleting ? 'Oui…' : 'Confirmer'}
					</button>
				{/if}
			</div>
		</div>

		{/if}
		<!-- fin {#if editing} -->
	</div>
</div>
