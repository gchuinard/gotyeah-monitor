import asyncio
import ipaddress
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
from sqlalchemy import select, delete

from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy.ext.asyncio import AsyncSession

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from database import AsyncSessionLocal, init_db
import models
from rate_limit import limiter
from routers import monitors
from routers import admin
from auth import router as auth_router

app = FastAPI(redirect_slashes=False)

# Rate limiting (anti brute-force / abus d'envoi d'emails) — voir auth.py pour les routes décorées.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


_DEBUG = os.getenv("DEBUG", "false").lower() == "true"


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    import traceback
    content: dict = {"detail": str(exc) if _DEBUG else "Internal server error"}
    if _DEBUG:
        content["traceback"] = traceback.format_exc()
    return JSONResponse(
        status_code=500,
        content=content,
        headers={"Access-Control-Allow-Origin": "*"},
    )


CHECK_INTERVAL_SECONDS = 600
HISTORY_RETENTION_DAYS = 7

logger = logging.getLogger("monitor")


def _ip_is_blocked(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _host_resolves_to_blocked_ip(hostname: str, port: int) -> bool:
    """Anti-SSRF : True si l'hôte résout (même partiellement) vers une IP interne/privée."""
    try:
        infos = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except Exception:
        return True  # résolution impossible -> on bloque par précaution
    return any(_ip_is_blocked(info[4][0]) for info in infos)


async def url_is_safe(url: str) -> bool:
    """Refuse une URL de monitor qui ciblerait le réseau interne (loopback, RFC1918,
    link-local/métadonnées cloud, etc.). Résolution faite au moment du check."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = parsed.hostname
    if not hostname:
        return False
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    loop = asyncio.get_event_loop()
    return not await loop.run_in_executor(
        None, _host_resolves_to_blocked_ip, hostname, port
    )


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


async def check_single_monitor(
    monitor: models.Monitor, client: httpx.AsyncClient, session: AsyncSession
) -> None:
    start = asyncio.get_event_loop().time()
    status_code: int | None = None
    latency_ms: int | None = None
    new_status = "down"
    ssl_expiry: Optional[datetime] = None

    if await url_is_safe(monitor.url):
        try:
            response = await client.get(monitor.url, timeout=10.0)
            status_code = response.status_code
            latency_ms = int((asyncio.get_event_loop().time() - start) * 1000)
            new_status = "up" if status_code == monitor.expected_status_code else "down"
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

    now = datetime.now(timezone.utc)
    monitor.status = new_status
    monitor.last_latency_ms = latency_ms
    monitor.last_status_code = status_code
    monitor.last_checked_at = now
    monitor.ssl_expiry_at = ssl_expiry

    session.add(models.MonitorCheck(
        monitor_id=monitor.id,
        status=new_status,
        latency_ms=latency_ms,
        checked_at=now,
    ))


async def monitor_loop() -> None:
    # follow_redirects=False : une redirection vers une cible interne contournerait
    # le contrôle anti-SSRF fait sur l'URL d'origine.
    async with httpx.AsyncClient(follow_redirects=False) as client:
        while True:
            # Une itération ne doit jamais tuer la boucle : on isole chaque cycle.
            try:
                async with AsyncSessionLocal() as session:
                    try:
                        # Cleanup: supprimer les checks de plus de 7 jours
                        cutoff = datetime.now(timezone.utc) - timedelta(
                            days=HISTORY_RETENTION_DAYS
                        )
                        await session.execute(
                            delete(models.MonitorCheck).where(
                                models.MonitorCheck.checked_at < cutoff
                            )
                        )

                        result = await session.execute(select(models.Monitor))
                        all_monitors = result.scalars().all()

                        for monitor in all_monitors:
                            await check_single_monitor(monitor, client, session)

                        await session.commit()
                    except Exception:
                        await session.rollback()
                        logger.exception("Échec de l'itération de monitoring (rollback)")
            except Exception:
                logger.exception("Erreur inattendue dans la boucle de monitoring")

            await asyncio.sleep(CHECK_INTERVAL_SECONDS)


def _on_monitor_task_done(task: "asyncio.Task[None]") -> None:
    # Filet de sécurité : si la boucle meurt malgré tout, on le journalise
    # au lieu de laisser l'exception disparaître silencieusement au GC.
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error(
            "La boucle de monitoring s'est arrêtée sur une exception", exc_info=exc
        )


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()
    task = asyncio.create_task(monitor_loop())
    task.add_done_callback(_on_monitor_task_done)
    app.state.monitor_task = task


@app.on_event("shutdown")
async def on_shutdown() -> None:
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


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.head("/health")
async def health_head():
    return


app.include_router(auth_router)
app.include_router(monitors.router)
app.include_router(admin.router)
