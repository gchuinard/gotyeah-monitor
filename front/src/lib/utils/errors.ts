/**
 * Transforme une réponse d'erreur HTTP en message utilisateur en français. Extrait le
 * `detail` du corps (gère le tableau des erreurs 422 de FastAPI), puis le combine à un
 * message adapté au code de statut (réseau/500/401/403/404/409/422…).
 * @param context - libellé de l'action en cours, injecté dans le message (ex. 'login').
 */
export async function parseApiError(res: Response, context: string): Promise<string> {
	let detail = '';
	try {
		const body = await res.json();
		const d = body?.detail;
		if (typeof d === 'string') {
			detail = d;
		} else if (Array.isArray(d)) {
			// FastAPI 422 : `detail` est un tableau d'objets { msg, loc, ... }.
			detail = d
				.map((item) => item?.msg)
				.filter(Boolean)
				.join(', ');
		} else if (d != null) {
			detail = typeof d === 'object' ? JSON.stringify(d) : String(d);
		}
	} catch {
		try {
			detail = await res.text();
		} catch {
			detail = '';
		}
	}

	// Erreurs réseau / serveur génériques
	if (res.status === 0 || res.status >= 502) {
		return `Impossible de contacter le serveur (${context}). Vérifiez que l'API est démarrée.`;
	}
	if (res.status === 500) {
		return `Erreur interne du serveur (${context})${detail ? ` : ${detail}` : ''}. Réessayez dans quelques instants.`;
	}
	if (res.status === 401) {
		if (context === 'login') return 'Email ou mot de passe incorrect.';
		return 'Session expirée. Reconnectez-vous.';
	}
	if (res.status === 403) return detail || 'Accès refusé.';
	if (res.status === 404) return `Ressource introuvable (${context}).`;
	if (res.status === 409 || (detail && detail.toLowerCase().includes('already exist'))) {
		return 'Cet email est déjà utilisé.';
	}
	if (res.status === 422) {
		return `Données invalides (${context})${detail ? ` : ${detail}` : ''}.`;
	}

	return detail || `Erreur inattendue (${context}, HTTP ${res.status}).`;
}

/**
 * Transforme une exception levée par `fetch` (avant toute réponse) en message en français :
 * détecte l'échec réseau (TypeError « fetch »), sinon renvoie le message de l'erreur.
 * @param context - libellé de l'action en cours, injecté dans le message.
 */
export function parseNetworkError(e: unknown, context: string): string {
	if (e instanceof TypeError && e.message.includes('fetch')) {
		return `Impossible de contacter le serveur (${context}). Vérifiez votre connexion et que l'API est démarrée.`;
	}
	if (e instanceof Error) return e.message;
	return `Erreur inconnue (${context}).`;
}
