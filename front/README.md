# GotYeah Monitor — Frontend

Interface SvelteKit 2 + Tailwind CSS v4 (TypeScript) du projet **GotYeah Monitor**.
Voir le [README racine](../README.md) pour la vue d'ensemble, le démarrage Docker et le déploiement.

## Développement (front seul)

```bash
npm install
npm run dev      # http://localhost:5173
npm run lint     # prettier --check + eslint (ce que la CI vérifie)
npm run check    # svelte-check (type-check)
npm run build    # build de production
```

> L'URL de l'API est lue à la **build** via `VITE_API_URL` (`import.meta.env`). En dev,
> elle vaut `http://localhost:8000` par défaut (voir `docker-compose.dev.yml`).

## Repères

- `src/routes/` — pages (dashboard, login, register, profil, admin…).
- `src/lib/components/` — `MonitorCard`, `MonitorDetailModal`, `StatusBar`, `Sparkline`, `PasswordStrength`.
- `src/lib/stores/` — `auth`, `monitors`, `theme`, `historyWindow` (persistés en localStorage).
- `src/lib/utils/api.ts` — `apiFetch()` : appels authentifiés (JWT) + déconnexion auto sur 401.
