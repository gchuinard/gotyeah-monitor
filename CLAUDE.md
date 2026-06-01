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

In **dev**, no migrations run (`Dockerfile` starts uvicorn directly); the schema comes from `Base.metadata.create_all`, gated behind `DEBUG=true` in `database.py:init_db`. `create_all` only **creates missing tables**, never adds a column to an existing one. So after adding/altering a model column, recreate the dev volume: `docker compose -f docker-compose.dev.yml down -v` (dev data is disposable). Prod is unaffected — Alembic handles column adds with `_column_exists` guards.

### Full stack
```bash
docker compose -f docker-compose.dev.yml up --build   # API:8000 · front:5173 · MySQL:3307 · Mailpit UI:8025
```

## Architecture

### Backend is monolithic, not a worker + API split

Despite the empty `worker/` directory at the repo root, **there is no separate worker process**. The monitoring loop runs as an asyncio task inside the FastAPI app itself, started in `api/main.py:on_startup` and cancelled in `on_shutdown`. Implications:

- `CHECK_INTERVAL_SECONDS = 600` (10 min), `HISTORY_RETENTION_DAYS = 7`, `INCIDENT_RETENTION_DAYS = 90` are constants in `api/main.py`. Each cycle (`_run_one_cycle`): (1) retention cleanup in its **own** transaction (deletes `monitor_checks` > 7d AND closed `incidents` > 90d); (2) probes all monitors **concurrently** (`asyncio.gather`, bounded by `MAX_CONCURRENT_CHECKS=10`) via `probe_monitor` which touches NO session; (3) applies results sequentially (`apply_check_result`) — so the async session is never used concurrently; (4) `evaluate_alerts` + `_sync_incidents` + `dispatch_alerts`; (5) one commit; (6) heartbeat ping.
- The frontend's `/monitors/:id/history` returns ALL stored checks (no server-side window). The window is a client-side filter in `StatusBar.svelte`.
- Only `type='http'` is actually executed (`probe_monitor` does `client.stream("GET", monitor.url)` **without reading the body** — status code only, anti-OOM). The `Enum('http','ping','port')` has unused values — the UI lets you pick them but the loop ignores non-http.
- Every probed URL goes through `ssrf_guard.url_is_safe()` first (see Anti-SSRF below). `client` uses `follow_redirects=False` so a redirect can't bypass the guard.
- SSL expiry is refreshed every check via a sync `ssl.create_default_context()` call run in an executor (`check_ssl_expiry`). NB: `ssl_expiry_at` is stored tz-naive; code that compares it normalizes to UTC.

### Alerting engine lives in the loop (`api/notifications.py`)

`evaluate_alerts(monitors, now)` runs each cycle AFTER `apply_check_result`, mutating anti-flapping state ON the monitor rows (`consecutive_failures`, `down_since`) and returning `_Alert` objects. Rules: **DOWN** alert after `ALERT_FAILURE_THRESHOLD=2` consecutive failures (not on a single blip), **recovery** only if a down alert was sent, **SSL** at day thresholds `(1,7,14,30)` plus a level `0` = expired so the real-expiry alert fires too. `dispatch_alerts` sends email (via `mail_service`) + optional webhook (`httpx`), and `_Alert.mark_sent()` only flips the "already notified" flags **if the email succeeded** → retry next cycle on failure. Email always-on (to the monitor's owner); webhook is per-user opt-in (`User.alert_webhook_url/_kind`, kinds: discord/slack/ntfy/generic) set in Profil → Notifications. The loop uses `selectinload(Monitor.user)` so the owner email/webhook is available.

### Incidents are derived from the same transition state (`api/main.py:_sync_incidents`)

`Incident` rows open when a monitor is confirmed-down (same threshold as the alert, `started_at = down_since`) and close (`ended_at`) on recovery — independent of email delivery. One "open incidents" query per cycle; the `ended_at IS NULL` guard prevents duplicate open incidents. Unlike `monitor_checks`, incidents survive the 7-day retention (purged only at 90d, closed ones) → they're the basis for long-term history. Endpoint: `GET /monitors/{id}/incidents` (ownership-checked, `limit 50`).

### Uptime % is computed, not stored (`api/routers/monitors.py`)

`_attach_uptime` runs a grouped SQL aggregation (`COUNT`/`SUM(case status='up')`) over `monitor_checks` per window (24h, 7j) using the composite index `ix_monitor_checks_monitor_id_checked_at`, and sets the **non-mapped** `Monitor.uptime_24h/_7d` class attributes (defaults `None`) which `MonitorRead` exposes. MySQL `SUM()` returns `Decimal` — coerce with `float()` before float math (a missed `float()` here previously 500'd the endpoint). Only `list_monitors`/`get_monitor` compute it; other paths serialize `None`. No 30j (retention is 7d) — would need a rollup table.

### Anti-SSRF guard is shared (`api/ssrf_guard.py`)

`url_is_safe(url)` resolves the host and rejects loopback / RFC1918 / link-local (incl. `169.254.169.254`) / reserved / multicast. Applied to **both** monitor probe URLs (the loop) and user webhook URLs (`notifications._send_one` + write-time in `auth.update_me`). Extracted to its own module to avoid a circular import (`main` ↔ `notifications`).

### Rate limiting (`api/rate_limit.py`)

`slowapi` `Limiter` keyed by `X-Forwarded-For` (falls back to client IP). Wired in `main.py` (`app.state.limiter` + `RateLimitExceeded` handler). Decorated routes in `auth.py`: `/login` 10/min, `/register` 5/min, `/forgot-password` 5/min, `/reset-password` 10/min — each needs a `request: Request` param. Behind the reverse proxy, the real client IP must arrive in `X-Forwarded-For`.

### `/health` reflects loop liveness + watchdog + dead-man switch

`/health` is **not** a static `ok`: `_loop_health()` returns 503 if `app.state.last_cycle_at` is older than `LOOP_STALE_AFTER_SECONDS` (3× interval ≈ 30 min). The monitor task has a watchdog (`_on_monitor_task_done` **relaunches** the loop if it dies, unless `app.state.shutting_down`). Optional `HEARTBEAT_URL` env → outbound ping each cycle (dead-man switch, e.g. healthchecks.io). NB: plain Docker does NOT auto-restart on unhealthy — the in-process watchdog is what actually restarts the loop; the 503 is for external observers + the dead-man switch covers total death.

### User isolation is per-route, not via row-level security

Every router handler that touches a `Monitor` re-checks `monitor.user_id == current_user.id` and 403s otherwise. `Monitor.user_id` is nullable, and `update`/`delete` claim ownership of orphan monitors (`user_id is None`) for the current user — a legacy migration path. Don't drop that branch.

### Auth has a transparent SHA-256 → Argon2 rehash

`api/auth.py` keeps a legacy code path: at login, if the stored hash is 64 hex chars (SHA-256), it's verified against SHA-256 and immediately rehashed to Argon2id via passlib. New registrations always use Argon2. Don't simplify the verify branch.

Other auth facts to keep in mind:
- **JWT lib is PyJWT** (not python-jose, which was dropped for CVEs): `import jwt` + `except PyJWTError`. HS256.
- **`SECRET_KEY` fails fast**: missing/<32 chars raises at import in prod (allowed only when `DEBUG=true`). Don't reintroduce a hardcoded fallback.
- **Token versioning**: the JWT carries `tv` = `User.token_version`; `get_current_user` rejects if they differ. `token_version` is bumped on password reset and confirmed email change → invalidates old sessions. So any deploy that changes it logs everyone out.
- **Email/reset/email-change tokens are hashed at rest** (`_hash_token` = SHA-256): the raw token is only emailed; lookups hash the incoming token. A DB dump can't be used to take over accounts.
- **Register is anti-enumeration**: always returns the same generic message (resends verification if unverified, sends a notice if verified) — don't reintroduce a distinct "email already registered" 400.

### Admin is env-based, not a DB column

`ADMIN_EMAILS` env var (comma-separated) is parsed once in `api/routers/admin.py`. There's no `is_admin` field on `User`. Adding an admin = editing the env file + restarting the API.

### Migrations have a stamping smart-start

`api/entrypoint.sh` checks if `users` table exists without an `alembic_version` row — if so, it `alembic stamp 0001` before running `upgrade head`. This protects pre-existing prod DBs that were created by `Base.metadata.create_all` before Alembic was introduced. Be careful when adding migration `0001`-equivalent destructive changes.

Migrations to date: `0001-0004` (initial + email flows), `0005` (`users.token_version`), `0006` (composite index `monitor_checks(monitor_id, checked_at)`), `0007` (alerting state on `monitors` + webhook cols on `users`), `0008` (`incidents` table). New migrations follow the guarded idempotent style (`_column_exists`/`_table_exists`/`_index_exists`). **`create_all` is gated behind `DEBUG`** (`database.py:init_db`): prod schema is Alembic-only; dev uses `create_all`, so adding a column means recreating the dev volume (`docker compose -f docker-compose.dev.yml down -v`).

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
