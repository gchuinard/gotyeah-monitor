# GotYeah Monitor

Outil de monitoring de disponibilité (uptime) auto-hébergé. Surveille des services en **HTTP, ping ou port (TCP)**, vérifie codes de statut et **contenu (mot-clé)**, mesure la latence, suit l'expiration SSL, **alerte par email et webhook** (panne, rétablissement, latence, SSL), calcule le **% d'uptime (24h → 90j) et un SLA mensuel**, tient un **journal d'incidents**, et publie une **page de statut publique** avec badge SVG.

## Stack technique

| Couche | Techno |
|---|---|
| Backend | FastAPI (Python 3.11 prod / 3.14 dev) + SQLAlchemy async + Alembic |
| Base de données | MySQL 8 |
| Frontend | SvelteKit 2 + Tailwind CSS v4 + TypeScript |
| Infra | Docker Compose (dev & prod) |
| CI/CD | GitHub Actions → déploiement SSH sur Raspberry Pi |

## Fonctionnalités

### Surveillance
- Monitors **HTTP, ping et port (TCP)** — code de statut attendu, **check de contenu (mot-clé présent/absent)**, **seuil de latence**, et **intervalle de check configurable par monitor** (la boucle réveille toutes les 60 s et ne sonde que les monitors « dus », par défaut toutes les 10 min ; checks réseau concurrents et bornés)
- Suivi de la latence et de l'historique des checks (rétention **7 jours**), visualisé avec une **fenêtre temporelle configurable par monitor** (1h → 7j, persistée localement, bucketing adaptatif des barres de statut)
- **% d'uptime 24h / 7j / 30j / 90j** sur chaque carte + **rapport SLA mensuel** (table de rollup quotidien)
- Détection et affichage de l'**expiration SSL**

### Organisation & partage
- **Groupes de monitors** : dashboard regroupé repliable + barre de recherche
- **Page de statut publique** par utilisateur (`/status/<slug>`, accessible sans connexion) + **badge SVG d'uptime** embeddable — seuls les monitors marqués « publics » sont exposés (jamais l'URL ni de détail privé)
- **Tokens d'API en lecture seule** (`Authorization: Bearer gym_…`) pour interroger l'API depuis Grafana / scripts sans le mot de passe

### Alerting & incidents
- **Alerting** email + webhook (Discord / Slack / ntfy / générique) sur **panne** (après 2 échecs consécutifs — anti-flapping), **rétablissement**, **latence élevée** (seuil par monitor), et **expiration SSL** (J-30 / J-14 / J-7 / J-1 / expiré)
- **Journal d'incidents** persisté (ouverture/fermeture automatiques, conservé bien au-delà des checks), avec **acquittement + note de post-mortem**
- **Fenêtres de maintenance** planifiées : muettent alertes et ouvertures d'incident pendant la fenêtre (les checks continuent)

### Comptes & exploitation
- Authentification complète : inscription, vérification email, connexion JWT (rate-limitée, tokens hachés au repos), réinitialisation de mot de passe, changement d'email
- **Auto-surveillance** : endpoint `/health` reflétant la liveness réelle de la boucle, watchdog (relance la boucle si elle meurt) et dead-man switch sortant optionnel (`HEARTBEAT_URL`)
- Garde **anti-SSRF** sur toutes les cibles sondées (checks HTTP/ping/port et webhooks)
- Interface d'administration

## Structure du projet

```
gotyeah-monitor/
├── api/                  # FastAPI — logique métier, checks, auth
│   ├── routers/
│   │   ├── monitors.py   # CRUD monitors + uptime/SLA + incidents + maintenance
│   │   ├── groups.py     # Groupes de monitors
│   │   ├── public.py     # Page de statut publique (non auth) + gestion + badge SVG
│   │   ├── api_tokens.py # Tokens d'API (lecture seule)
│   │   └── admin.py      # Routes admin
│   ├── auth.py           # JWT (PyJWT), inscription, vérification email, rate-limit
│   ├── models.py         # Modèles SQLAlchemy
│   ├── schemas.py        # Schémas Pydantic
│   ├── database.py       # Session async MySQL
│   ├── mail_service.py   # Envoi d'emails (SMTP) : auth + alertes
│   ├── notifications.py  # Moteur d'alerting (transitions, latence, SSL) + webhooks
│   ├── ssrf_guard.py     # Garde anti-SSRF partagée (checks + webhooks)
│   ├── rate_limit.py     # Limiteur de débit (slowapi)
│   ├── main.py           # App FastAPI + boucle de monitoring + /health + watchdog
│   └── alembic/          # Migrations DB
├── front/                # SvelteKit — interface utilisateur
│   └── src/
│       └── routes/       # Pages : dashboard, login, register, profil, status/[slug] (publique)…
├── docker-compose.dev.yml
└── docker-compose.prod.yml
```

## Démarrage en développement

### Prérequis

- Docker & Docker Compose
- Node.js 24+ (optionnel, pour le dev frontend sans Docker)

### Lancer l'environnement complet

```bash
cp .env.dev.example .env.dev   # configurer les variables d'environnement
docker compose -f docker-compose.dev.yml up --build
```

| Service | URL |
|---|---|
| API | http://localhost:8000 |
| Frontend | http://localhost:5173 |
| Mailpit (UI emails) | http://localhost:8025 |
| MySQL | localhost:3307 |

### Variables d'environnement (`.env.dev`)

Voir `.env.dev.example` (à copier). L'API lit les variables `DB_*` ; les `MYSQL_*` ne servent qu'à initialiser le conteneur MySQL. `ALGORITHM` et la durée du token sont des constantes dans `api/auth.py` (pas des variables d'environnement).

```env
# Base de données — lue par l'API
DB_HOST=db
DB_PORT=3306
DB_USER=monitor
DB_PASSWORD=monitor
DB_NAME=monitor

# Initialisation du conteneur MySQL
MYSQL_ROOT_PASSWORD=root
MYSQL_DATABASE=monitor
MYSQL_USER=monitor
MYSQL_PASSWORD=monitor

SECRET_KEY=dev-secret-key          # en prod : ≥ 32 caractères, sinon l'API refuse de démarrer
ADMIN_EMAILS=ton@email.com         # emails admin séparés par des virgules

# Mail (MailPit en dev)
SMTP_HOST=mailpit
SMTP_PORT=1025
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=noreply@gotyeah.local

FRONTEND_URL=http://localhost:5173 # base des liens dans les emails
VITE_API_URL=http://localhost:8000

# Optionnel — dead-man switch : pingé à chaque cycle (ex. healthchecks.io)
# HEARTBEAT_URL=
```

> Les **alertes email** sont actives par défaut mais peuvent être coupées par utilisateur, et le **webhook d'alerte** (Discord / Slack / ntfy) s'active **par utilisateur** : tout se configure dans Profil → Notifications.

## Déploiement en production

Le déploiement cible un **Raspberry Pi** via SSH. La CI/CD GitHub Actions s'en charge automatiquement à chaque push sur `main`.

```bash
# Sur le serveur — première installation
git clone https://github.com/<org>/gotyeah-monitor.git
cd gotyeah-monitor
cp .env.example .env        # remplir les vraies valeurs

docker network create monitor_net
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```

### Variables pour la prod

Copier `.env.example` vers `.env` et tout remplir. Points clés :

```env
SECRET_KEY=                         # OBLIGATOIRE, ≥ 32 car. : python -c "import secrets; print(secrets.token_urlsafe(64))"
DB_HOST=db                          # nom du service réseau (pas localhost)
DB_USER=...
DB_PASSWORD=...
DB_NAME=...
MYSQL_ROOT_PASSWORD=...             # requis pour initialiser le conteneur MySQL
VITE_API_URL=https://api.votre-domaine.com
ADMIN_EMAILS=...
FRONTEND_URL=https://votre-domaine.com
# + variables SMTP réelles (SMTP_HOST/PORT/USER/PASSWORD/SMTP_FROM)
# HEARTBEAT_URL=...                  # optionnel : dead-man switch (ex. healthchecks.io)
```

> Un reverse proxy (Nginx, Caddy…) doit exposer les conteneurs `monitor_api_prod` (port 8000) et `monitor_front_prod` (port 80) vers l'extérieur.

## CI/CD

Le pipeline GitHub Actions (`.github/workflows/`) effectue à chaque push :

1. **Backend** — installation des dépendances Python + compilation (`compileall`)
2. **Frontend** — `npm ci`, lint ESLint/Prettier, `vite build`
3. **Deploy** (uniquement sur `main`) — SSH au Pi, `git pull`, `docker compose up --build`, **puis attente des healthchecks Docker avec rollback automatique** (retour au commit précédent) si l'API ou le front ne deviennent pas sains

## Développement frontend seul

```bash
cd front
npm install
npm run dev        # http://localhost:5173
npm run check      # type-check Svelte
npm run lint       # ESLint + Prettier
```

## Migrations base de données

```bash
# Depuis le conteneur api ou avec l'env activé
alembic upgrade head        # appliquer les migrations
alembic revision --autogenerate -m "description"   # créer une migration
```

## Endpoint de santé

`/health` reflète la **liveness réelle de la boucle de monitoring** (et pas un simple `ok` statique) : il renvoie **503** si aucun cycle n'a abouti depuis 3 intervalles (~30 min), ce qui permet à un healthcheck/observateur externe de détecter une boucle bloquée.

```
GET  /health  → 200 { "status": "ok",       "monitor_loop": "alive", "last_cycle_at": "…", "seconds_since_last_cycle": 42 }
              → 503 { "status": "degraded",  "monitor_loop": "stale", … }   # boucle bloquée
HEAD /health  → 200 / 503
```

En complément, un **watchdog** relance automatiquement la boucle si la tâche meurt, et un **dead-man switch** (`HEARTBEAT_URL`) pingue un service tiers à chaque cycle.
