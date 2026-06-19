<script lang="ts">
	import { goto } from '$app/navigation';
	import { parseApiError, parseNetworkError } from '$lib/utils/errors';
	import { getUrlToken } from '$lib/utils/token';
	import PasswordStrength from '$lib/components/PasswordStrength.svelte';
	import { onMount } from 'svelte';

	const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

	let token = '';
	let newPassword = '';
	let confirmPassword = '';
	let passwordValid = false;
	let submitting = false;
	let error: string | null = null;
	let success = false;
	let invalidLink = false;

	$: passwordsMatch = confirmPassword === '' || newPassword === confirmPassword;
	$: canSubmit = passwordValid && newPassword === confirmPassword && confirmPassword !== '';

	onMount(() => {
		token = getUrlToken();
		if (!token) invalidLink = true;
	});

	/** Réinitialise le mot de passe via le token du lien (POST /auth/reset-password) puis redirige vers /login après 2 s. */
	async function onSubmit() {
		if (!canSubmit) return;
		submitting = true;
		error = null;
		try {
			const res = await fetch(`${API_URL}/auth/reset-password`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ token, new_password: newPassword })
			});

			if (!res.ok) {
				error = await parseApiError(res, 'reset-password');
				return;
			}

			success = true;
			setTimeout(() => goto('/login'), 2000);
		} catch (e) {
			error = parseNetworkError(e, 'reset-password');
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
			<h1 class="text-2xl font-semibold text-slate-900 dark:text-slate-100">
				Nouveau mot de passe
			</h1>
		</div>

		{#if invalidLink}
			<div
				class="flex items-start gap-2 rounded-xl px-3 py-2 mb-4 text-sm text-rose-600 bg-rose-50 border border-rose-200 dark:text-rose-300 dark:bg-rose-500/10 dark:border-rose-500/30"
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
				Lien invalide.
			</div>
			<button
				type="button"
				class="btn btn-md btn-primary w-full"
				on:click={() => goto('/forgot-password')}
			>
				Demander un nouveau lien
			</button>
		{:else if success}
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
				Mot de passe mis à jour ! Redirection vers la connexion…
			</div>
		{:else}
			<form class="flex flex-col gap-4" on:submit|preventDefault={onSubmit}>
				<div class="flex flex-col gap-1">
					<label class="flex flex-col gap-1">
						<span class="text-sm text-slate-600 dark:text-slate-300">Nouveau mot de passe</span>
						<input type="password" class="field" bind:value={newPassword} required />
					</label>
					<PasswordStrength password={newPassword} bind:valid={passwordValid} />
				</div>

				<div class="flex flex-col gap-1">
					<label class="flex flex-col gap-1">
						<span class="text-sm text-slate-600 dark:text-slate-300">Confirmer le mot de passe</span
						>
						<input
							type="password"
							class="field {confirmPassword && !passwordsMatch
								? 'border-rose-400 ring-2 ring-rose-200 dark:border-rose-500/60 dark:ring-rose-500/20'
								: ''}"
							bind:value={confirmPassword}
							required
						/>
					</label>
					{#if confirmPassword && !passwordsMatch}
						<p class="text-xs text-rose-500 dark:text-rose-400">
							Les mots de passe ne correspondent pas.
						</p>
					{:else if confirmPassword && passwordsMatch}
						<p class="text-xs text-emerald-600 dark:text-emerald-400">
							Les mots de passe correspondent.
						</p>
					{/if}
				</div>

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

				<button
					type="submit"
					class="btn btn-md btn-primary mt-2 disabled:opacity-50 disabled:cursor-not-allowed"
					disabled={submitting || !canSubmit}
				>
					{submitting ? 'Mise à jour...' : 'Mettre à jour le mot de passe'}
				</button>
			</form>
		{/if}
	</div>
</div>
