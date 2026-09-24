<script lang="ts">
	import { page } from '$app/stores';

	// Page d'erreur racine. Pour une adresse inconnue, nginx renvoie le shell avec le code
	// 404 (nginx.conf, error_page 404 /index.html) : le routeur client ne trouve aucune
	// route et affiche cette page. Les autres erreurs (chargement impossible, bug) ont
	// leur propre texte.
	$: notFound = $page.status === 404;
</script>

<svelte:head>
	<title>{notFound ? 'Page introuvable' : 'Erreur'} · GotYeah Monitor</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<div class="min-h-screen flex items-center justify-center py-10 px-4">
	<div
		class="w-full max-w-md mx-auto p-8
           rounded-3xl bg-white/85 dark:bg-slate-900/80 backdrop-blur-xl
           border border-white/70 dark:border-slate-800 shadow-soft-lg"
	>
		<div class="flex flex-col gap-1 mb-6">
			<div class="eyebrow">GotYeah Monitor</div>
			<h1 class="text-2xl font-semibold text-slate-900 dark:text-slate-100">
				{notFound ? 'Page introuvable' : 'Une erreur est survenue'}
			</h1>
		</div>

		{#if notFound}
			<p class="text-sm text-slate-500 dark:text-slate-400 mb-6">
				Cette adresse ne correspond à aucune page. Le lien est peut-être incomplet, ou la page a
				changé d'adresse.
			</p>
		{:else}
			<p class="text-sm text-slate-500 dark:text-slate-400 mb-6">
				La page n'a pas pu s'afficher (erreur {$page.status}). Réessayez dans un instant.
			</p>
		{/if}

		<div class="flex flex-col gap-2">
			<a href="/" class="btn btn-md btn-primary w-full">Retour à l'accueil</a>
			<a href="/login" class="btn btn-md btn-secondary w-full">Se connecter</a>
		</div>
	</div>
</div>
