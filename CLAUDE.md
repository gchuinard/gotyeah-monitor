# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Frontend (`front/`)
```bash
npm run dev          # vite dev — http://localhost:5173
npm run lint         # prettier --check . && eslint . — gates CI
npm run format       # prettier --write . — fix formatting
npm run check        # svelte-kit sync && svelte-check (type-check)
npm run build        # vite build
```

Local WSL note : `npm run check` and `npm run build` often fail with `EACCES` on `.svelte-kit/` (filesystem perms). `npm run lint` works and is what CI runs — rely on it. The CI runner is plain Linux so the build passes there.

### Backend (`api/`)
```bash
python -m compileall .                       # what CI runs to validate
python -m alembic upgrade head               # apply migrations
python -m alembic revision --autogenerate -m "<msg>"   # new migration
```

The API auto-runs migrations on container start via `entrypoint.sh` (prod only) — manual `alembic upgrade` is only needed outside Docker.

### Full stack
```bash
docker compose -f docker-compose.dev.yml up --build   # API:8000 · front:5173 · MySQL:3307 · Mailpit UI:8025
```

## Architecture

### Backend is monolithic, not a worker + API split

Despite the empty `worker/` directory at the repo root, **there is no separate worker process**. The monitoring loop runs as an asyncio task inside the FastAPI app itself, started in `api/main.py:on_startup` and cancelled in `on_shutdown`. Implications:

- `CHECK_INTERVAL_SECONDS = 600` (10 min) and `HISTORY_RETENTION_DAYS = 7` are constants in `api/main.py:43-44`. The loop both performs checks AND deletes rows older than 7 days from `monitor_checks` each iteration.
- The frontend's `/monitors/:id/history` returns ALL stored checks (no server-side window). The window is purely a client-side filter in `StatusBar.svelte`.
- Only `type='http'` is actually executed (`check_single_monitor` does `client.get(monitor.url)`). The `Enum('http','ping','port')` in the model has unused values — the UI lets you pick them but the worker ignores non-http.
- SSL expiry is refreshed every check via a sync `ssl.create_default_context()` call run in an executor (`check_ssl_expiry`).

### User isolation is per-route, not via row-level security

Every router handler that touches a `Monitor` re-checks `monitor.user_id == current_user.id` and 403s otherwise. `Monitor.user_id` is nullable, and `update`/`delete` claim ownership of orphan monitors (`user_id is None`) for the current user — a legacy migration path. Don't drop that branch.

### Auth has a transparent SHA-256 → Argon2 rehash

`api/auth.py` keeps a legacy code path: at login, if the stored hash is 64 hex chars (SHA-256), it's verified against SHA-256 and immediately rehashed to Argon2id via passlib. New registrations always use Argon2. Don't simplify the verify branch.

### Admin is env-based, not a DB column

`ADMIN_EMAILS` env var (comma-separated) is parsed once in `api/routers/admin.py`. There's no `is_admin` field on `User`. Adding an admin = editing the env file + restarting the API.

### Migrations have a stamping smart-start

`api/entrypoint.sh` checks if `users` table exists without an `alembic_version` row — if so, it `alembic stamp 0001` before running `upgrade head`. This protects pre-existing prod DBs that were created by `Base.metadata.create_all` before Alembic was introduced. Be careful when adding migration `0001`-equivalent destructive changes.

### Frontend talks to API via fetch + JWT in localStorage

- `VITE_API_URL` is **build-time** (read via `import.meta.env.VITE_API_URL`). Changing the API URL requires rebuilding the front image — that's why `docker-compose.prod.yml` passes it as a build `arg`, not a runtime env.
- JWT lives in `localStorage` under `auth` key (see `front/src/lib/stores/auth.ts`). Not httpOnly cookies — XSS would leak the token.
- Stores follow a consistent localStorage-persist pattern via `writable` + `subscribe` (see `theme.ts`, `historyWindow.ts`).

### StatusBar history window is per-monitor, persisted, bucketed

`front/src/lib/components/StatusBar.svelte` is used in both `MonitorCard` and `MonitorDetailModal` — both must pass `monitorId={...}`. Per-monitor choice is stored in `localStorage.historyWindowHours` as a JSON map `{monitorId: hours}` (see `front/src/lib/stores/historyWindow.ts`). Each preset has a `bucketMinutes` field so bars aggregate adaptively (10 min for ≤12h windows, up to 1 day for 7j). A bucket with both up & down checks renders yellow, no-data buckets render gray.

### Prod front isn't a real prod server

`front/Dockerfile.prod` runs `npm run preview` (Vite's preview server) on port 80. Fine for a Raspberry Pi side project, would NOT scale. If touching prod hosting, this is the thing to replace first (build a static adapter + serve via nginx, or use `@sveltejs/adapter-node`).

## Deploy & CI

- CI/CD lives in `.github/workflows/ci-cd.yml` (single file). Three jobs: `backend`, `frontend`, `deploy` (deploy only on push to `main`).
- Deploy uses `appleboy/ssh-action` → SSH to Pi via `secrets.SSH_HOST/SSH_USER/SSH_KEY`. **`SSH_HOST` is the Pi's public IP — no DDNS configured**, so home IP changes break deploy with `dial tcp ***:22: i/o timeout`. Past fix: update the GH secret manually.
- `docker-compose.prod.yml` uses `monitor_net` as an `external: true` network. The reverse proxy (managed outside this repo) lives on that network. Creating the network is a one-time `docker network create monitor_net`.
- API prod runs Python 3.11 (`Dockerfile.prod`), dev runs 3.14 (`Dockerfile`). Difference is mostly for asyncmy compile compatibility on ARM64 — don't try to align them without testing.

## Repo conventions

- **All UI text is in French.** Error messages, button labels, comments, commit messages — keep it French.
- **Commit messages** follow Conventional Commits in French: `feat:`, `fix:`, `docs:`, `style:`, `chore:` etc. See recent log for tone.
- **Comments are sparse.** When present, they tend to flag a non-obvious *why* (e.g., legacy migration paths). Don't add docstrings for self-explanatory code.
- **Pre-existing svelte-check warnings** (mouseenter without role, unused props in MonitorCard) are tolerated. Don't fan out fixes for these unless asked — the CI only gates on `npm run lint`, not `npm run check`.
