import { writable, derived, get } from 'svelte/store';
import { apiFetch } from '$lib/utils/api';

export type TeamRole = 'admin' | 'member' | 'readonly';

export type Team = {
	id: number;
	name: string;
	role: TeamRole;
	memberCount: number;
	alertWebhookUrl: string | null;
	alertWebhookKind: string | null;
};

// Liste des équipes du user, rechargée depuis l'API (non persistée).
export const teams = writable<Team[]>([]);

// Équipe active : persistée en localStorage (comme theme.ts / historyWindow.ts).
const STORAGE_KEY = 'activeTeamId';

function loadActive(): number | null {
	if (typeof localStorage === 'undefined') return null;
	const raw = localStorage.getItem(STORAGE_KEY);
	if (!raw) return null;
	const n = Number(raw);
	return Number.isFinite(n) ? n : null;
}

export const activeTeamId = writable<number | null>(loadActive());

if (typeof localStorage !== 'undefined') {
	activeTeamId.subscribe((v) => {
		if (v === null) localStorage.removeItem(STORAGE_KEY);
		else localStorage.setItem(STORAGE_KEY, String(v));
	});
}

// Équipe active résolue + rôle courant (dérivés).
export const activeTeam = derived(
	[teams, activeTeamId],
	([$teams, $id]) => $teams.find((t) => t.id === $id) ?? null
);
export const activeRole = derived(activeTeam, ($t) => $t?.role ?? null);

/** Droit d'écriture : admin ou member (readonly = lecture seule). */
export function canWrite(role: TeamRole | null | undefined): boolean {
	return role === 'admin' || role === 'member';
}

type TeamFromApi = {
	id: number;
	name: string;
	role: TeamRole;
	member_count: number;
	alert_webhook_url: string | null;
	alert_webhook_kind: string | null;
};

function mapTeam(t: TeamFromApi): Team {
	return {
		id: t.id,
		name: t.name,
		role: t.role,
		memberCount: t.member_count,
		alertWebhookUrl: t.alert_webhook_url,
		alertWebhookKind: t.alert_webhook_kind
	};
}

/**
 * Recharge la liste des équipes. Si l'équipe active est absente/invalide, sélectionne
 * la première équipe. Best-effort (apiFetch gère le 401).
 */
export async function loadTeams(): Promise<void> {
	try {
		const res = await apiFetch('/teams');
		if (!res.ok) return;
		const data = (await res.json()) as TeamFromApi[];
		const mapped = data.map(mapTeam);
		teams.set(mapped);
		const cur = get(activeTeamId);
		if (cur === null || !mapped.some((t) => t.id === cur)) {
			activeTeamId.set(mapped.length ? mapped[0].id : null);
		}
	} catch {
		/* best-effort */
	}
}
