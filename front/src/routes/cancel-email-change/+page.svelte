<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

	let pageStatus: 'loading' | 'success' | 'error' = 'loading';
	let message = '';

	onMount(async () => {
		const token = new URLSearchParams(window.location.search).get('token');
		if (!token) {
			pageStatus = 'error';
			message = 'Lien invalide.';
			return;
		}

		try {
			const res = await fetch(`${API_URL}/auth/cancel-email-change?token=${token}`);
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
           rounded-3xl bg-white/85 backdrop-blur-2xl
           border border-white/70 shadow-[0_0_60px_rgba(56,189,248,0.3)]"
	>
		<div class="flex flex-col gap-1 mb-6">
			<div class="text-xs uppercase tracking-[0.25em] text-slate-400">GotYeah Monitor</div>
			<h1 class="text-2xl font-semibold text-slate-900">Annulation du changement</h1>
		</div>

		{#if pageStatus === 'loading'}
			<p class="text-sm text-slate-500">Annulation en cours…</p>
		{:else if pageStatus === 'success'}
			<div
				class="flex items-center gap-2 text-sm text-emerald-600 bg-emerald-50 border border-emerald-200 rounded-xl px-3 py-2 mb-4"
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
				class="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 mb-4"
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
					<p class="text-sm font-semibold text-amber-700 mb-0.5">Sécurisez votre compte</p>
					<p class="text-xs text-amber-600 leading-relaxed">
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
				class="flex items-start gap-2 text-sm text-rose-600 bg-rose-50 border border-rose-200 rounded-xl px-3 py-2 mb-4"
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
