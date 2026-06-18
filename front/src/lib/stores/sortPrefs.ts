import { writable } from 'svelte/store';

export type SortMode = 'manual' | 'name' | 'status' | 'latency' | 'uptime';

export const SORT_OPTIONS: { value: SortMode; label: string }[] = [
	{ value: 'manual', label: 'Manuel (glisser-déposer)' },
	{ value: 'name', label: 'Nom (A→Z)' },
	{ value: 'status', label: "Statut (panne d'abord)" },
	{ value: 'latency', label: 'Latence (lent d’abord)' },
	{ value: 'uptime', label: 'Uptime (pire d’abord)' }
];

const VALID_MODES = new Set<SortMode>(['manual', 'name', 'status', 'latency', 'uptime']);

function persisted<T>(key: string, initial: T, validate?: (v: unknown) => v is T) {
	let start = initial;
	if (typeof window !== 'undefined') {
		const raw = window.localStorage.getItem(key);
		if (raw) {
			try {
				const parsed = JSON.parse(raw);
				if (!validate || validate(parsed)) start = parsed as T;
			} catch {
				/* valeur par défaut conservée */
			}
		}
	}
	const store = writable<T>(start);
	if (typeof window !== 'undefined') {
		store.subscribe((v) => window.localStorage.setItem(key, JSON.stringify(v)));
	}
	return store;
}

// Critère de tri courant (manuel = glisser-déposer)
export const sortMode = persisted<SortMode>(
	'sortMode',
	'manual',
	(v): v is SortMode => typeof v === 'string' && VALID_MODES.has(v as SortMode)
);

// Ordre manuel des groupes (liste d'ids de groupe)
export const groupOrder = persisted<number[]>(
	'groupOrder',
	[],
	(v): v is number[] => Array.isArray(v) && v.every((n) => typeof n === 'number')
);

// Ordre manuel des cards par section (clé de section -> liste d'ids de monitor)
export const monitorOrder = persisted<Record<string, number[]>>(
	'monitorOrder',
	{},
	(v): v is Record<string, number[]> => !!v && typeof v === 'object' && !Array.isArray(v)
);

/** Ordonne une liste d'objets {id} selon un ordre d'ids sauvegardé ; les nouveaux
 *  (absents de l'ordre) sont ajoutés à la fin dans leur ordre d'origine. */
export function applyManualOrder<T extends { id: number }>(items: T[], order: number[]): T[] {
	if (!order.length) return items;
	const pos = new Map(order.map((id, i) => [id, i]));
	return [...items].sort((a, b) => {
		const pa = pos.has(a.id) ? (pos.get(a.id) as number) : Number.MAX_SAFE_INTEGER;
		const pb = pos.has(b.id) ? (pos.get(b.id) as number) : Number.MAX_SAFE_INTEGER;
		return pa - pb;
	});
}
