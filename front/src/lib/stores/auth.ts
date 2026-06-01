import { writable } from 'svelte/store';

export type AuthUser = {
	id: number;
	email: string;
};

export type AuthState = {
	token: string | null;
	user: AuthUser | null;
};

const stored = typeof localStorage !== 'undefined' ? localStorage.getItem('auth') : null;

// JSON.parse protégé : une valeur corrompue ne doit pas faire planter le module
// (et donc toute l'app) au chargement.
let initial: AuthState = { token: null, user: null };
if (stored) {
	try {
		const parsed = JSON.parse(stored);
		if (parsed && typeof parsed === 'object') {
			initial = { token: parsed.token ?? null, user: parsed.user ?? null };
		}
	} catch {
		if (typeof localStorage !== 'undefined') localStorage.removeItem('auth');
	}
}

export const auth = writable<AuthState>(initial);

auth.subscribe((value) => {
	if (typeof localStorage === 'undefined') return;
	localStorage.setItem('auth', JSON.stringify(value));
});

export function setAuth(token: string, user: AuthUser) {
	auth.set({ token, user });
}

export function clearAuth() {
	auth.set({ token: null, user: null });
}
