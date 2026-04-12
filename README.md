# GotYeah Monitor

Outil de monitoring de disponibilité (uptime) auto-hébergé. Surveille des URLs HTTP, vérifie les codes de statut, mesure la latence et suit l'expiration des certificats SSL.

## Stack technique

| Couche | Techno |
|---|---|
| Backend | FastAPI (Python 3.14) + SQLAlchemy async + Alembic |
| Base de données | MySQL 8 |
| Frontend | SvelteKit 2 + Tailwind CSS v4 + TypeScript |
| Infra | Docker Compose (dev & prod) |
| CI/CD | GitHub Actions → déploiement SSH sur Raspberry Pi |

## Fonctionnalités

- Ajout de monitors HTTP avec code de statut attendu configurable
- Vérification automatique toutes les **10 minutes**
- Suivi de la latence et de l'historique des checks (rétention **7 jours**)
- Détection et affichage de l'**expiration SSL**
- Authentification complète : inscription, vérification email, connexion JWT
- Réinitialisation de mot de passe et changement d'email par token
- Interface d'administration

## Structure du projet

```
gotyeah-monitor/
├── api/                  # FastAPI — logique métier, checks, auth
│   ├── routers/
│   │   ├── monitors.py   # CRUD monitors + historique
│   │   └── admin.py      # Routes admin
│   ├── auth.py           # JWT, inscription, vérification email
│   ├── models.py         # Modèles SQLAlchemy
│   ├── schemas.py        # Schémas Pydantic
│   ├── database.py       # Session async MySQL
│   ├── mail_service.py   # Envoi d'emails (SMTP)
│   ├── main.py           # App FastAPI + boucle de monitoring
│   └── alembic/          # Migrations DB
├── front/                # SvelteKit — interface utilisateur
│   └── src/
│       └── routes/       # Pages : dashboard, login, register, profil…
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

```env
MYSQL_DATABASE=monitor
MYSQL_USER=monitor
MYSQL_PASSWORD=monitor
MYSQL_ROOT_PASSWORD=root

SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

SMTP_HOST=mailpit
SMTP_PORT=1025
MAIL_FROM=noreply@gotyeah.local

VITE_API_URL=http://localhost:8000
```

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

### Variables supplémentaires pour la prod

```env
VITE_API_URL=https://api.votre-domaine.com
# + variables SMTP réelles
```

> Un reverse proxy (Nginx, Caddy…) doit exposer les conteneurs `monitor_api_prod` (port 8000) et `monitor_front_prod` (port 80) vers l'extérieur.

## CI/CD

Le pipeline GitHub Actions (`.github/workflows/`) effectue à chaque push :

1. **Backend** — installation des dépendances Python + compilation (`compileall`)
2. **Frontend** — `npm ci`, lint ESLint/Prettier, `vite build`
3. **Deploy** (uniquement sur `main`) — connexion SSH au Pi, `git pull`, `docker compose up --build`

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

```
GET /health   →  { "status": "ok" }
HEAD /health
```
