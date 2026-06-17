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
		}),
		// CSP stricte sans script-src 'unsafe-inline' : SvelteKit calcule au build le hash
		// SHA-256 de ses scripts inline (bootstrap d'hydratation) et l'injecte dans une
		// balise <meta>. Le script de thème d'app.html est couvert par son hash ajouté
		// ci-dessous (contenu figé). style-src garde 'unsafe-inline' (styles runtime Svelte).
		csp: {
			mode: 'hash',
			directives: {
				'default-src': ['self'],
				// 2e hash = script de thème inline d'app.html (anti-flash). À régénérer si
				// ce <script> change : sha256 base64 de son contenu exact.
				'script-src': ['self', 'sha256-oclU6dgaYp6zDxdRq1v+Tu7U5I3b3C58sPX3u/CxrDs='],
				'style-src': ['self', 'unsafe-inline'],
				'img-src': ['self', 'data:'],
				'font-src': ['self', 'data:'],
				'connect-src': ['self', 'https://api-monitor.gautierchuinard.com'],
				'object-src': ['none'],
				'base-uri': ['self'],
				'form-action': ['self']
			}
		}
	}
};
