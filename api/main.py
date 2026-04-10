import asyncio
import ssl
import socket
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI
from sqlalchemy import select, delete

from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal, init_db
import models
from routers import monitors
from routers import admin
from auth import router as auth_router

app = FastAPI()


CHECK_INTERVAL_SECONDS = 600
HISTORY_RETENTION_DAYS = 7


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

    try:
        response = await client.get(monitor.url, timeout=10.0)
        status_code = response.status_code
        latency_ms = int((asyncio.get_event_loop().time() - start) * 1000)
        new_status = "up" if status_code == monitor.expected_status_code else "down"
    except Exception:
        pass

    now = datetime.now(timezone.utc)
    monitor.status = new_status
    monitor.last_latency_ms = latency_ms
    monitor.last_status_code = status_code
    monitor.last_checked_at = now
    monitor.ssl_expiry_at = await check_ssl_expiry(monitor.url)

    session.add(models.MonitorCheck(
        monitor_id=monitor.id,
        status=new_status,
        latency_ms=latency_ms,
        checked_at=now,
    ))


async def monitor_loop() -> None:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        while True:
            async with AsyncSessionLocal() as session:
                # Cleanup: supprimer les checks de plus de 7 jours
                cutoff = datetime.now(timezone.utc) - timedelta(days=HISTORY_RETENTION_DAYS)
                await session.execute(
                    delete(models.MonitorCheck).where(models.MonitorCheck.checked_at < cutoff)
                )

                result = await session.execute(select(models.Monitor))
                all_monitors = result.scalars().all()

                for monitor in all_monitors:
                    await check_single_monitor(monitor, client, session)

                await session.commit()

            await asyncio.sleep(CHECK_INTERVAL_SECONDS)


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()
    app.state.monitor_task = asyncio.create_task(monitor_loop())


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
