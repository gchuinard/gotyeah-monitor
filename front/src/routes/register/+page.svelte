<script lang="ts">
	import { goto } from '$app/navigation';
	import { parseApiError, parseNetworkError } from '$lib/utils/errors';

	const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

	let email = '';
	let password = '';
	let submitting = false;
	let error: string | null = null;
	let success = false;

	async function onSubmit() {
		submitting = true;
		error = null;
		try {
			const res = await fetch(`${API_URL}/auth/register`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ email, password })
			});

			if (!res.ok) {
				error = await parseApiError(res, 'register');
				return;
			}

			success = true;
		} catch (e) {
			error = parseNetworkError(e, 'register');
		} finally {
			submitting = false;
		}
	}
</script>

<div class="min-h-screen flex items-center justify-center py-10">
	<div
		class="w-full max-w-md mx-auto p-8
           rounded-3xl bg-white/85 dark:bg-slate-900/80 backdrop-blur-xl
           border border-white/70 dark:border-slate-800 shadow-soft-lg"
	>
		<div class="flex flex-col gap-1 mb-6">
			<div class="eyebrow">GotYeah Monitor</div>
			<h1 class="text-2xl font-semibold text-slate-900 dark:text-slate-100">Créer un compte</h1>
		</div>

		<form class="flex flex-col gap-4" on:submit|preventDefault={onSubmit}>
			<label class="flex flex-col gap-1">
				<span class="text-sm text-slate-600 dark:text-slate-300">Email</span>
				<input type="email" class="field" bind:value={email} required />
			</label>

			<label class="flex flex-col gap-1">
				<span class="text-sm text-slate-600 dark:text-slate-300">Mot de passe</span>
				<input type="password" class="field" bind:value={password} required />
			</label>

			{#if error}
				<div
					class="flex items-start gap-2 rounded-xl px-3 py-2 text-sm text-rose-600 bg-rose-50 border border-rose-200 dark:text-rose-300 dark:bg-rose-500/10 dark:border-rose-500/30"
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

			{#if success}
				<div
					class="flex items-center gap-2 rounded-xl px-3 py-2 text-sm text-emerald-600 bg-emerald-50 border border-emerald-200 dark:text-emerald-300 dark:bg-emerald-500/10 dark:border-emerald-500/30"
				>
					<svg
						class="w-4 h-4 shrink-0"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						viewBox="0 0 24 24"
					>
						<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
					</svg>
					Compte créé ! Vérifiez votre email pour activer votre compte.
				</div>
			{/if}

			<button
				type="submit"
				class="btn btn-md btn-primary mt-2 disabled:opacity-50 disabled:cursor-not-allowed"
				disabled={submitting || success}
			>
				{submitting ? 'Création...' : 'Créer le compte'}
			</button>
		</form>

		<div class="mt-4 text-xs text-slate-500 dark:text-slate-400">
			Déjà un compte ?
			<button
				type="button"
				class="text-cyan-600 hover:text-cyan-500 dark:text-cyan-400 dark:hover:text-cyan-300 underline"
				on:click={() => goto('/login')}
			>
				Se connecter
			</button>
		</div>
	</div>
</div>
