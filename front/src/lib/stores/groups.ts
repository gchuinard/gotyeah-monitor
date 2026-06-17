import { writable } from 'svelte/store';
import { apiFetch } from '$lib/utils/api';

export type MonitorGroup = {
	id: number;
	name: string;
};

// Liste des groupes de l'utilisateur, rechargée depuis l'API (non persistée).
export const groups = writable<MonitorGroup[]>([]);

/** Recharge la liste des groupes depuis l'API. Best-effort (apiFetch gère le 401). */
export async function loadGroups(): Promise<void> {
	try {
		const res = await apiFetch('/groups');
		if (res.ok) {
			const data = (await res.json()) as MonitorGroup[];
			groups.set(data.map((g) => ({ id: g.id, name: g.name })));
		}
	} catch {
		/* best-effort */
	}
}
