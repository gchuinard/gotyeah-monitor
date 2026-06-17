import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

export default {
	preprocess: vitePreprocess(),
	kit: {
		// SPA auth-gated en rendu client-only (ssr=false) : pas de prerender possible.
		// On émet une page de repli unique (index.html) que nginx sert pour toutes les
		// routes → plus de serveur Node/Vite en prod, juste des fichiers statiques.
		adapter: adapter({
			fallback: 'index.html'
		})
	}
};
