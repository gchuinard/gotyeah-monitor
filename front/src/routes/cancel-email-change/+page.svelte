<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { getUrlToken } from '$lib/utils/token';

	const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

	let pageStatus: 'loading' | 'success' | 'error' = 'loading';
	let message = '';

	// Au montage : lit le token du fragment d'URL et annule le changement d'email en attente
	// (POST /auth/cancel-email-change) ; le résultat pilote l'affichage success/error.
	onMount(async () => {
		const token = getUrlToken();
		if (!token) {
			pageStatus = 'error';
			message = 'Lien invalide.';
			return;
		}

		try {
			const res = await fetch(`${API_URL}/auth/cancel-email-change`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ token })
			});
			const data = await res.json();
			if (res.ok) {
				pageStatus = 'success';
				message = data.message;
			} else {
				pageStatus = 'error';
				message = data.detail || 'Lien invalide ou expiré.';
			}
		} catch {
			pageStatus = 'error';
			message = 'Impossible de contacter le serveur.';
		}
	});
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
				Annulation du changement
			</h1>
		</div>

		{#if pageStatus === 'loading'}
			<p class="text-sm text-slate-500 dark:text-slate-400">Annulation en cours…</p>
		{:else if pageStatus === 'success'}
			<div
				class="flex items-center gap-2 rounded-xl px-3 py-2 mb-4 text-sm text-emerald-600 bg-emerald-50 border border-emerald-200 dark:text-emerald-300 dark:bg-emerald-500/10 dark:border-emerald-500/30"
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
				{message}
			</div>
			<div
				class="flex items-start gap-3 rounded-xl px-4 py-3 mb-4 bg-amber-50 border border-amber-200 dark:bg-amber-500/10 dark:border-amber-500/30"
			>
				<svg
					class="w-5 h-5 shrink-0 text-amber-500 mt-0.5"
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
				<div>
					<p class="text-sm font-semibold text-amber-700 dark:text-amber-300 mb-0.5">
						Sécurisez votre compte
					</p>
					<p class="text-xs text-amber-600 dark:text-amber-200/80 leading-relaxed">
						Si vous n'êtes pas à l'origine de cette demande, quelqu'un a peut-être accès à votre
						compte. Nous vous recommandons de <strong>changer votre mot de passe</strong> dès maintenant.
					</p>
				</div>
			</div>
			<button type="button" class="btn btn-md btn-primary w-full" on:click={() => goto('/login')}>
				Se connecter et changer mon mot de passe
			</button>
		{:else}
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
				{message}
			</div>
			<button type="button" class="btn btn-md btn-primary w-full" on:click={() => goto('/')}>
				Retour à l'accueil
			</button>
		{/if}
	</div>
</div>
