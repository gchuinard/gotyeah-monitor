/**
 * Lit le token d'action (vérif email, reset, changement d'email) depuis le fragment
 * d'URL (#token=...). Le fragment n'est jamais envoyé au serveur ni dans le Referer
 * et n'apparaît pas dans les logs de proxy — contrairement à la query string.
 * Repli sur ?token=... pour rester compatible avec les emails envoyés avant ce changement.
 */
export function getUrlToken(): string {
	if (typeof window === 'undefined') return '';
	const hash = window.location.hash.replace(/^#/, '');
	const fromHash = new URLSearchParams(hash).get('token');
	if (fromHash) return fromHash;
	return new URLSearchParams(window.location.search).get('token') ?? '';
}
