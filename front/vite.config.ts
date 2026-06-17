import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
	// Plus de bloc `preview` : la prod ne sert plus via `vite preview` mais via nginx
	// (adapter-static). L'ancien `allowedHosts` codait en dur un domaine unique.
	plugins: [tailwindcss(), sveltekit()],
	server: {
		watch: {
			usePolling: true,
			interval: 300
		}
	}
});
