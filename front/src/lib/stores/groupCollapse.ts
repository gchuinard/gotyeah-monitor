import { writable } from 'svelte/store';

// Quels groupes sont repliés sur le dashboard, persisté en localStorage.
// Clé spéciale 'ungrouped' pour la section "Sans groupe".
export type CollapseMap = Record<string, boolean>;

const STORAGE_KEY = 'groupCollapse';

/** Lit la map d'état replié depuis localStorage, en filtrant les valeurs non booléennes ; renvoie {} si absent ou corrompu. */
function load(): CollapseMap {
	if (typeof window === 'undefined') return {};
	const raw = window.localStorage.getItem(STORAGE_KEY);
	if (!raw) return {};
	try {
		const parsed = JSON.parse(raw);
		if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
		const out: CollapseMap = {};
		for (const [k, v] of Object.entries(parsed)) {
			if (typeof v === 'boolean') out[k] = v;
		}
		return out;
	} catch {
		return {};
	}
}

/** État replié/déplié de chaque groupe du dashboard, persisté en localStorage (clé `groupCollapse`). */
export const groupCollapse = writable<CollapseMap>(load());

if (typeof window !== 'undefined') {
	groupCollapse.subscribe((value) => {
		window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
	});
}

/** Bascule l'état replié/déplié d'un groupe. */
export function toggleGroupCollapse(key: string | number): void {
	const k = String(key);
	groupCollapse.update((m) => ({ ...m, [k]: !(m[k] ?? false) }));
}
