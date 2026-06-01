# Audit — gotyeah-monitor

> Audit réalisé le **2026-06-01**.
> **Méthode** : 9 dimensions parcourues en parallèle (auth, SSRF/validation, backend async, frontend cœur, composants frontend, données/migrations, infra/CI, dépendances, cohérence docs) par des sous-agents, **chaque finding vérifié de façon adversariale** (re-lecture du code cité pour le confirmer ou le réfuter), puis recoupé manuellement avec la config réelle (`.env`, `requirements.txt`, `docker-compose`).
> **Résultat** : 64 findings confirmés, 1 écarté.

| Sévérité | Nb | Verdict |
|---|---|---|
| 🔴 Critique | 1 | Contournement total d'authentification |
| 🟠 Élevé | 4 | SSRF, mort silencieuse du monitoring, crash UI, prod DB cassée |
| 🟡 Moyen | 10 | Sécurité auth, robustesse front, dérive de schéma |
| 🔵 Faible | 34 | Robustesse, validation, infra |
| ⚪ Info | 15 | Notes / dette / dont 4 décisions intentionnelles |

**Verdict global** : la base est propre et cohérente (l'architecture documentée dans `CLAUDE.md` est fidèle au code), mais le projet est exposé sur IP publique avec de **vrais comptes/emails** — or plusieurs failles de sécurité y sont exploitables. La priorité absolue est le secret JWT.

---

## 🔴 CRITIQUE

### 1. Secret JWT faible → contournement total de l'authentification
`api/auth.py:25` · *confirmé, recoupé manuellement*

```python
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")  # fallback en dur
```

- Le `.env` de prod réel contient `SECRET_KEY` = **placeholder de 18 caractères** (vérifié sur disque). HS256 (symétrique) → quiconque connaît/devine ce secret peut **forger un JWT pour n'importe quel `user_id`**. Le token ne porte que `{sub, exp}`, sans `aud`/`iss`/révocation (`auth.py:97-104`, `:433`) → usurpation de n'importe quel compte.
- Le fallback en dur signifie aussi qu'un déploiement mal configuré tourne **silencieusement** sur une clé publiquement connue (présente dans le repo).
- `ADMIN_EMAILS` est actuellement vide (admin fail-closed) → l'escalade admin nécessite un admin configuré, mais l'usurpation utilisateur, elle, est inconditionnelle.

**Correctif** : supprimer le fallback, échouer au démarrage si la clé manque ou < 32 octets. Générer avec `python -c 'import secrets; print(secrets.token_urlsafe(64))'`, stocker uniquement dans le `.env` de prod. La rotation invalide tous les tokens existants (souhaitable ici).

---

## 🟠 ÉLEVÉ

### 2. SSRF — la boucle fetch des URL arbitraires vers le réseau interne
`api/main.py:80,92,103` · *confirmé empiriquement*

`HttpUrl` (Pydantic) ne valide que le **schéma**, pas l'hôte. Un utilisateur authentifié peut créer un monitor vers `http://127.0.0.1:3306`, `http://169.254.169.254/latest/meta-data/`, `http://monitor_db_prod:3306`, un host RFC1918 du LAN du Pi… La boucle fait alors un `GET` (toutes les 10 min) **et** un handshake TLS (`check_ssl_expiry`). La réponse `MonitorRead` renvoie `status` / `last_status_code` / `last_latency_ms` → **oracle de scan de ports/hôtes internes** (SSRF aveugle). `follow_redirects=True` (`main.py:103`) permet de contourner une validation naïve via une redirection 302.

**Correctif** : résoudre l'hôte et rejeter loopback / link-local (`169.254/16`) / RFC1918 / `0.0.0.0` via le module `ipaddress` (`is_private`/`is_loopback`/`is_link_local`), **au moment du fetch** (anti-DNS-rebinding) ; `follow_redirects=False` ; appliquer le même contrôle dans `check_ssl_expiry`.

### 3. Une seule exception non gérée tue le monitoring jusqu'au redémarrage
`api/main.py:102-120` · *confirmé, recoupé manuellement*

`monitor_loop()` n'a **aucun** `try/except` autour du corps du `while True`. `check_single_monitor` protège le `GET`, mais le `delete` de rétention (`:108`), le `select` (`:112`) et surtout `session.commit()` (`:118`) sont nus. Un seul échec DB (deadlock, *MySQL server has gone away*, disque plein) fait remonter l'exception, la task asyncio **meurt silencieusement** (l'API HTTP continue de répondre) — plus aucun check ni alerte SSL, et rien ne le signale. C'est l'échec le plus grave pour un outil de monitoring.

**Correctif** : envelopper l'itération dans `try/except` + `rollback` + log, afin qu'un cycle puisse échouer sans tuer la boucle ; ajouter un `add_done_callback` sur la task pour logger/relancer si elle meurt.

### 4. Sparkline plante sur des latences constantes (clés dupliquées)
`front/src/lib/components/Sparkline.svelte:43-46,127` · *confirmé*

Quand toutes les latences sont égales (endpoint local stable à 1-2 ms), `range = max-min || 1` → les labels de la grille Y deviennent `[V, V, V-1]` (deux identiques). Le `{#each gridLines as gl (gl.label)}` est **clé par `gl.label`** → Svelte lève *« Cannot have duplicate keys »* et **crashe** le rendu (et les onglets Latence / Les deux du modal).

**Correctif** : clé par index → `{#each gridLines as gl, i (i)}`.

### 5. Le `.env` de prod n'a aucune variable `MYSQL_*` → bring-up DB impossible
`.env` / `docker-compose.prod.yml:31-44` · *confirmé sur disque*

Le `.env` de prod ne contient **aucun** `MYSQL_DATABASE/MYSQL_USER/MYSQL_PASSWORD/MYSQL_ROOT_PASSWORD` (uniquement `DB_*`, que l'image `mysql:8` ignore). Sur un volume vierge, la base et l'utilisateur ne sont **jamais créés** → l'API ne peut pas se connecter. Le healthcheck code en dur `-u monitor -pmonitor` (un user qui n'existera pas). Le Pi actuel a dû être réparé à la main → footgun latent, non reproductible depuis le repo.

**Correctif** : dans `.env`, `DB_HOST=db` + ajouter `MYSQL_ROOT_PASSWORD`, `MYSQL_DATABASE=${DB_NAME}`, `MYSQL_USER=${DB_USER}`, `MYSQL_PASSWORD=${DB_PASSWORD}` ; corriger le healthcheck avec les vrais identifiants.

---

## 🟡 MOYEN (10)

### Sécurité auth
- **Tokens en clair en base** (`models.py:76,88,102-103`) — reset/vérif/changement-email stockés verbatim. Un dump DB = prise de contrôle de compte immédiate. → stocker `sha256(token)`, n'envoyer le brut que dans l'email.
- **Aucun rate-limiting** sur `/login`, `/forgot-password`, `/register`, `/reset-password` (`main.py:159-161`) — credential stuffing + amplificateur d'emails (abus quota Resend). → `slowapi` par IP + fail2ban au reverse proxy.
- **Énumération de comptes** (`auth.py:119-124,422-426,309-314`) — `/register` « Email already registered », `/login` 403 « Email non vérifié » seulement si mot de passe correct, `/change-email` « Email already in use », et timing différent sur `/forgot-password`.
- **Reset / changement d'email n'invalident pas les sessions JWT** (`auth.py:252-256,372-374`) — tokens valides 24 h, sans `jti`/version → un reset ne déconnecte pas l'attaquant. → colonne `password_changed_at`/`token_version` vérifiée dans `get_current_user`.

### Frontend
- **Pas de logout-sur-401** (`+page.svelte:230-256`) — à l'expiration du JWT, le dashboard reste bloqué sur « Session expirée » sans purge ni redirection ; tout réessai re-401. → wrapper `apiFetch()` qui `clearAuth()` + `goto('/login')` sur 401.
- **`auth` localStorage corrompu = écran blanc** (`auth.ts:13-15`) — `JSON.parse` non protégé au chargement du module → toute l'app ne monte plus (idem `add/+page.svelte:20`, `edit/[id]/+page.svelte:23,53`). → `try/catch` + validation de forme.
- **Suppression admin échoue en silence** (`admin/+page.svelte:134-160`) — la modale se ferme, aucun retour d'erreur si `!res.ok` ou throw réseau → l'admin croit avoir supprimé. → `try/catch` + bannière d'erreur.

### Données / docs
- **Double autorité de schéma** (`database.py:37-42`) — `Base.metadata.create_all` tourne à chaque démarrage **en plus** d'Alembic → dérive latente si `create_all` s'exécute avant le stamp. → retirer `create_all` (ou le réserver au dev), s'appuyer sur `alembic upgrade head`.
- **README documente des variables jamais lues** (`README.md:69-86`) — `MYSQL_*` (l'API lit `DB_*`), `MAIL_FROM` (le code lit `SMTP_FROM`), `ALGORITHM`/`ACCESS_TOKEN_EXPIRE_MINUTES` (constantes en dur) ; et omet `ADMIN_EMAILS`/`FRONTEND_URL` requis. Copier le template tel quel donne une API qui ne se connecte pas.

---

## 🔵 FAIBLE (34) — par thème

### Backend / async
- Checks **séquentiels** avec timeout 10 s → cycle ∝ N×~15 s, un check lent retarde tous les suivants (`main.py:115`).
- DELETE de rétention + tous les checks dans un seul `commit` → un échec en fin de boucle perd tout le travail du cycle (`main.py:107-118`).
- Handshake SSL bloquant sur l'executor par défaut (threadpool partagé), en série à chaque check (`main.py:59-68`).
- Pool DB par défaut (5+10) sans `pool_recycle` → connexions MySQL périmées sur Pi (`database.py:23-29`).

### Sécurité
- Pas de limite de taille de réponse sur le fetch monitoré → OOM possible (`main.py:80-82`).
- Validation monitor quasi absente : pas de borne sur `name`, pas de contrôle d'enum `type`, pas de plage sur `expected_status_code` (`schemas.py:33-44`).
- **Aucune validation de robustesse/longueur de mot de passe** — mot de passe vide accepté à l'inscription et au reset (`schemas.py:11-17,83-85`).
- Tokens dans la query string `?token=` → fuite via logs/referrer (`mail_service.py:83,123,163,206`).
- Handler d'exception code en dur `Access-Control-Allow-Origin:*` + fuite de traceback si `DEBUG=true` (`main.py:30-40`).

### Frontend
- `'[object Object]'` affiché sur erreur 422 de changement d'email (`+page.svelte:140-142`).
- Pas d'`AbortController` → courses entre refresh, last-writer-wins (`+page.svelte:214-261`).
- Le JWT n'est jamais décodé ni vérifié pour l'expiration — « a un token » = « connecté » (`+page.svelte:219-222`).
- SSR activé sur une SPA auth-gated → flash initial / rendu redondant d'un shell déconnecté (`+layout.svelte:1-3`).
- Logique token + fetch + gestion d'erreur dupliquée partout (pas de client API partagé) (`+page.svelte:56-276`).
- Modal sans focus-trap, sans gestion de focus, non fermable au clavier de l'intérieur (`MonitorDetailModal.svelte:114-152`).

### Données / migrations
- Dérive `is_verified` `server_default` : modèle `"0"` vs migration 0003 `"1"` (`models.py:14`).
- FK `monitors.user_id` **sans `ON DELETE`** → suppression user non atomique, nettoyage des orphelins cassé (`models.py:50`).
- **Index composite `(monitor_id, checked_at)` manquant** sur le chemin chaud de l'historique (`monitors.py:122-126`).

### Infra / CI
- Pas de `HEALTHCHECK` / `depends_on: healthy` sur api & front malgré `/health` fonctionnel (`docker-compose.prod.yml:2-29`).
- Conteneurs en **root** + `build-essential` embarqué en prod (`Dockerfile.prod:1-17`).
- CI **sans étape de tests**, deploy par `git pull` aveugle sur le Pi, sans rollback ni garde en cas d'échec de migration (`ci-cd.yml:27-68`).
- `vite preview` `allowedHosts` code en dur un seul domaine → casse silencieusement si le domaine change (`vite.config.ts:6-8`).
- **`docker-compose.dev.bak` cassé et committé**, contredit le vrai compose dev.
- `entrypoint.sh` `upgrade head` sans retry DB-ready ni rollback si une migration échoue (`entrypoint.sh:5-34`).
- Aucune limite de ressources sur les conteneurs → OOM du Pi possible.
- Tags d'images flottants `mysql:8` / `mailpit:latest` → déploiements non reproductibles.

### Dépendances
- **`python-jose==3.3.0` abandonné** — advisories JWT connues (CVE-2024-33663 confusion d'algorithme, CVE-2024-33664 JWT-bomb). → migrer vers `pyjwt`.
- `vite` advisories *high* alors que la prod sert via `vite preview` exposé au réseau (`package.json:37`).
- Dockerfiles en `npm install` au lieu de `npm ci` → la prod ignore le lockfile testé par la CI (`Dockerfile.prod:7`).
- **`.env.example` / `.env.dev.example` absents** alors que le README demande de les copier ; `.gitignore` `.env.*` les bloquerait sans exception `!`.

### Docs
- README cite des fichiers d'exemple inexistants (`README.md:58,96`).
- Node 24 (docs) vs `node:20-alpine` (Dockerfiles) (`README.md:53`).
- `ACCESS_TOKEN_EXPIRE_MINUTES=60` documenté mais durée réelle = **24 h** (`README.md:79,117`).
- `front/README.md` = template SvelteKit non modifié.

---

## ⚪ INFO (15) — sélection

- `ADMIN_EMAILS` vide = fail-closed sûr, mais comparaison **sensible à la casse** (`admin.py:24`).
- `ssl_expiry_at` stocké **naïf** depuis « GMT » alors que tout le reste est aware-UTC (`main.py:53` / `models.py:45`).
- `clearAuth` laisse `{token:null}` au lieu de supprimer la clé localStorage (`auth.ts:19`).
- `MonitorCard` utilise `beforeUpdate` + `setTimeout` pour le flash de statut (anti-pattern lifecycle Svelte) (`MonitorCard.svelte:29-35`).
- Migration 0002 recrée `monitor_checks` déjà créée en 0001 (`0002_add_missing_columns.py:40-49`).
- Charset / collation DB jamais spécifiés (`database.py:19-23`).
- StatusBar/Sparkline ignorent les checks au bord d'attaque de la fenêtre (intervalle semi-ouvert finissant à `now`) (`StatusBar.svelte:43-49`).

**Décisions intentionnelles** (documentées dans `CLAUDE.md`, signalées comme risques acceptés) : CORS `allow_origins=['*']` (acceptable car credentials désactivés), `vite preview` en prod, `adapter-auto` sans plateforme cible, `entrypoint.sh` sans rollback.

---

## ✅ Faux positif écarté (1)

Le cast `m.status as 'up' | 'down'` (`+page.svelte:244`) a été signalé puis **réfuté** : l'enum DB (`models.py:36`) borne `status` à exactement `{up, down, unknown}`, `unknown` est mappé vers `checking`, et `ping`/`port` appartiennent à la colonne `type`, pas `status`. Le cast décrit un invariant réel — pas de bug.

---

## 🎯 Plan d'action priorisé

1. **Aujourd'hui** : générer un vrai `SECRET_KEY` + supprimer le fallback (#1) — sinon tout le reste est secondaire.
2. **Cette semaine** : `try/except` sur la boucle monitoring (#3) · garde SSRF (#2) · fix `MYSQL_*` du `.env` prod (#5) · clé par index Sparkline (#4, *one-liner*).
3. **Quick wins faciles** : rate-limiting `slowapi` · logout-sur-401 + `try/catch` `JSON.parse` · hash des tokens · supprimer `create_all` · index `(monitor_id, checked_at)` · `npm ci` · retirer `docker-compose.dev.bak`.
