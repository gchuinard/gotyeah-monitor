<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { get } from 'svelte/store';
	import { apiFetch } from '$lib/utils/api';
	import { activeTeamId, loadTeams } from '$lib/stores/teams';

	let name = '';
	let url = '';
	let type = 'http';
	let expectedStatusCode = 200;
	let environment = '';

	let submitting = false;
	let error: string | null = null;

	onMount(loadTeams);

	async function onSubmit() {
		const teamId = get(activeTeamId);
		if (teamId == null) {
			error = 'Aucune équipe active. Crée une équipe depuis le tableau de bord.';
			return;
		}
		submitting = true;
		error = null;

		try {
			const res = await apiFetch('/monitors', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name,
					url,
					type,
					expected_status_code: expectedStatusCode,
					environment: environment.trim() || null,
					team_id: teamId
				})
			});

			if (!res.ok) {
				const text = await res.text().catch(() => '');
				throw new Error(text || `HTTP ${res.status}`);
			}

			await goto('/');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Erreur inconnue';
		} finally {
			submitting = false;
		}
	}
</script>

<div class="min-h-screen flex items-start justify-center pt-10 pb-12">
	<div
		class="w-full max-w-xl mx-auto
           rounded-3xl bg-white/80 dark:bg-slate-900/90 backdrop-blur-xl
           border border-white/70 dark:border-slate-800 shadow-soft-lg
           overflow-hidden"
	>
		<div
			class="flex items-center justify-between px-8 pt-7 pb-5 border-b border-slate-200/80 dark:border-slate-800"
		>
			<div class="flex flex-col gap-1">
				<div class="eyebrow">GotYeah Monitor</div>
				<h1 class="text-2xl font-semibold text-slate-900 dark:text-slate-50">Ajouter un monitor</h1>
			</div>
			<button type="button" class="btn btn-sm btn-secondary" on:click={() => goto('/')}>
				Retour
			</button>
		</div>

		<div class="px-6 pb-6 pt-5">
			<form
				class="rounded-2xl border border-slate-200/70 dark:border-slate-800/80
               bg-white/70 dark:bg-slate-950/70 backdrop-blur-xl shadow-soft
               flex flex-col gap-4 p-6"
				on:submit|preventDefault={onSubmit}
			>
				<label class="flex flex-col gap-1">
					<span class="text-sm text-slate-600 dark:text-slate-300">Nom</span>
					<input class="field" bind:value={name} placeholder="Ex: Backend API" required />
				</label>

				<label class="flex flex-col gap-1">
					<span class="text-sm text-slate-600 dark:text-slate-300">URL</span>
					<input class="field" bind:value={url} placeholder="https://example.com/health" required />
					<span class="text-xs text-slate-400 dark:text-slate-500"
						>Doit être une URL valide (http/https).</span
					>
				</label>

				<label class="flex flex-col gap-1">
					<span class="text-sm text-slate-600 dark:text-slate-300">Type</span>
					<select class="field" bind:value={type}>
						<option value="http">HTTP</option>
						<option value="ping">Ping</option>
						<option value="port">Port</option>
					</select>
				</label>

				<label class="flex flex-col gap-1">
					<span class="text-sm text-slate-600 dark:text-slate-300">Code HTTP attendu</span>
					<input
						type="number"
						min="100"
						max="599"
						class="field tabular-nums"
						bind:value={expectedStatusCode}
					/>
					<span class="text-xs text-slate-400 dark:text-slate-500">Par défaut 200 (OK).</span>
				</label>

				<label class="flex flex-col gap-1">
					<span class="text-sm text-slate-600 dark:text-slate-300">Environnement</span>
					<input
						class="field"
						list="env-presets-addpage"
						bind:value={environment}
						placeholder="prod, staging, dev… (optionnel)"
					/>
					<datalist id="env-presets-addpage">
						<option value="prod"></option>
						<option value="staging"></option>
						<option value="dev"></option>
					</datalist>
				</label>

				{#if error}
					<div
						class="text-sm text-rose-600 bg-rose-50/90 dark:bg-rose-900/30 border border-rose-200/80 dark:border-rose-500/40 rounded-xl px-3 py-2"
					>
						{error}
					</div>
				{/if}

				<button
					type="submit"
					class="btn btn-md btn-primary mt-2 self-end disabled:opacity-50 disabled:cursor-not-allowed"
					disabled={submitting}
				>
					{submitting ? 'Ajout...' : 'Ajouter'}
				</button>
			</form>
		</div>
	</div>
</div>
