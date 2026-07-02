<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { SvelteURLSearchParams } from 'svelte/reactivity';
	import { auth, setAuth } from '$lib/stores/auth';
	import { get } from 'svelte/store';
	import { parseApiError, parseNetworkError } from '$lib/utils/errors';

	const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

	let email = '';
	let password = '';
	let submitting = false;
	let error: string | null = null;

	// SSO / OIDC (bouton « Se connecter avec Pocket ID »)
	let oidcEnabled = false;
	let oidcLabel = 'Se connecter avec Pocket ID';
	let processingSso = false;

	/** Authentifie (form-urlencoded /auth/login), récupère le profil via /auth/me, stocke le JWT puis redirige vers le dashboard. */
	async function onSubmit() {
		submitting = true;
		error = null;
		try {
			const form = new SvelteURLSearchParams();
			form.append('username', email);
			form.append('password', password);

			const res = await fetch(`${API_URL}/auth/login`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
				body: form.toString()
			});

			if (!res.ok) {
				error = await parseApiError(res, 'login');
				return;
			}

			const data = await res.json();
			const token = data.access_token as string;

			const meRes = await fetch(`${API_URL}/auth/me`, {
				headers: { Authorization: `Bearer ${token}` }
			});
			if (!meRes.ok) {
				error = await parseApiError(meRes, 'récupération du profil');
				return;
			}
			const me = await meRes.json();

			setAuth(token, { id: me.id as number, email: me.email as string });
			await goto('/');
		} catch (e) {
			error = parseNetworkError(e, 'login');
		} finally {
			submitting = false;
		}
	}

	// Déjà connecté : on redirige sans jamais peindre le formulaire (anti-flash).
	let redirecting = get(auth).token !== null;
	if (redirecting) goto('/');

	/** Lance le flux OIDC : navigation top-level vers l'endpoint de login de l'API. */
	function startOidc() {
		window.location.href = `${API_URL}/auth/oidc/login`;
	}

	function ssoErrorMessage(code: string): string {
		switch (code) {
			case 'provider':
				return 'Connexion via Pocket ID refusée ou annulée.';
			case 'nosignup':
				return "Aucun compte Monitor n'est associé à cet identifiant Pocket ID.";
			case 'unverified':
				return "Adresse email non vérifiée côté fournisseur d'identité.";
			case 'noemail':
				return "Le fournisseur d'identité n'a pas transmis d'adresse email.";
			case 'disabled':
				return 'La connexion via Pocket ID est désactivée.';
			default:
				return 'Échec de la connexion via Pocket ID. Réessayez.';
		}
	}

	/** Finalise le retour SSO : le JWT arrive dans le fragment (#session=...). On récupère
	 *  le profil (/auth/me), on stocke, puis on redirige — comme le login mot de passe. */
	async function completeSso(token: string) {
		try {
			const meRes = await fetch(`${API_URL}/auth/me`, {
				headers: { Authorization: `Bearer ${token}` }
			});
			if (!meRes.ok) {
				error = await parseApiError(meRes, 'récupération du profil');
				processingSso = false;
				return;
			}
			const me = await meRes.json();
			setAuth(token, { id: me.id as number, email: me.email as string });
			await goto('/');
		} catch (e) {
			error = parseNetworkError(e, 'login');
			processingSso = false;
		}
	}

	onMount(async () => {
		if (redirecting) return;

		// Erreur renvoyée par le callback OIDC (query, non sensible) : afficher + nettoyer l'URL.
		const url = new URL(window.location.href);
		const ssoError = url.searchParams.get('sso_error');
		if (ssoError) {
			error = ssoErrorMessage(ssoError);
			url.searchParams.delete('sso_error');
			history.replaceState(null, '', url.pathname + url.search + url.hash);
		}

		// Retour SSO réussi : JWT dans le fragment. Le retirer AUSSITÔT de l'URL (pas de
		// JWT dans la barre d'adresse / l'historique), puis finaliser.
		const sessionToken = new URLSearchParams(window.location.hash.replace(/^#/, '')).get('session');
		if (sessionToken) {
			processingSso = true;
			history.replaceState(null, '', window.location.pathname + window.location.search);
			await completeSso(sessionToken);
			return;
		}

		// Sinon : demander à l'API si le bouton OIDC doit être affiché.
		try {
			const res = await fetch(`${API_URL}/auth/oidc/status`);
			if (res.ok) {
				const data = await res.json();
				oidcEnabled = !!data.enabled;
				if (data.label) oidcLabel = data.label as string;
			}
		} catch {
			// Réseau indisponible : on masque simplement le bouton.
		}
	});
</script>

{#if processingSso}
	<div class="min-h-screen flex items-center justify-center py-10">
		<div
			class="w-full max-w-md mx-auto p-8 text-center
	           rounded-3xl bg-white/85 dark:bg-slate-900/80 backdrop-blur-xl
	           border border-white/70 dark:border-slate-800 shadow-soft-lg
	           text-slate-600 dark:text-slate-300"
		>
			Connexion via Pocket ID en cours…
		</div>
	</div>
{/if}

<div
	class="min-h-screen flex items-center justify-center py-10"
	class:hidden={redirecting || processingSso}
>
	<div
		class="w-full max-w-md mx-auto p-8
           rounded-3xl bg-white/85 dark:bg-slate-900/80 backdrop-blur-xl
           border border-white/70 dark:border-slate-800 shadow-soft-lg"
	>
		<div class="flex flex-col gap-1 mb-6">
			<div class="eyebrow">GotYeah Monitor</div>
			<h1 class="text-2xl font-semibold text-slate-900 dark:text-slate-100">Connexion</h1>
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

			<button
				type="submit"
				class="btn btn-md btn-primary mt-2 disabled:opacity-50 disabled:cursor-not-allowed"
				disabled={submitting}
			>
				{submitting ? 'Connexion...' : 'Se connecter'}
			</button>
		</form>

		{#if oidcEnabled}
			<div class="my-4 flex items-center gap-3 text-xs text-slate-400 dark:text-slate-500">
				<span class="h-px flex-1 bg-slate-200 dark:bg-slate-700"></span>
				ou
				<span class="h-px flex-1 bg-slate-200 dark:bg-slate-700"></span>
			</div>

			<button
				type="button"
				class="btn btn-md w-full border border-slate-300 dark:border-slate-700
				       bg-white/60 dark:bg-slate-800/60 hover:bg-white dark:hover:bg-slate-800
				       text-slate-700 dark:text-slate-200"
				on:click={startOidc}
			>
				{oidcLabel}
			</button>
		{/if}

		<div class="mt-4 flex flex-col gap-2 text-xs text-slate-500 dark:text-slate-400">
			<div>
				Mot de passe oublié ?
				<button
					type="button"
					class="text-cyan-600 hover:text-cyan-500 dark:text-cyan-400 dark:hover:text-cyan-300 underline"
					on:click={() => goto('/forgot-password')}
				>
					Réinitialiser
				</button>
			</div>
			<div>
				Pas encore de compte ?
				<button
					type="button"
					class="text-cyan-600 hover:text-cyan-500 dark:text-cyan-400 dark:hover:text-cyan-300 underline"
					on:click={() => goto('/register')}
				>
					Créer un compte
				</button>
			</div>
		</div>
	</div>
</div>
