export async function parseApiError(res: Response, context: string): Promise<string> {
	let detail = '';
	try {
		const body = await res.json();
		detail = body?.detail ?? '';
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
	if (res.status === 403) return 'Accès refusé.';
	if (res.status === 404) return `Ressource introuvable (${context}).`;
	if (res.status === 409 || (detail && detail.toLowerCase().includes('already exist'))) {
		return 'Cet email est déjà utilisé.';
	}
	if (res.status === 422) {
		return `Données invalides (${context})${detail ? ` : ${detail}` : ''}.`;
	}

	return detail || `Erreur inattendue (${context}, HTTP ${res.status}).`;
}

export function parseNetworkError(e: unknown, context: string): string {
	if (e instanceof TypeError && e.message.includes('fetch')) {
		return `Impossible de contacter le serveur (${context}). Vérifiez votre connexion et que l'API est démarrée.`;
	}
	if (e instanceof Error) return e.message;
	return `Erreur inconnue (${context}).`;
}
