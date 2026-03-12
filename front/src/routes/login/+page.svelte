<script lang="ts">
	import { goto } from '$app/navigation';
	import { auth, setAuth } from '$lib/stores/auth';
	import { get } from 'svelte/store';

	const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

	let email = '';
	let password = '';
	let submitting = false;
	let error: string | null = null;

	async function onSubmit() {
		submitting = true;
		error = null;
		try {
			// eslint-disable-next-line svelte/prefer-svelte-reactivity
			const form = new URLSearchParams();
			form.append('username', email);
			form.append('password', password);

			const res = await fetch(`${API_URL}/auth/login`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
				body: form.toString()
			});

			if (!res.ok) {
				const text = await res.text().catch(() => '');
				throw new Error(text || `HTTP ${res.status}`);
			}

			const data = await res.json();
			const token = data.access_token as string;

			const meRes = await fetch(`${API_URL}/auth/me`, {
				headers: { Authorization: `Bearer ${token}` }
			});
			if (!meRes.ok) {
				throw new Error('Impossible de récupérer le profil utilisateur');
			}
			const me = await meRes.json();

			setAuth(token, { id: me.id as number, email: me.email as string });

			await goto('/');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Erreur inconnue';
		} finally {
			submitting = false;
		}
	}

	const current = get(auth);
	if (current.token) {
		goto('/');
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
			<h1 class="text-2xl font-semibold text-slate-900">Connexion</h1>
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
				<div class="text-sm text-rose-600 bg-rose-50 border border-rose-200 rounded-xl px-3 py-2">
					{error}
				</div>
			{/if}

			<button
				type="submit"
				class="btn btn-md btn-primary mt-2 disabled:opacity-50 disabled:cursor-not-allowed"
				disabled={submitting}
			>
				{submitting ? 'Connexion...' : 'Se connecter'}
			</button>
		</form>

		<div class="mt-4 text-xs text-slate-500">
			Pas encore de compte ?
			<button
				type="button"
				class="text-cyan-600 hover:text-cyan-500 underline"
				on:click={() => goto('/register')}
			>
				Créer un compte
			</button>
		</div>
	</div>
</div>
