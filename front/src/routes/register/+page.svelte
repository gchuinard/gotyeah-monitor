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
           rounded-3xl bg-white/85 backdrop-blur-2xl
           border border-white/70 shadow-[0_0_60px_rgba(56,189,248,0.3)]"
	>
		<div class="flex flex-col gap-1 mb-6">
			<div class="text-xs uppercase tracking-[0.25em] text-slate-400">GotYeah Monitor</div>
			<h1 class="text-2xl font-semibold text-slate-900">Créer un compte</h1>
		</div>

		<form class="flex flex-col gap-4" on:submit|preventDefault={onSubmit}>
			<label class="flex flex-col gap-1">
				<span class="text-sm text-slate-600">Email</span>
				<input
					type="email"
					class="px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 focus:outline-none focus:ring-2 focus:ring-cyan-400/60"
					bind:value={email}
					required
				/>
			</label>

			<label class="flex flex-col gap-1">
				<span class="text-sm text-slate-600">Mot de passe</span>
				<input
					type="password"
					class="px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 focus:outline-none focus:ring-2 focus:ring-cyan-400/60"
					bind:value={password}
					required
				/>
			</label>

			{#if error}
				<div class="flex items-start gap-2 text-sm text-rose-600 bg-rose-50 border border-rose-200 rounded-xl px-3 py-2">
					<svg class="w-4 h-4 shrink-0 mt-0.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
					</svg>
					{error}
				</div>
			{/if}

			{#if success}
				<div class="flex items-center gap-2 text-sm text-emerald-600 bg-emerald-50 border border-emerald-200 rounded-xl px-3 py-2">
					<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
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

		<div class="mt-4 text-xs text-slate-500">
			Déjà un compte ?
			<button type="button" class="text-cyan-600 hover:text-cyan-500 underline" on:click={() => goto('/login')}>
				Se connecter
			</button>
		</div>
	</div>
</div>
