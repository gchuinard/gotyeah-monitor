import { writable } from 'svelte/store';
import { apiFetch } from '$lib/utils/api';

export type MonitorGroup = {
	id: number;
	name: string;
	teamId: number | null;
};

// Liste des groupes de l'équipe active, rechargée depuis l'API (non persistée).
export const groups = writable<MonitorGroup[]>([]);

type GroupFromApi = { id: number; name: string; team_id: number | null };

/**
 * Recharge la liste des groupes depuis l'API, filtrée sur l'équipe (si fournie).
 * Best-effort (apiFetch gère le 401).
 */
export async function loadGroups(teamId?: number | null): Promise<void> {
	try {
		const path = teamId != null ? `/groups?team_id=${teamId}` : '/groups';
		const res = await apiFetch(path);
		if (res.ok) {
			const data = (await res.json()) as GroupFromApi[];
			groups.set(data.map((g) => ({ id: g.id, name: g.name, teamId: g.team_id ?? null })));
		}
	} catch {
		/* best-effort */
	}
}
