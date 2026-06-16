// SPA auth-gated (JWT en localStorage) : le serveur n'a pas accès au localStorage,
// donc le SSR rendait chaque page en version "déconnecté" avant que le client ne
// corrige/redirige → flash de la mauvaise page au chargement. On rend tout côté
// client : le premier paint connaît déjà l'état d'auth réel.
export const ssr = false;
