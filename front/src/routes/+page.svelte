<script lang="ts">
	import { monitors, type CheckEntry } from '$lib/stores/monitors';
	import { auth, clearAuth, type AuthState } from '$lib/stores/auth';
	import { parseApiError, parseNetworkError } from '$lib/utils/errors';
	import MonitorCard from '$lib/components/MonitorCard.svelte';
	import MonitorDetailModal from '$lib/components/MonitorDetailModal.svelte';
	import PasswordStrength from '$lib/components/PasswordStrength.svelte';
	import { onMount } from 'svelte';
	import { goto, preloadCode } from '$app/navigation';

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
		ssl_expiry_at: string | null;
		created_at: string;
	};

	let loading = false;
	let error: string | null = null;
	let authState: AuthState;
	let viewMode: 'grid' | 'list' = 'grid';
	let isAdmin = false;
	let openCardId: number | null = null;

	function toggleCardDetails(id: number) {
		openCardId = openCardId === id ? null : id;
	}

	// Add monitor modal
	let showAdd = false;
	let addName = '';
	let addUrl = '';
	let addType = 'http';
	let addExpectedStatusCode = 200;
	let addSubmitting = false;
	let addError: string | null = null;

	function openAdd() {
		addName = '';
		addUrl = '';
		addType = 'http';
		addExpectedStatusCode = 200;
		addError = null;
		showAdd = true;
	}

	async function submitAdd() {
		addSubmitting = true;
		addError = null;
		try {
			const res = await fetch(`${API_URL}/monitors`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${authState.token}`
				},
				body: JSON.stringify({
					name: addName,
					url: addUrl,
					type: addType,
					expected_status_code: addExpectedStatusCode
				})
			});
			if (!res.ok) throw new Error(await res.text().catch(() => `HTTP ${res.status}`));
			showAdd = false;
			await fetchMonitors();
		} catch (e) {
			addError = e instanceof Error ? e.message : 'Erreur inconnue';
		} finally {
			addSubmitting = false;
		}
	}

	// Utilise la réactivité Svelte pour suivre le store auth
	$: authState = $auth;

	// Profil modal
	let showProfile = false;
	let profileConfirmDelete = false;
	let profileDeleting = false;
	let profileDeleteConfirmText = '';

	// Email change
	let profileNewEmail = '';
	let profileEmailSubmitting = false;
	let profileEmailError: string | null = null;
	let profileEmailSuccess: string | null = null;

	// Password change
	let profilePassword = '';
	let profileConfirmPassword = '';
	let profilePasswordValid = false;
	let profilePasswordSubmitting = false;
	let profilePasswordError: string | null = null;
	let profilePasswordSuccess: string | null = null;

	$: profilePasswordsMatch =
		profileConfirmPassword === '' || profilePassword === profileConfirmPassword;
	$: profileCanSavePassword =
		!profilePasswordSubmitting &&
		profilePassword !== '' &&
		profilePasswordValid &&
		profilePassword === profileConfirmPassword;

	function openProfile() {
		profileNewEmail = '';
		profileEmailError = null;
		profileEmailSuccess = null;
		profilePassword = '';
		profileConfirmPassword = '';
		profilePasswordError = null;
		profilePasswordSuccess = null;
		profileConfirmDelete = false;
		profileDeleteConfirmText = '';
		showProfile = true;
	}

	async function submitEmailChange() {
		profileEmailSubmitting = true;
		profileEmailError = null;
		profileEmailSuccess = null;
		try {
			const res = await fetch(`${API_URL}/auth/change-email`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${authState.token}`
				},
				body: JSON.stringify({ new_email: profileNewEmail })
			});
			const data = await res.json();
			if (!res.ok) {
				profileEmailError = data.detail || 'Erreur lors de la demande.';
			} else {
				profileEmailSuccess = data.message;
				profileNewEmail = '';
			}
		} catch {
			profileEmailError = 'Impossible de contacter le serveur.';
		} finally {
			profileEmailSubmitting = false;
		}
	}

	async function deleteAccount() {
		profileDeleting = true;
		try {
			const res = await fetch(`${API_URL}/auth/me`, {
				method: 'DELETE',
				headers: { Authorization: `Bearer ${authState.token}` }
			});
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			clearAuth();
			goto('/login');
		} catch (e) {
			profilePasswordError = e instanceof Error ? e.message : 'Erreur inconnue';
			profileDeleting = false;
			profileConfirmDelete = false;
		}
	}

	async function savePassword() {
		profilePasswordSubmitting = true;
		profilePasswordError = null;
		profilePasswordSuccess = null;
		try {
			const res = await fetch(`${API_URL}/auth/me`, {
				method: 'PUT',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${authState.token}`
				},
				body: JSON.stringify({ password: profilePassword })
			});

			if (!res.ok) throw new Error(await res.text().catch(() => `HTTP ${res.status}`));

			profilePasswordSuccess = 'Mot de passe mis à jour.';
			profilePassword = '';
			profileConfirmPassword = '';
		} catch (e) {
			profilePasswordError = e instanceof Error ? e.message : 'Erreur inconnue';
		} finally {
			profilePasswordSubmitting = false;
		}
	}

	function logout() {
		clearAuth();
		goto('/login');
	}

	async function fetchHistory(monitorId: number): Promise<CheckEntry[]> {
		try {
			const res = await fetch(`${API_URL}/monitors/${monitorId}/history`, {
				headers: { Authorization: `Bearer ${authState.token}` }
			});
			if (!res.ok) return [];
			return (await res.json()) as CheckEntry[];
		} catch {
			return [];
		}
	}

	async function fetchMonitors() {
		loading = true;
		error = null;
		const minDelay = new Promise((r) => setTimeout(r, 1000));
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
				throw new Error(await parseApiError(res, 'chargement des monitors'));
			}

			const data = (await res.json()) as MonitorFromApi[];

			// Récupère l'historique de chaque monitor en parallèle
			const histories = await Promise.all(data.map((m) => fetchHistory(m.id)));

			monitors.set(
				data.map((m, i) => ({
					id: m.id,
					name: m.name,
					url: m.url,
					status: m.status === 'unknown' ? 'checking' : (m.status as 'up' | 'down'),
					type: m.type,
					latency: m.last_latency_ms,
					history: histories[i],
					lastCheckedAt: m.last_checked_at,
					expectedStatusCode: m.expected_status_code,
					lastStatusCode: m.last_status_code,
					sslExpiryAt: m.ssl_expiry_at,
					createdAt: m.created_at
				}))
			);
		} catch (err) {
			error = parseNetworkError(err, 'chargement des monitors');
		} finally {
			await minDelay;
			loading = false;
		}
	}

	async function checkAdmin() {
		if (!authState?.token) return;
		try {
			const res = await fetch(`${API_URL}/admin/check`, {
				headers: { Authorization: `Bearer ${authState.token}` }
			});
			if (res.ok) {
				const data = await res.json();
				isAdmin = data.is_admin;
			}
		} catch {
			/* ignore — admin check is best-effort */
		}
	}

	onMount(() => {
		fetchMonitors();
		checkAdmin();
		preloadCode('/profile', '/add', '/login');
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
			class="flex items-center justify-between px-8 pt-7 pb-5 border-b border-slate-200/60 dark:border-slate-800/80"
		>
			<!-- Left: branding + title -->
			<div class="flex flex-col gap-0.5">
				<div
					class="text-[10px] uppercase tracking-[0.3em] text-slate-400 dark:text-slate-500 font-medium"
				>
					GotYeah Monitor
				</div>
				<div class="text-2xl font-bold text-slate-900 dark:text-slate-50 tracking-tight">
					Moniteurs
				</div>
			</div>

			<!-- Right: actions -->
			<div class="flex items-center gap-2">
				<!-- View toggle -->
				<div
					class="flex items-center rounded-full border border-slate-200 dark:border-slate-700 bg-slate-100/80 dark:bg-slate-800/80 p-0.5 gap-0.5 cursor-pointer"
					on:click={() => (viewMode = viewMode === 'grid' ? 'list' : 'grid')}
					role="button"
					tabindex="0"
					on:keydown={(e) =>
						e.key === 'Enter' && (viewMode = viewMode === 'grid' ? 'list' : 'grid')}
				>
					<span
						class="rounded-full p-1.5 transition-all {viewMode === 'grid'
							? 'bg-white dark:bg-slate-700 shadow-sm text-cyan-500'
							: 'text-slate-400'}"
					>
						<svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 16 16">
							<rect x="1" y="1" width="6" height="6" rx="1" /><rect
								x="9"
								y="1"
								width="6"
								height="6"
								rx="1"
							/><rect x="1" y="9" width="6" height="6" rx="1" /><rect
								x="9"
								y="9"
								width="6"
								height="6"
								rx="1"
							/>
						</svg>
					</span>
					<span
						class="rounded-full p-1.5 transition-all {viewMode === 'list'
							? 'bg-white dark:bg-slate-700 shadow-sm text-cyan-500'
							: 'text-slate-400'}"
					>
						<svg
							class="w-3.5 h-3.5"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
							viewBox="0 0 16 16"
						>
							<line x1="3" y1="4" x2="13" y2="4" /><line x1="3" y1="8" x2="13" y2="8" /><line
								x1="3"
								y1="12"
								x2="13"
								y2="12"
							/>
						</svg>
					</span>
				</div>

				<!-- Refresh -->
				<button
					type="button"
					class="h-8 w-8 flex items-center justify-center rounded-full border border-slate-200 dark:border-slate-700 bg-slate-100/80 dark:bg-slate-800/80 text-slate-500 dark:text-slate-400 hover:text-cyan-500 dark:hover:text-cyan-400 hover:border-cyan-300 dark:hover:border-cyan-700 transition-all disabled:opacity-40"
					on:click={fetchMonitors}
					disabled={loading}
					title="Rafraîchir"
				>
					<svg
						class="w-3.5 h-3.5 {loading ? 'animate-spin' : ''}"
						fill="none"
						stroke="currentColor"
						stroke-width="2.5"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
						/>
					</svg>
				</button>

				<!-- Separator -->
				<div class="h-5 w-px bg-slate-200 dark:bg-slate-700 mx-1"></div>

				<!-- Admin badge -->
				{#if isAdmin}
					<button
						type="button"
						class="flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-semibold
							   bg-amber-500 hover:bg-amber-400 text-white
							   shadow-[0_0_20px_rgba(251,191,36,0.4)] hover:shadow-[0_0_28px_rgba(251,191,36,0.6)]
							   transition-all"
						on:click={() => goto('/admin')}
					>
						<svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
							<path
								fill-rule="evenodd"
								d="M18 8a6 6 0 01-7.743 5.743L10 14l-1 1-1 1H6v2H2v-4l4.257-4.257A6 6 0 1118 8zm-6-4a1 1 0 100 2 2 2 0 012 2 1 1 0 102 0 4 4 0 00-4-4z"
								clip-rule="evenodd"
							/>
						</svg>
						Admin
					</button>
				{/if}

				<!-- Add button -->
				<button
					type="button"
					class="flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-semibold
						   bg-cyan-500 hover:bg-cyan-400 text-white
						   shadow-[0_0_20px_rgba(34,211,238,0.4)] hover:shadow-[0_0_28px_rgba(34,211,238,0.6)]
						   transition-all"
					on:click={openAdd}
				>
					<svg
						class="w-3.5 h-3.5"
						fill="none"
						stroke="currentColor"
						stroke-width="3"
						viewBox="0 0 24 24"
					>
						<path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
					</svg>
					Ajouter
				</button>

				<!-- Separator -->
				<div class="h-5 w-px bg-slate-200 dark:bg-slate-700 mx-1"></div>

				<!-- Profile -->
				<button
					type="button"
					class="flex items-center gap-2 pl-1 pr-3 py-1 rounded-full border border-slate-200 dark:border-slate-700 bg-white/70 dark:bg-slate-800/70 hover:border-cyan-300 dark:hover:border-cyan-700 transition-all"
					on:click={openProfile}
				>
					<span
						class="inline-flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-cyan-400 to-cyan-600 text-white text-xs font-bold shadow"
					>
						{authState?.user?.email?.[0]?.toUpperCase() ?? '?'}
					</span>
					<span class="text-xs text-slate-600 dark:text-slate-300 max-w-[120px] truncate">
						{authState?.user?.email ?? 'Profil'}
					</span>
				</button>

				<!-- Logout -->
				<button
					type="button"
					class="h-8 w-8 flex items-center justify-center rounded-full border border-slate-200 dark:border-slate-700 bg-slate-100/80 dark:bg-slate-800/80 text-slate-400 hover:text-rose-500 hover:border-rose-300 dark:hover:border-rose-700 transition-all"
					on:click={logout}
					title="Déconnexion"
				>
					<svg
						class="w-3.5 h-3.5"
						fill="none"
						stroke="currentColor"
						stroke-width="2.5"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
						/>
					</svg>
				</button>
			</div>
		</div>

		{#if error}
			<div
				class="mx-8 mt-4 flex items-start gap-2 text-sm text-rose-600 bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 rounded-xl px-4 py-3"
			>
				<svg
					class="w-4 h-4 shrink-0 mt-0.5"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
					viewBox="0 0 24 24"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
					/>
				</svg>
				{error}
			</div>
		{/if}

		{#if !loading && $monitors.length === 0}
			<div class="flex flex-col items-center justify-center gap-5 py-20 px-8 text-center">
				<div
					class="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-cyan-50 dark:bg-cyan-900/20 border border-cyan-100 dark:border-cyan-800"
				>
					<svg
						class="w-8 h-8 text-cyan-400"
						fill="none"
						stroke="currentColor"
						stroke-width="1.5"
						viewBox="0 0 24 24"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M9 17.25v1.007a3 3 0 01-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0115 18.257V17.25m6-12V15a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 15V5.25m18 0A2.25 2.25 0 0018.75 3H5.25A2.25 2.25 0 003 5.25m18 0H3"
						/>
					</svg>
				</div>
				<div class="flex flex-col gap-1">
					<p class="text-base font-semibold text-slate-800 dark:text-slate-100">
						Aucun moniteur pour l'instant
					</p>
					<p class="text-sm text-slate-400 dark:text-slate-500 max-w-xs">
						Ajoutez votre premier site ou service à surveiller pour commencer.
					</p>
				</div>
				<button
					type="button"
					class="flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-semibold
						   bg-cyan-500 hover:bg-cyan-400 text-white
						   shadow-[0_0_24px_rgba(34,211,238,0.45)] hover:shadow-[0_0_32px_rgba(34,211,238,0.65)]
						   transition-all"
					on:click={openAdd}
				>
					<svg
						class="w-4 h-4"
						fill="none"
						stroke="currentColor"
						stroke-width="3"
						viewBox="0 0 24 24"
					>
						<path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
					</svg>
					Ajouter un moniteur
				</button>
			</div>
		{:else}
			<div
				class={viewMode === 'grid'
					? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 p-8 items-start'
					: 'flex flex-col gap-4 p-8'}
			>
				{#each $monitors as m (m.id)}
					<MonitorCard
						{...m}
						showDetails={openCardId === m.id}
						onToggleDetails={() => toggleCardDetails(m.id)}
						onDeleted={fetchMonitors}
						compact={viewMode === 'list'}
					/>
				{/each}
			</div>
		{/if}
	</div>
</div>

{#if openCardId !== null}
	{@const selectedMonitor = $monitors.find((m) => m.id === openCardId)}
	{#if selectedMonitor}
		<MonitorDetailModal
			monitor={selectedMonitor}
			onClose={() => (openCardId = null)}
			onDeleted={fetchMonitors}
		/>
	{/if}
{/if}

{#if showAdd}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center backdrop-blur-md bg-black/40"
		on:click={() => (showAdd = false)}
		role="presentation"
	>
		<div
			class="w-full max-w-sm mx-4 rounded-2xl bg-white dark:bg-slate-900
                   border border-slate-200 dark:border-slate-700
                   shadow-[0_0_60px_rgba(56,189,248,0.25)] p-6 flex flex-col gap-5"
			on:click|stopPropagation
			role="dialog"
			aria-modal="true"
		>
			<div class="flex items-center justify-between">
				<h2 class="font-semibold text-slate-900 dark:text-slate-50">Ajouter un monitor</h2>
				<button
					type="button"
					class="h-7 w-7 flex items-center justify-center rounded-full text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
					on:click={() => (showAdd = false)}
				>
					<svg
						class="w-4 h-4"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						viewBox="0 0 24 24"
					>
						<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			</div>

			<form class="flex flex-col gap-3" on:submit|preventDefault={submitAdd}>
				<label class="flex flex-col gap-1">
					<span class="text-xs text-slate-500 dark:text-slate-400">Nom</span>
					<input
						class="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500"
						bind:value={addName}
						placeholder="Ex: Backend API"
						required
					/>
				</label>
				<label class="flex flex-col gap-1">
					<span class="text-xs text-slate-500 dark:text-slate-400">URL</span>
					<input
						class="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500"
						bind:value={addUrl}
						placeholder="https://example.com/health"
						required
					/>
				</label>
				<div class="grid grid-cols-2 gap-3">
					<label class="flex flex-col gap-1">
						<span class="text-xs text-slate-500 dark:text-slate-400">Type</span>
						<select
							class="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500"
							bind:value={addType}
						>
							<option value="http">HTTP</option>
							<option value="ping">Ping</option>
							<option value="port">Port</option>
						</select>
					</label>
					<label class="flex flex-col gap-1">
						<span class="text-xs text-slate-500 dark:text-slate-400">Code HTTP attendu</span>
						<input
							type="number"
							min="100"
							max="599"
							class="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500"
							bind:value={addExpectedStatusCode}
						/>
					</label>
				</div>

				{#if addError}
					<p
						class="text-xs text-rose-500 bg-rose-50 dark:bg-rose-900/20 border border-rose-200 dark:border-rose-800 rounded-lg px-3 py-2"
					>
						{addError}
					</p>
				{/if}

				<div class="flex gap-2 justify-end pt-1">
					<button type="button" class="btn btn-sm btn-secondary" on:click={() => (showAdd = false)}>
						Annuler
					</button>
					<button
						type="submit"
						class="btn btn-sm btn-primary disabled:opacity-50"
						disabled={addSubmitting}
					>
						{addSubmitting ? 'Ajout...' : 'Ajouter'}
					</button>
				</div>
			</form>
		</div>
	</div>
{/if}

{#if showProfile}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center backdrop-blur-md bg-black/40 px-4"
		on:click={() => (showProfile = false)}
		role="presentation"
	>
		<div
			class="w-full max-w-sm rounded-2xl overflow-hidden
                   bg-white dark:bg-slate-900
                   border border-slate-200 dark:border-slate-700
                   shadow-[0_0_60px_rgba(56,189,248,0.25)]"
			on:click|stopPropagation
			role="dialog"
			aria-modal="true"
		>
			<!-- Body -->
			<div class="px-5 pb-5 pt-5 flex flex-col gap-3 max-h-[80vh] overflow-y-auto">
				<div class="flex items-center justify-between mb-1">
					<h2 class="text-sm font-semibold text-slate-800 dark:text-slate-100">Mon profil</h2>
					<button
						type="button"
						class="h-7 w-7 flex items-center justify-center rounded-full text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
						on:click={() => (showProfile = false)}
					>
						<svg
							class="w-4 h-4"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
							viewBox="0 0 24 24"
						>
							<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				</div>

				<!-- Changer l'adresse email -->
				<form
					class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm p-4 flex flex-col gap-3"
					on:submit|preventDefault={submitEmailChange}
				>
					<p
						class="text-[10px] font-semibold uppercase tracking-widest text-slate-400 dark:text-slate-500"
					>
						Adresse email
					</p>

					<label class="flex flex-col gap-1">
						<span class="text-xs text-slate-500 dark:text-slate-400">Email actuel</span>
						<input
							type="email"
							class="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-slate-900/60 px-3 py-2 text-sm text-slate-500 dark:text-slate-400 cursor-not-allowed"
							value={authState?.user?.email ?? ''}
							disabled
						/>
					</label>

					<label class="flex flex-col gap-1">
						<span class="text-xs text-slate-500 dark:text-slate-400">Nouvelle adresse email</span>
						<input
							type="email"
							class="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500"
							bind:value={profileNewEmail}
							placeholder="nouvelle@adresse.com"
							required
						/>
					</label>

					{#if profileEmailError}
						<div
							class="flex items-start gap-2 text-xs text-rose-600 bg-rose-50 dark:bg-rose-900/20 border border-rose-200 dark:border-rose-800 rounded-lg px-3 py-2"
						>
							<svg
								class="w-3.5 h-3.5 shrink-0 mt-0.5"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
								/>
							</svg>
							{profileEmailError}
						</div>
					{/if}
					{#if profileEmailSuccess}
						<div
							class="flex items-center gap-2 text-xs text-emerald-600 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-lg px-3 py-2"
						>
							<svg
								class="w-3.5 h-3.5 shrink-0"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
								viewBox="0 0 24 24"
							>
								<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
							</svg>
							{profileEmailSuccess}
						</div>
					{/if}

					<div class="flex justify-end pt-1">
						<button
							type="submit"
							class="btn btn-sm btn-primary disabled:opacity-50"
							disabled={profileEmailSubmitting || !profileNewEmail}
						>
							{profileEmailSubmitting ? 'Envoi...' : 'Envoyer le lien de confirmation'}
						</button>
					</div>
				</form>

				<!-- Changer le mot de passe -->
				<form
					class="rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm p-4 flex flex-col gap-3"
					on:submit|preventDefault={savePassword}
				>
					<p
						class="text-[10px] font-semibold uppercase tracking-widest text-slate-400 dark:text-slate-500"
					>
						Mot de passe
					</p>

					<div class="flex flex-col gap-1">
						<label class="flex flex-col gap-1">
							<span class="text-xs text-slate-500 dark:text-slate-400">Nouveau mot de passe</span>
							<input
								type="password"
								class="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500"
								bind:value={profilePassword}
								placeholder="Nouveau mot de passe"
							/>
						</label>
						<PasswordStrength password={profilePassword} bind:valid={profilePasswordValid} />
					</div>

					<div class="flex flex-col gap-1">
						<label class="flex flex-col gap-1">
							<span class="text-xs text-slate-500 dark:text-slate-400"
								>Confirmer le mot de passe</span
							>
							<input
								type="password"
								class="rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500
									{profileConfirmPassword && !profilePasswordsMatch ? 'border-rose-400 ring-2 ring-rose-200' : ''}"
								bind:value={profileConfirmPassword}
								placeholder="Répétez le mot de passe"
							/>
						</label>
						{#if profileConfirmPassword && !profilePasswordsMatch}
							<p class="text-xs text-rose-500">Les mots de passe ne correspondent pas.</p>
						{:else if profileConfirmPassword && profilePasswordsMatch}
							<p class="text-xs text-emerald-600">Les mots de passe correspondent.</p>
						{/if}
					</div>

					{#if profilePasswordError}
						<div
							class="flex items-start gap-2 text-xs text-rose-600 bg-rose-50 dark:bg-rose-900/20 border border-rose-200 dark:border-rose-800 rounded-lg px-3 py-2"
						>
							<svg
								class="w-3.5 h-3.5 shrink-0 mt-0.5"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
								/>
							</svg>
							{profilePasswordError}
						</div>
					{/if}
					{#if profilePasswordSuccess}
						<div
							class="flex items-center gap-2 text-xs text-emerald-600 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-lg px-3 py-2"
						>
							<svg
								class="w-3.5 h-3.5 shrink-0"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
								viewBox="0 0 24 24"
							>
								<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
							</svg>
							{profilePasswordSuccess}
						</div>
					{/if}

					<div class="flex justify-end pt-1">
						<button
							type="submit"
							class="btn btn-sm btn-primary disabled:opacity-50"
							disabled={!profileCanSavePassword}
						>
							{profilePasswordSubmitting ? 'Enregistrement...' : 'Mettre à jour'}
						</button>
					</div>
				</form>

				<!-- Zone de danger -->
				<div
					class="rounded-xl border border-rose-200 dark:border-rose-900/60 bg-rose-50/60 dark:bg-rose-950/30 p-4 flex flex-col gap-2"
				>
					<p class="text-[10px] font-semibold uppercase tracking-widest text-rose-400">
						Zone de danger
					</p>
					{#if !profileConfirmDelete}
						<button
							type="button"
							class="flex items-center gap-2 text-sm text-rose-500 hover:text-rose-600 dark:hover:text-rose-400 transition-colors text-left"
							on:click={() => (profileConfirmDelete = true)}
						>
							<svg
								class="w-4 h-4 shrink-0"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
								viewBox="0 0 24 24"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
								/>
							</svg>
							Supprimer mon compte
						</button>
					{:else}
						<p class="text-xs text-rose-500 mb-2">
							Tous tes moniteurs seront supprimés. Cette action est irréversible.
						</p>
						<label class="flex flex-col gap-1">
							<span class="text-xs text-rose-400"
								>Tape <strong>supprimer</strong> pour confirmer</span
							>
							<input
								type="text"
								class="rounded-lg border border-rose-300 bg-white dark:bg-slate-900 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-rose-400"
								bind:value={profileDeleteConfirmText}
								placeholder="supprimer"
								disabled={profileDeleting}
							/>
						</label>
						<div class="flex gap-2 justify-end mt-1">
							<button
								type="button"
								class="btn btn-sm btn-secondary"
								on:click={() => {
									profileConfirmDelete = false;
									profileDeleteConfirmText = '';
								}}
								disabled={profileDeleting}
							>
								Annuler
							</button>
							<button
								type="button"
								class="btn btn-sm bg-rose-500 hover:bg-rose-600 text-white border-transparent disabled:opacity-50"
								on:click={deleteAccount}
								disabled={profileDeleting || profileDeleteConfirmText !== 'supprimer'}
							>
								{profileDeleting ? 'Suppression...' : 'Supprimer'}
							</button>
						</div>
					{/if}
				</div>
			</div>
		</div>
	</div>
{/if}
