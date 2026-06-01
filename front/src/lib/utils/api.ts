import { get } from 'svelte/store';
import { goto } from '$app/navigation';
import { browser } from '$app/environment';
import { auth, clearAuth } from '$lib/stores/auth';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

let redirecting = false;

/**
 * fetch authentifié vers l'API : ajoute le JWT, et sur 401 purge la session puis
 * redirige vers /login (une seule fois). `path` est relatif à l'API, ex. '/monitors'.
 */
export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
	const token = get(auth).token;
	const headers = new Headers(options.headers);
	if (token && !headers.has('Authorization')) {
		headers.set('Authorization', `Bearer ${token}`);
	}

	const res = await fetch(`${API_URL}${path}`, { ...options, headers });

	if (res.status === 401) {
		// Redirection uniquement côté navigateur (goto() ne doit pas tourner en SSR).
		if (browser && !redirecting) {
			redirecting = true;
			clearAuth();
			void goto('/login').finally(() => {
				redirecting = false;
			});
		}
		throw new Error('Session expirée. Reconnectez-vous.');
	}

	return res;
}
