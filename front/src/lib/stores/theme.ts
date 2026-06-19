import { writable } from 'svelte/store';

export type Theme = 'light' | 'dark';

/** Résout le thème initial uniquement depuis la préférence stockée (la préférence système est volontairement ignorée), avec repli sur 'light'. */
function getInitialTheme(): Theme {
	if (typeof document === 'undefined') {
		return 'light';
	}

	// On ne regarde QUE la préférence stockée localement,
	// on ignore totalement le mode système (Windows / OS).
	const stored = window.localStorage.getItem('theme');
	if (stored === 'light' || stored === 'dark') {
		return stored;
	}

	// Valeur par défaut si rien n'est encore stocké
	return 'light';
}

const initial: Theme = getInitialTheme();

/** Thème courant ('light'/'dark'), persisté en localStorage et appliqué au DOM via la classe `.dark`. */
export const theme = writable<Theme>(initial);

/** Applique le thème au DOM (classe `.dark` forcée sur <html>) et le persiste en localStorage. */
function applyTheme(value: Theme) {
	if (typeof document === 'undefined') return;
	const root = document.documentElement;

	// On force la classe au lieu de simplement "toggle"
	root.classList.remove('dark');
	if (value === 'dark') {
		root.classList.add('dark');
	}

	window.localStorage.setItem('theme', value);
}

// appliquer immédiatement au démarrage côté client
if (typeof document !== 'undefined') {
	applyTheme(initial);
}

theme.subscribe((value) => {
	applyTheme(value);
});

export function toggleTheme() {
	theme.update((v) => (v === 'light' ? 'dark' : 'light'));
}
