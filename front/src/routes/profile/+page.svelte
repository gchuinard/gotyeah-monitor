<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { auth, clearAuth, type AuthState } from '$lib/stores/auth';
	import { get } from 'svelte/store';
	import { apiFetch } from '$lib/utils/api';
	import { parseApiError, parseNetworkError } from '$lib/utils/errors';
	import PasswordStrength from '$lib/components/PasswordStrength.svelte';

	let state: AuthState = { token: null, user: null };
	let email = '';
	let newPassword = '';
	let confirmPassword = '';
	let passwordValid = false;
	let submitting = false;
	let error: string | null = null;
	let success: string | null = null;

	$: passwordsMatch = confirmPassword === '' || newPassword === confirmPassword;
	$: canSubmit =
		!submitting && (!newPassword || (passwordValid && newPassword === confirmPassword));

	onMount(() => {
		state = get(auth);
		email = state.user?.email ?? '';
		if (!state.token) {
			goto('/login');
		}
	});

	/** Met à jour le profil (PUT /auth/me) en n'envoyant que les champs modifiés (email et/ou mot de passe) puis rafraîchit le store auth. */
	async function onSubmit() {
		if (!canSubmit) return;
		submitting = true;
		error = null;
		success = null;

		try {
			const payload: { email?: string; password?: string } = {};
			if (email && email !== state.user?.email) {
				payload.email = email;
			}
			if (newPassword) {
				payload.password = newPassword;
			}

			// apiFetch ajoute le JWT et, sur 401, purge la session + redirige vers /login.
			const res = await apiFetch('/auth/me', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(payload)
			});

			if (!res.ok) {
				error = await parseApiError(res, 'profil');
				return;
			}

			const me = await res.json();
			state = { token: state.token, user: { id: me.id, email: me.email } };
			auth.set(state);
			success = 'Profil mis à jour.';
			newPassword = '';
			confirmPassword = '';
		} catch (e) {
			error = parseNetworkError(e, 'profil');
		} finally {
			submitting = false;
		}
	}

	function logout() {
		clearAuth();
		goto('/login');
	}
</script>

<div class="min-h-screen flex items-center justify-center py-10">
	<div
		class="w-full max-w-md mx-auto p-8
           rounded-3xl bg-white/85 dark:bg-slate-900/80 backdrop-blur-xl
           border border-white/70 dark:border-slate-800 shadow-soft-lg"
	>
		<div class="flex items-center justify-between mb-6">
			<div class="flex flex-col gap-1">
				<div class="eyebrow">GotYeah Monitor</div>
				<h1 class="text-2xl font-semibold text-slate-900 dark:text-slate-100">Profil</h1>
			</div>
			<div class="flex items-center gap-2">
				<button type="button" class="btn btn-sm btn-muted" on:click={() => goto('/')}>
					Accueil
				</button>
				<button type="button" class="btn btn-sm btn-muted" on:click={logout}> Déconnexion </button>
			</div>
		</div>

		<form class="flex flex-col gap-4" on:submit|preventDefault={onSubmit}>
			<label class="flex flex-col gap-1">
				<span class="text-sm text-slate-600 dark:text-slate-300">Email</span>
				<input type="email" class="field" bind:value={email} required />
			</label>

			<div class="flex flex-col gap-1">
				<label class="flex flex-col gap-1">
					<span class="text-sm text-slate-600 dark:text-slate-300">Nouveau mot de passe</span>
					<input
						type="password"
						class="field"
						bind:value={newPassword}
						placeholder="Laisser vide pour ne pas changer"
					/>
				</label>
				<PasswordStrength password={newPassword} bind:valid={passwordValid} />
			</div>

			{#if newPassword}
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
			{/if}

			{#if error}
				<div
					class="rounded-xl px-3 py-2 text-sm text-rose-600 bg-rose-50 border border-rose-200 dark:text-rose-300 dark:bg-rose-500/10 dark:border-rose-500/30"
				>
					{error}
				</div>
			{/if}

			{#if success}
				<div
					class="rounded-xl px-3 py-2 text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 dark:text-emerald-300 dark:bg-emerald-500/10 dark:border-emerald-500/30"
				>
					{success}
				</div>
			{/if}

			<button
				type="submit"
				class="btn btn-md btn-primary mt-2 disabled:opacity-50 disabled:cursor-not-allowed"
				disabled={!canSubmit}
			>
				{submitting ? 'Enregistrement...' : 'Enregistrer'}
			</button>
		</form>
	</div>
</div>
