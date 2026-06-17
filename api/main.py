import asyncio
import logging
import os
import ssl
import socket
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select, delete, func, case, insert
from sqlalchemy.orm import selectinload

from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy.ext.asyncio import AsyncSession

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from database import AsyncSessionLocal, init_db
import models
from rate_limit import limiter
from ssrf_guard import url_is_safe, host_is_safe
from notifications import evaluate_alerts, dispatch_alerts, ALERT_FAILURE_THRESHOLD
from routers import monitors
from routers import groups
from routers import admin
from auth import router as auth_router

app = FastAPI(redirect_slashes=False)

# Rate limiting (anti brute-force / abus d'envoi d'emails) — voir auth.py pour les routes décorées.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


_DEBUG = os.getenv("DEBUG", "false").lower() == "true"


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # La stacktrace est journalisée côté serveur, jamais renvoyée au client (même en
    # debug) : elle ne doit pas fuiter via la réponse HTTP.
    logging.getLogger("gotyeah.api").exception(
        "Unhandled exception on %s %s", request.method, request.url.path
    )
    # Ce handler (Starlette ServerErrorMiddleware, niveau le plus externe) court-circuite
    # le CORSMiddleware : on remet donc l'en-tête CORS à la main, en cohérence avec la
    # politique globale allow_origins=["*"] (credentials désactivés) — sinon le front,
    # servi sur un autre domaine, ne pourrait pas lire les réponses 500.
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc) if _DEBUG else "Internal server error"},
        headers={"Access-Control-Allow-Origin": "*"},
    )


CHECK_INTERVAL_SECONDS = 600  # intervalle de check par défaut (par monitor, surchargeable)
# La boucle se réveille à cette cadence et ne sonde que les monitors "dus" — permet des
# intervalles par monitor plus courts que l'ancien cycle unique de 600s.
TICK_INTERVAL_SECONDS = 60
# Cadence (lente) du nettoyage de rétention et du heartbeat — pas à chaque tick.
RETENTION_INTERVAL_SECONDS = 600
# Taille max de corps lue pour le check par mot-clé (anti-OOM sur le Pi).
MAX_BODY_BYTES = 256 * 1024
# Rollup uptime : nombre de jours complets récents recalculés à chaque agrégation
# quotidienne. < HISTORY_RETENTION_DAYS (7) -> aucun jour n'est purgé avant d'être agrégé.
ROLLUP_LOOKBACK_DAYS = 3
HISTORY_RETENTION_DAYS = 7
# Les incidents (clos) sont conservés bien plus longtemps que les checks (historique
# long terme), mais bornés pour éviter une croissance illimitée de la table.
INCIDENT_RETENTION_DAYS = 90
MAX_CONCURRENT_CHECKS = 10
# La boucle est considérée "bloquée" si aucun cycle n'a abouti depuis 3 intervalles.
LOOP_STALE_AFTER_SECONDS = CHECK_INTERVAL_SECONDS * 3
# Dead-man switch : ping sortant à chaque cycle vers un service tiers (ex. healthchecks.io).
# C'est un réglage opérateur (variable d'env), pas une URL utilisateur -> pas de garde SSRF.
HEARTBEAT_URL = os.getenv("HEARTBEAT_URL", "").strip()

logger = logging.getLogger("monitor")


def _fetch_ssl_expiry(hostname: str, port: int = 443) -> Optional[datetime]:
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                expiry_str = cert["notAfter"]  # e.g. "Apr 10 12:00:00 2026 GMT"
                return datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z")
    except Exception:
        return None


async def check_ssl_expiry(url: str) -> Optional[datetime]:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return None
    hostname = parsed.hostname
    port = parsed.port or 443
    if not hostname:
        return None
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_ssl_expiry, hostname, port)


async def probe_port(host: str, port: int, timeout: float = 10.0) -> bool:
    """Test de joignabilité par TCP connect (pas d'ICMP : l'API tourne en non-root)."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


async def probe_monitor(monitor: models.Monitor, client: httpx.AsyncClient) -> dict:
    """Effectue le check réseau SANS toucher la session (sûr à lancer en parallèle).
    Renvoie le résultat ; l'application en base se fait séquentiellement ensuite."""
    start = asyncio.get_event_loop().time()
    status_code: int | None = None
    latency_ms: int | None = None
    new_status = "down"
    ssl_expiry: Optional[datetime] = None

    # --- Types ping/port : simple TCP connect, gardé par le SSRF host-check ---
    if monitor.type in ("ping", "port"):
        parsed = urlparse(monitor.url)
        host = parsed.hostname
        if monitor.type == "port":
            port = monitor.port or parsed.port
        else:  # ping : joignabilité du host sur le port de l'URL (ou 443/80)
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if host and port and await host_is_safe(host, port):
            ok = await probe_port(host, port)
            latency_ms = int((asyncio.get_event_loop().time() - start) * 1000)
            new_status = "up" if ok else "down"
        elif not (host and port):
            logger.warning("Monitor %s ignoré : host/port manquant", monitor.id)
        else:
            logger.warning("Monitor %s ignoré : cible interne/non autorisée", monitor.id)
        return {"status": new_status, "status_code": None, "latency_ms": latency_ms, "ssl_expiry": None}

    # --- Type http : GET (+ check de contenu optionnel) ---
    if await url_is_safe(monitor.url):
        need_body = bool(monitor.keyword)
        try:
            # Sans mot-clé : on ne lit PAS le corps (stream) — seul le code compte,
            # ce qui évite de charger une réponse énorme (anti-OOM). Avec mot-clé :
            # lecture BORNÉE à MAX_BODY_BYTES.
            async with client.stream("GET", monitor.url, timeout=10.0) as response:
                status_code = response.status_code
                body_ok = True
                if need_body:
                    total = 0
                    chunks: list[bytes] = []
                    async for chunk in response.aiter_bytes():
                        chunks.append(chunk)
                        total += len(chunk)
                        if total >= MAX_BODY_BYTES:
                            break
                    text = b"".join(chunks)[:MAX_BODY_BYTES].decode("utf-8", errors="ignore")
                    found = monitor.keyword in text
                    body_ok = found if monitor.keyword_mode == "present" else (not found)
            latency_ms = int((asyncio.get_event_loop().time() - start) * 1000)
            code_ok = status_code == monitor.expected_status_code
            new_status = "up" if (code_ok and body_ok) else "down"
        except Exception:
            pass
        ssl_expiry = await check_ssl_expiry(monitor.url)
    else:
        # URL pointant vers une cible interne/non autorisée : on ne la sonde pas (anti-SSRF).
        logger.warning(
            "Monitor %s ignoré : URL vers une cible interne/non autorisée (%s)",
            monitor.id,
            monitor.url,
        )

    return {
        "status": new_status,
        "status_code": status_code,
        "latency_ms": latency_ms,
        "ssl_expiry": ssl_expiry,
    }


def apply_check_result(
    monitor: models.Monitor, result: dict, now: datetime, session: AsyncSession
) -> None:
    monitor.status = result["status"]
    monitor.last_latency_ms = result["latency_ms"]
    monitor.last_status_code = result["status_code"]
    monitor.last_checked_at = now
    monitor.ssl_expiry_at = result["ssl_expiry"]
    session.add(models.MonitorCheck(
        monitor_id=monitor.id,
        status=result["status"],
        latency_ms=result["latency_ms"],
        checked_at=now,
    ))


async def _sync_incidents(
    session: AsyncSession, monitors: "list[models.Monitor]", now: datetime
) -> None:
    """Ouvre un incident quand un monitor est confirmé down (même seuil que l'alerte),
    le ferme au rétablissement. Indépendant de l'envoi d'email, et non purgé par la
    rétention (≠ monitor_checks) -> base de l'historique long terme."""
    ids = [m.id for m in monitors]
    if not ids:
        return
    res = await session.execute(
        select(models.Incident).where(
            models.Incident.monitor_id.in_(ids),
            models.Incident.ended_at.is_(None),
        )
    )
    open_by_monitor = {inc.monitor_id: inc for inc in res.scalars().all()}
    for m in monitors:
        confirmed_down = (
            m.status == "down" and m.consecutive_failures >= ALERT_FAILURE_THRESHOLD
        )
        existing = open_by_monitor.get(m.id)
        if confirmed_down and existing is None:
            session.add(
                models.Incident(
                    monitor_id=m.id,
                    started_at=m.down_since or now,
                    last_status_code=m.last_status_code,
                )
            )
        elif m.status == "up" and existing is not None:
            existing.ended_at = now


def _is_due(monitor: models.Monitor, now: datetime) -> bool:
    """True si le monitor doit être sondé maintenant (jamais checké, ou intervalle écoulé)."""
    if monitor.last_checked_at is None:
        return True
    interval = monitor.check_interval_seconds or CHECK_INTERVAL_SECONDS
    last = monitor.last_checked_at
    if last.tzinfo is None:  # MySQL renvoie parfois un datetime naïf
        last = last.replace(tzinfo=timezone.utc)
    return (now - last).total_seconds() >= interval


async def _run_retention() -> None:
    # Nettoyage de rétention dans SA PROPRE transaction : un échec des checks ne doit
    # pas annuler le nettoyage, et inversement.
    try:
        async with AsyncSessionLocal() as session:
            cutoff = datetime.now(timezone.utc) - timedelta(days=HISTORY_RETENTION_DAYS)
            await session.execute(
                delete(models.MonitorCheck).where(models.MonitorCheck.checked_at < cutoff)
            )
            # Purge des incidents CLOS trop anciens (les incidents en cours, ended_at IS
            # NULL, ne sont jamais supprimés).
            inc_cutoff = datetime.now(timezone.utc) - timedelta(days=INCIDENT_RETENTION_DAYS)
            await session.execute(
                delete(models.Incident).where(
                    models.Incident.ended_at.is_not(None),
                    models.Incident.ended_at < inc_cutoff,
                )
            )
            await session.commit()
    except Exception:
        logger.exception("Échec du nettoyage de rétention")


async def _run_rollup(now: datetime) -> None:
    """Agrège les jours COMPLETS récents dans monitor_uptime_daily (delete+insert
    idempotent), AVANT que la rétention 7j ne purge monitor_checks. Le jour courant
    (incomplet) est exclu. Lookback (3) < rétention (7) -> jamais de perte de données."""
    today = now.date()
    start_day = today - timedelta(days=ROLLUP_LOOKBACK_DAYS)
    start_dt = datetime(start_day.year, start_day.month, start_day.day, tzinfo=timezone.utc)
    end_dt = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                delete(models.MonitorUptimeDaily).where(
                    models.MonitorUptimeDaily.day >= start_day,
                    models.MonitorUptimeDaily.day < today,
                )
            )
            day_col = func.date(models.MonitorCheck.checked_at)
            agg = (
                select(
                    models.MonitorCheck.monitor_id,
                    day_col.label("day"),
                    func.sum(case((models.MonitorCheck.status == "up", 1), else_=0)).label("up_count"),
                    func.count().label("total_count"),
                )
                .where(
                    models.MonitorCheck.checked_at >= start_dt,
                    models.MonitorCheck.checked_at < end_dt,
                )
                .group_by(models.MonitorCheck.monitor_id, day_col)
            )
            await session.execute(
                insert(models.MonitorUptimeDaily).from_select(
                    ["monitor_id", "day", "up_count", "total_count"], agg
                )
            )
            await session.commit()
    except Exception:
        logger.exception("Échec du rollup uptime quotidien")


async def _run_one_cycle(client: httpx.AsyncClient) -> None:
    async with AsyncSessionLocal() as session:
        try:
            # selectinload(user) : la boucle a besoin de l'email/webhook de l'owner pour alerter.
            result = await session.execute(
                select(models.Monitor).options(selectinload(models.Monitor.user))
            )
            all_monitors = list(result.scalars().all())

            now = datetime.now(timezone.utc)
            # Intervalle par monitor : on ne sonde que les monitors "dus" ce tick.
            due = [m for m in all_monitors if _is_due(m, now)]
            if not due:
                return

            # Checks réseau en parallèle (bornés), puis application séquentielle en base
            # (la session async n'est jamais utilisée de façon concurrente).
            sem = asyncio.Semaphore(MAX_CONCURRENT_CHECKS)

            async def _probe(m: models.Monitor) -> dict:
                async with sem:
                    return await probe_monitor(m, client)

            results = await asyncio.gather(*[_probe(m) for m in due])

            for monitor, res in zip(due, results):
                apply_check_result(monitor, res, now, session)

            # Alerting : UNIQUEMENT sur les monitors checkés ce tick — sinon on
            # déclencherait de fausses transitions/incidents sur des monitors non sondés.
            alerts = evaluate_alerts(due, now)
            await _sync_incidents(session, due, now)
            await dispatch_alerts(client, alerts)

            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Échec de l'itération de monitoring (rollback)")


async def _heartbeat(client: httpx.AsyncClient) -> None:
    """Dead-man switch : signale à un service tiers que la boucle tourne (best-effort)."""
    if not HEARTBEAT_URL:
        return
    try:
        await client.get(HEARTBEAT_URL, timeout=10.0)
    except Exception:
        logger.warning("Échec du ping heartbeat (dead-man switch)")


async def monitor_loop() -> None:
    # follow_redirects=False : une redirection vers une cible interne contournerait
    # le contrôle anti-SSRF fait sur l'URL d'origine.
    # NB : last_cycle_at n'est PAS posé ici (au démarrage) — sinon un crash-loop qui
    # relance la boucle sans jamais finir un cycle garderait /health vert à tort.
    async with httpx.AsyncClient(follow_redirects=False) as client:
        last_retention: float | None = None
        last_heartbeat: float | None = None
        last_rollup_day = None
        while True:
            mono = asyncio.get_event_loop().time()
            try:
                # Rollup uptime : une fois par jour (UTC), AVANT la rétention.
                today = datetime.now(timezone.utc).date()
                if last_rollup_day != today:
                    await _run_rollup(datetime.now(timezone.utc))
                    last_rollup_day = today
                # Rétention : cadence lente, pas à chaque tick de 60s.
                if last_retention is None or mono - last_retention >= RETENTION_INTERVAL_SECONDS:
                    await _run_retention()
                    last_retention = mono
                await _run_one_cycle(client)
                # Liveness : le tick a abouti (même si aucun monitor n'était dû). On
                # réarme aussi le backoff de redémarrage.
                app.state.last_cycle_at = datetime.now(timezone.utc)
                app.state.restart_count = 0
            except Exception:
                logger.exception("Erreur inattendue dans la boucle de monitoring")
            # Heartbeat (dead-man switch) : cadence lente également.
            if last_heartbeat is None or asyncio.get_event_loop().time() - last_heartbeat >= RETENTION_INTERVAL_SECONDS:
                await _heartbeat(client)
                last_heartbeat = asyncio.get_event_loop().time()
            await asyncio.sleep(TICK_INTERVAL_SECONDS)


def _spawn_monitor_loop() -> None:
    if getattr(app.state, "shutting_down", False):
        return
    task = asyncio.create_task(monitor_loop())
    task.add_done_callback(_on_monitor_task_done)
    app.state.monitor_task = task


def _on_monitor_task_done(task: "asyncio.Task[None]") -> None:
    # Watchdog : relance la boucle si elle meurt (hors arrêt de l'app), AVEC un backoff
    # exponentiel borné — sinon un échec persistant avant la boucle (ex. épuisement de
    # ressources sur le Pi) provoquerait une boucle de redémarrage serrée. Le compteur
    # est remis à 0 dès qu'un cycle aboutit (monitor_loop).
    if getattr(app.state, "shutting_down", False) or task.cancelled():
        return
    exc = task.exception()
    if exc is None:
        return
    n = getattr(app.state, "restart_count", 0)
    app.state.restart_count = n + 1
    delay = min(60, 2 ** min(n, 6))  # 1, 2, 4, … plafonné à 60 s
    logger.error(
        "Boucle de monitoring arrêtée — redémarrage dans %ss", delay, exc_info=exc
    )
    asyncio.get_running_loop().call_later(delay, _spawn_monitor_loop)


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()
    app.state.shutting_down = False
    app.state.last_cycle_at = None
    app.state.loop_started_at = datetime.now(timezone.utc)
    app.state.restart_count = 0
    task = asyncio.create_task(monitor_loop())
    task.add_done_callback(_on_monitor_task_done)
    app.state.monitor_task = task


@app.on_event("shutdown")
async def on_shutdown() -> None:
    app.state.shutting_down = True
    task = getattr(app.state, "monitor_task", None)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _loop_health() -> tuple[bool, dict]:
    """Liveness réelle de la boucle de monitoring (et pas un simple 'ok' statique)."""
    now = datetime.now(timezone.utc)
    last = getattr(app.state, "last_cycle_at", None)
    if last is not None:
        age = (now - last).total_seconds()
        ok = age < LOOP_STALE_AFTER_SECONDS
        return ok, {
            "status": "ok" if ok else "degraded",
            "monitor_loop": "alive" if ok else "stale",
            "last_cycle_at": last.isoformat(),
            "seconds_since_last_cycle": round(age),
        }
    # Aucun cycle abouti : grâce au démarrage, MAIS devient stale si ça dure trop
    # (ex. crash-loop avant le 1er cycle) — loop_started_at n'est PAS réinitialisé aux relances.
    started = getattr(app.state, "loop_started_at", None)
    grace = started is None or (now - started).total_seconds() < LOOP_STALE_AFTER_SECONDS
    return grace, {
        "status": "starting" if grace else "degraded",
        "monitor_loop": "starting" if grace else "stale",
        "last_cycle_at": None,
        "seconds_since_last_cycle": None,
    }


@app.get("/health")
async def health():
    ok, body = _loop_health()
    return JSONResponse(status_code=200 if ok else 503, content=body)


@app.head("/health")
async def health_head():
    ok, _ = _loop_health()
    return JSONResponse(status_code=200 if ok else 503, content=None)


app.include_router(auth_router)
app.include_router(monitors.router)
app.include_router(groups.router)
app.include_router(admin.router)
