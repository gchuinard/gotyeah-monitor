<script lang="ts">
	import { auth, clearAuth } from '$lib/stores/auth';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';

	const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

	type Monitor = {
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

	type UserWithMonitors = {
		id: number;
		email: string;
		created_at: string;
		monitors: Monitor[];
	};

	let users: UserWithMonitors[] = [];
	let loading = true;
	let error: string | null = null;
	let expandedUserId: number | null = null;

	type ConfirmModal =
		| { kind: 'monitor'; monitorId: number; monitorName: string; userEmail: string }
		| { kind: 'user'; userId: number; userEmail: string };

	let confirmModal: ConfirmModal | null = null;

	type EditModal = {
		monitorId: number;
		name: string;
		url: string;
		type: string;
		expected_status_code: number;
		userId: number;
	};

	let editModal: EditModal | null = null;
	let editSaving = false;
	let editError: string | null = null;

	async function fetchUsers() {
		loading = true;
		error = null;
		const token = $auth.token;
		if (!token) {
			await goto('/login');
			return;
		}
		try {
			const res = await fetch(`${API_URL}/admin/users`, {
				headers: { Authorization: `Bearer ${token}` }
			});
			if (res.status === 403) {
				error = 'Accès refusé. Vous n\'êtes pas administrateur.';
				return;
			}
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			users = await res.json();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Erreur inconnue';
		} finally {
			loading = false;
		}
	}

	function toggleUser(userId: number) {
		expandedUserId = expandedUserId === userId ? null : userId;
	}

	function askDelete(monitor: Monitor, userEmail: string) {
		confirmModal = { kind: 'monitor', monitorId: monitor.id, monitorName: monitor.name, userEmail };
	}

	function askDeleteUser(user: UserWithMonitors) {
		confirmModal = { kind: 'user', userId: user.id, userEmail: user.email };
	}

	function openEdit(monitor: Monitor, userId: number) {
		editModal = {
			monitorId: monitor.id,
			name: monitor.name,
			url: monitor.url,
			type: monitor.type,
			expected_status_code: monitor.expected_status_code,
			userId
		};
		editError = null;
	}

	async function saveEdit() {
		if (!editModal) return;
		editSaving = true;
		editError = null;
		const token = $auth.token;
		try {
			const res = await fetch(`${API_URL}/admin/monitors/${editModal.monitorId}`, {
				method: 'PUT',
				headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: editModal.name,
					url: editModal.url,
					type: editModal.type,
					expected_status_code: editModal.expected_status_code
				})
			});
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			const updated = await res.json();
			users = users.map((u) => ({
				...u,
				monitors: u.monitors.map((m) => (m.id === updated.id ? { ...m, ...updated } : m))
			}));
			editModal = null;
		} catch (err) {
			editError = err instanceof Error ? err.message : 'Erreur inconnue';
		} finally {
			editSaving = false;
		}
	}

	async function confirmDelete() {
		if (!confirmModal) return;
		const token = $auth.token;
		const modal = confirmModal;
		confirmModal = null;

		if (modal.kind === 'monitor') {
			const res = await fetch(`${API_URL}/admin/monitors/${modal.monitorId}`, {
				method: 'DELETE',
				headers: { Authorization: `Bearer ${token}` }
			});
			if (res.ok) {
				users = users.map((u) => ({
					...u,
					monitors: u.monitors.filter((m) => m.id !== modal.monitorId)
				}));
			}
		} else {
			const res = await fetch(`${API_URL}/admin/users/${modal.userId}`, {
				method: 'DELETE',
				headers: { Authorization: `Bearer ${token}` }
			});
			if (res.ok) {
				users = users.filter((u) => u.id !== modal.userId);
			}
		}
	}

	function statusColor(status: string) {
		if (status === 'up') return 'text-emerald-400';
		if (status === 'down') return 'text-rose-400';
		return 'text-slate-400';
	}

	function statusDot(status: string) {
		if (status === 'up') return 'bg-emerald-400';
		if (status === 'down') return 'bg-rose-400';
		return 'bg-slate-400';
	}

	onMount(fetchUsers);
</script>

<div class="min-h-screen flex items-start justify-center pt-10 pb-12">
	<div
		class="w-full max-w-5xl mx-auto
           rounded-3xl bg-white/80 dark:bg-slate-900/90 backdrop-blur-2xl
           border border-white/70 dark:border-slate-800 shadow-[0_0_60px_rgba(56,189,248,0.28)]
           overflow-hidden"
	>
		<!-- Header -->
		<div
			class="flex items-center justify-between px-8 pt-7 pb-4 border-b border-slate-200/80 dark:border-slate-800"
		>
			<div class="flex flex-col gap-1">
				<div class="text-xs uppercase tracking-[0.25em] text-slate-400 dark:text-slate-500">
					GotYeah Monitor
				</div>
				<div class="text-2xl font-semibold text-slate-900 dark:text-slate-50">
					Back Office — Utilisateurs
				</div>
			</div>
			<div class="flex items-center gap-3">
				<button
					type="button"
					class="btn btn-sm btn-secondary"
					on:click={() => goto('/')}
				>
					← Dashboard
				</button>
				<button
					type="button"
					class="btn btn-sm btn-secondary disabled:opacity-50"
					on:click={fetchUsers}
					disabled={loading}
				>
					{loading ? 'Chargement...' : 'Rafraîchir'}
				</button>
			</div>
		</div>

		<!-- Stats bar -->
		{#if !loading && !error}
			<div class="flex gap-6 px-8 py-4 border-b border-slate-200/60 dark:border-slate-800/60 text-sm text-slate-500 dark:text-slate-400">
				<span><strong class="text-slate-900 dark:text-slate-50">{users.length}</strong> utilisateurs</span>
				<span><strong class="text-slate-900 dark:text-slate-50">{users.reduce((acc, u) => acc + u.monitors.length, 0)}</strong> moniteurs total</span>
				<span><strong class="text-emerald-400">{users.reduce((acc, u) => acc + u.monitors.filter(m => m.status === 'up').length, 0)}</strong> up</span>
				<span><strong class="text-rose-400">{users.reduce((acc, u) => acc + u.monitors.filter(m => m.status === 'down').length, 0)}</strong> down</span>
			</div>
		{/if}

		<!-- Content -->
		<div class="p-8">
			{#if loading}
				<div class="text-center text-slate-400 py-16">Chargement...</div>
			{:else if error}
				<div class="text-center text-rose-500 py-16">{error}</div>
			{:else if users.length === 0}
				<div class="text-center text-slate-400 py-16">Aucun utilisateur trouvé.</div>
			{:else}
				<div class="flex flex-col gap-3">
					{#each users as user (user.id)}
						<div
							class="rounded-2xl border border-slate-200/70 dark:border-slate-700/70
                             bg-white/60 dark:bg-slate-800/60 overflow-hidden"
						>
							<!-- User row -->
							<div
								class="w-full flex items-center justify-between px-6 py-4 text-left hover:bg-slate-50/80 dark:hover:bg-slate-700/40 transition-colors cursor-pointer"
								on:click={() => toggleUser(user.id)}
								role="button"
								tabindex="0"
								on:keydown={(e) => e.key === 'Enter' && toggleUser(user.id)}
							>
								<div class="flex items-center gap-4">
									<span
										class="inline-flex h-9 w-9 items-center justify-center rounded-full bg-cyan-500 text-white font-semibold text-sm"
									>
										{user.email[0].toUpperCase()}
									</span>
									<div class="flex flex-col">
										<span class="font-medium text-slate-900 dark:text-slate-100">{user.email}</span>
										<span class="text-xs text-slate-400">
											Inscrit le {new Date(user.created_at).toLocaleDateString('fr-FR')}
											· ID #{user.id}
										</span>
									</div>
								</div>
								<div class="flex items-center gap-4">
									<div class="flex items-center gap-2 text-sm">
										<span class="text-slate-500 dark:text-slate-400">
											{user.monitors.length} moniteur{user.monitors.length !== 1 ? 's' : ''}
										</span>
										{#if user.monitors.some(m => m.status === 'down')}
											<span class="inline-block h-2 w-2 rounded-full bg-rose-400"></span>
										{:else if user.monitors.some(m => m.status === 'up')}
											<span class="inline-block h-2 w-2 rounded-full bg-emerald-400"></span>
										{/if}
									</div>
									<button
										type="button"
										class="text-xs text-rose-400 hover:text-rose-600 transition-colors px-2 py-1 rounded"
										on:click|stopPropagation={() => askDeleteUser(user)}
									>
										Supprimer le compte
									</button>
									<svg
										class="w-4 h-4 text-slate-400 transition-transform {expandedUserId === user.id ? 'rotate-180' : ''}"
										fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"
									>
										<path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
									</svg>
								</div>
							</div>

							<!-- Monitors list -->
							{#if expandedUserId === user.id}
								<div class="border-t border-slate-200/60 dark:border-slate-700/60">
									{#if user.monitors.length === 0}
										<div class="px-6 py-4 text-sm text-slate-400">Aucun moniteur.</div>
									{:else}
										<table class="w-full text-sm">
											<thead>
												<tr class="text-xs uppercase tracking-wider text-slate-400 border-b border-slate-200/50 dark:border-slate-700/50">
													<th class="px-6 py-3 text-left">Nom</th>
													<th class="px-4 py-3 text-left">URL</th>
													<th class="px-4 py-3 text-left">Type</th>
													<th class="px-4 py-3 text-left">Statut</th>
													<th class="px-4 py-3 text-right">Latence</th>
													<th class="px-4 py-3 text-right">Dernier check</th>
													<th class="px-4 py-3"></th>
												</tr>
											</thead>
											<tbody>
												{#each user.monitors as monitor (monitor.id)}
													<tr
														class="border-b border-slate-100/60 dark:border-slate-700/30 last:border-0 hover:bg-slate-50/80 dark:hover:bg-slate-700/30 cursor-pointer"
														on:click={() => openEdit(monitor, user.id)}
													>
														<td class="px-6 py-3 font-medium text-slate-800 dark:text-slate-200">{monitor.name}</td>
														<td class="px-4 py-3 text-slate-500 dark:text-slate-400 max-w-[200px] truncate">
															<a href={monitor.url} target="_blank" rel="noopener noreferrer" class="hover:text-cyan-500 transition-colors">{monitor.url}</a>
														</td>
														<td class="px-4 py-3 text-slate-500 dark:text-slate-400 uppercase text-xs">{monitor.type}</td>
														<td class="px-4 py-3">
															<span class="inline-flex items-center gap-1.5 {statusColor(monitor.status)}">
																<span class="h-1.5 w-1.5 rounded-full {statusDot(monitor.status)}"></span>
																{monitor.status}
															</span>
														</td>
														<td class="px-4 py-3 text-right text-slate-500 dark:text-slate-400">
															{monitor.last_latency_ms !== null ? `${monitor.last_latency_ms} ms` : '—'}
														</td>
														<td class="px-4 py-3 text-right text-slate-400 text-xs">
															{monitor.last_checked_at
																? new Date(monitor.last_checked_at).toLocaleString('fr-FR')
																: '—'}
														</td>
													<td class="px-4 py-3 text-right">
														<button
															type="button"
															class="text-xs text-rose-400 hover:text-rose-600 transition-colors"
															on:click|stopPropagation={() => askDelete(monitor, user.email)}
														>
															Supprimer
														</button>
													</td>
													</tr>
												{/each}
											</tbody>
										</table>
									{/if}
								</div>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		</div>
	</div>
</div>

{#if editModal}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
		on:click={() => (editModal = null)}
		role="presentation"
	>
		<div
			class="w-full max-w-md mx-4 rounded-2xl bg-white dark:bg-slate-900
                   border border-slate-200 dark:border-slate-700
                   shadow-[0_0_40px_rgba(0,0,0,0.3)] p-6 flex flex-col gap-5"
			on:click|stopPropagation
			role="dialog"
			aria-modal="true"
		>
			<h3 class="text-base font-semibold text-slate-900 dark:text-slate-50">Modifier le moniteur</h3>

			<div class="flex flex-col gap-3">
				<label class="flex flex-col gap-1">
					<span class="text-xs text-slate-500 dark:text-slate-400">Nom</span>
					<input
						type="text"
						class="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500"
						bind:value={editModal.name}
					/>
				</label>
				<label class="flex flex-col gap-1">
					<span class="text-xs text-slate-500 dark:text-slate-400">URL</span>
					<input
						type="url"
						class="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500"
						bind:value={editModal.url}
					/>
				</label>
				<div class="flex gap-3">
					<label class="flex flex-col gap-1 flex-1">
						<span class="text-xs text-slate-500 dark:text-slate-400">Type</span>
						<select
							class="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500"
							bind:value={editModal.type}
						>
							<option value="http">HTTP</option>
							<option value="ping">Ping</option>
							<option value="port">Port</option>
						</select>
					</label>
					<label class="flex flex-col gap-1 w-32">
						<span class="text-xs text-slate-500 dark:text-slate-400">Code attendu</span>
						<input
							type="number"
							class="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500"
							bind:value={editModal.expected_status_code}
						/>
					</label>
				</div>
			</div>

			{#if editError}
				<p class="text-sm text-rose-500">{editError}</p>
			{/if}

			<div class="flex gap-3 justify-end">
				<button
					type="button"
					class="btn btn-sm btn-secondary"
					on:click={() => (editModal = null)}
				>
					Annuler
				</button>
				<button
					type="button"
					class="btn btn-sm btn-primary disabled:opacity-50"
					on:click={saveEdit}
					disabled={editSaving}
				>
					{editSaving ? 'Enregistrement...' : 'Enregistrer'}
				</button>
			</div>
		</div>
	</div>
{/if}

{#if confirmModal}
	<!-- Backdrop -->
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
		on:click={() => (confirmModal = null)}
		role="presentation"
	>
		<!-- Modal -->
		<div
			class="w-full max-w-sm mx-4 rounded-2xl bg-white dark:bg-slate-900
                   border border-slate-200 dark:border-slate-700
                   shadow-[0_0_40px_rgba(0,0,0,0.3)] p-6 flex flex-col gap-5"
			on:click|stopPropagation
			role="dialog"
			aria-modal="true"
		>
			<div class="flex flex-col gap-2">
				<div class="flex items-center gap-3">
					<span class="inline-flex h-10 w-10 items-center justify-center rounded-full bg-rose-100 dark:bg-rose-900/40">
						<svg class="w-5 h-5 text-rose-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
							<path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
						</svg>
					</span>
					<h3 class="text-base font-semibold text-slate-900 dark:text-slate-50">
						{confirmModal.kind === 'user' ? 'Supprimer le compte' : 'Supprimer le moniteur'}
					</h3>
				</div>
				<p class="text-sm text-slate-500 dark:text-slate-400">
					{#if confirmModal.kind === 'monitor'}
						Tu es sur le point de supprimer <span class="font-medium text-slate-700 dark:text-slate-200">"{confirmModal.monitorName}"</span> du compte <span class="font-medium text-slate-700 dark:text-slate-200">{confirmModal.userEmail}</span>.
					{:else}
						Tu es sur le point de supprimer le compte <span class="font-medium text-slate-700 dark:text-slate-200">{confirmModal.userEmail}</span> ainsi que tous ses moniteurs.
					{/if}
					Cette action est irréversible.
				</p>
			</div>
			<div class="flex gap-3 justify-end">
				<button
					type="button"
					class="btn btn-sm btn-secondary"
					on:click={() => (confirmModal = null)}
				>
					Annuler
				</button>
				<button
					type="button"
					class="btn btn-sm bg-rose-500 hover:bg-rose-600 text-white border-transparent"
					on:click={confirmDelete}
				>
					Supprimer
				</button>
			</div>
		</div>
	</div>
{/if}
