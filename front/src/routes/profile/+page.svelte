<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { auth, clearAuth, type AuthState } from '$lib/stores/auth';
	import { get } from 'svelte/store';
	import PasswordStrength from '$lib/components/PasswordStrength.svelte';

	const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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

			const res = await fetch(`${API_URL}/auth/me`, {
				method: 'PUT',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${state.token}`
				},
				body: JSON.stringify(payload)
			});

			if (!res.ok) {
				const text = await res.text().catch(() => '');
				throw new Error(text || `HTTP ${res.status}`);
			}

			const me = await res.json();
			state = { token: state.token, user: { id: me.id, email: me.email } };
			auth.set(state);
			success = 'Profil mis à jour.';
			newPassword = '';
			confirmPassword = '';
		} catch (e) {
			error = e instanceof Error ? e.message : 'Erreur inconnue';
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
           rounded-3xl bg-white/85 backdrop-blur-2xl
           border border-white/70 shadow-[0_0_60px_rgba(56,189,248,0.3)]"
	>
		<div class="flex items-center justify-between mb-6">
			<div class="flex flex-col gap-1">
				<div class="text-xs uppercase tracking-[0.25em] text-slate-400">GotYeah Monitor</div>
				<h1 class="text-2xl font-semibold text-slate-900">Profil</h1>
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
				<span class="text-sm text-slate-600">Email</span>
				<input
					type="email"
					class="px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 focus:outline-none focus:ring-2 focus:ring-cyan-400/60"
					bind:value={email}
					required
				/>
			</label>

			<div class="flex flex-col gap-1">
				<label class="flex flex-col gap-1">
					<span class="text-sm text-slate-600">Nouveau mot de passe</span>
					<input
						type="password"
						class="px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 focus:outline-none focus:ring-2 focus:ring-cyan-400/60"
						bind:value={newPassword}
						placeholder="Laisser vide pour ne pas changer"
					/>
				</label>
				<PasswordStrength password={newPassword} bind:valid={passwordValid} />
			</div>

			{#if newPassword}
				<div class="flex flex-col gap-1">
					<label class="flex flex-col gap-1">
						<span class="text-sm text-slate-600">Confirmer le mot de passe</span>
						<input
							type="password"
							class="px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 focus:outline-none focus:ring-2 focus:ring-cyan-400/60
								{confirmPassword && !passwordsMatch ? 'border-rose-400 ring-2 ring-rose-200' : ''}"
							bind:value={confirmPassword}
						/>
					</label>
					{#if confirmPassword && !passwordsMatch}
						<p class="text-xs text-rose-500">Les mots de passe ne correspondent pas.</p>
					{:else if confirmPassword && passwordsMatch}
						<p class="text-xs text-emerald-600">Les mots de passe correspondent.</p>
					{/if}
				</div>
			{/if}

			{#if error}
				<div class="text-sm text-rose-600 bg-rose-50 border border-rose-200 rounded-xl px-3 py-2">
					{error}
				</div>
			{/if}

			{#if success}
				<div
					class="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-xl px-3 py-2"
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
