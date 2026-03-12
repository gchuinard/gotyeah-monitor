<script lang="ts">
	import { monitors, type MonitorCardData } from '$lib/stores/monitors';
	import { auth, clearAuth, type AuthState } from '$lib/stores/auth';
	import MonitorCard from '$lib/components/MonitorCard.svelte';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';

	const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

	type MonitorFromApi = {
		id: number;
		name: string;
		url: string;
		type: string;
		status: string;
		last_latency_ms: number | null;
		last_checked_at: string | null;
		expected_status_code: number;
		last_status_code: number | null;
		created_at: string;
	};

	let loading = false;
	let error: string | null = null;
	let authState: AuthState;
	let viewMode: 'grid' | 'list' = 'grid';

	$: auth.subscribe((v) => (authState = v));

	function logout() {
		clearAuth();
		goto('/login');
	}

	async function fetchMonitors() {
		loading = true;
		error = null;
		try {
			if (!authState?.token) {
				await goto('/login');
				return;
			}

			const res = await fetch(`${API_URL}/monitors`, {
				headers: {
					Authorization: `Bearer ${authState.token}`
				}
			});

			if (!res.ok) {
				throw new Error(`HTTP ${res.status}`);
			}

			const data = (await res.json()) as MonitorFromApi[];

			monitors.update((current) => {
				const byId = new Map(current.map((m) => [m.id, m]));

				const mapped: MonitorCardData[] = data.map((m) => {
					const previous = byId.get(m.id);
					let history = previous?.history ? [...previous.history] : [];

					if (m.last_latency_ms !== null) {
						history.push(m.last_latency_ms);
						if (history.length > 20) {
							history = history.slice(history.length - 20);
						}
					}

					return {
						id: m.id,
						name: m.name,
						url: m.url,
						status: m.status === 'unknown' ? 'checking' : (m.status as 'up' | 'down'),
						type: m.type,
						latency: m.last_latency_ms,
						history,
						lastCheckedAt: m.last_checked_at,
						expectedStatusCode: m.expected_status_code,
						lastStatusCode: m.last_status_code,
						createdAt: m.created_at
					};
				});

				return mapped;
			});
		} catch (err) {
			console.error('Erreur lors du fetch /monitors', err);
			error = err instanceof Error ? err.message : 'Erreur inconnue';
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		fetchMonitors();
	});
</script>

<div class="min-h-screen flex items-start justify-center pt-10 pb-12">
	<div
		class="w-full max-w-6xl mx-auto
           rounded-3xl bg-white/80 dark:bg-slate-900/90 backdrop-blur-2xl
           border border-white/70 dark:border-slate-800 shadow-[0_0_60px_rgba(56,189,248,0.28)]
           overflow-hidden"
	>
		<div
			class="flex items-center justify-between px-8 pt-7 pb-4 border-b border-slate-200/80 dark:border-slate-800"
		>
			<div class="flex flex-col gap-1">
				<div class="text-xs uppercase tracking-[0.25em] text-slate-400 dark:text-slate-500">
					GotYeah Monitor
				</div>
				<div class="text-2xl font-semibold text-slate-900 dark:text-slate-50">Moniteurs</div>
			</div>
			<div class="flex items-center gap-3">
				<div class="relative">
					<button
						type="button"
						class="btn btn-sm btn-secondary flex items-center gap-2"
						on:click={() => goto('/profile')}
					>
						<span
							class="inline-flex h-6 w-6 items-center justify-center rounded-full bg-cyan-500 text-white text-xs"
						>
							{authState?.user?.email?.[0]?.toUpperCase() ?? '?'}
						</span>
						<span class="max-w-[140px] truncate">
							{authState?.user?.email ?? 'Profil'}
						</span>
					</button>
				</div>
				<button
					type="button"
					class="btn btn-sm btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
					on:click={fetchMonitors}
					disabled={loading}
				>
					{loading ? 'Chargement...' : 'Rafraîchir'}
				</button>
				<button
					type="button"
					class={`btn btn-sm ${
						viewMode === 'grid'
							? 'btn-ghost'
							: 'btn-secondary bg-slate-800 text-slate-100 border-slate-600'
					}`}
					on:click={() => (viewMode = viewMode === 'grid' ? 'list' : 'grid')}
				>
					{viewMode === 'grid' ? 'Vue liste' : 'Vue grille'}
				</button>
				<button type="button" class="btn btn-sm btn-primary" on:click={() => goto('/add')}>
					Ajouter
				</button>
				<button type="button" class="btn btn-sm btn-secondary" on:click={logout}>
					Déconnexion
				</button>
			</div>
		</div>

		{#if error}
			<div class="px-8 pt-3 pb-2 text-sm text-rose-500">{error}</div>
		{/if}

		<div
			class={viewMode === 'grid'
				? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 p-8'
				: 'flex flex-col gap-4 p-8'}
		>
			{#each $monitors as m (m.id)}
				<MonitorCard {...m} onDeleted={fetchMonitors} compact={viewMode === 'list'} />
			{/each}
		</div>
	</div>
</div>
