import asyncio
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from fastapi.middleware.cors import CORSMiddleware

from database import AsyncSessionLocal, init_db
import models
from routers import monitors
from auth import router as auth_router

app = FastAPI()


CHECK_INTERVAL_SECONDS = 30


async def check_single_monitor(
    monitor: models.Monitor, client: httpx.AsyncClient
) -> None:
    start = asyncio.get_event_loop().time()
    status_code: int | None = None
    try:
        response = await client.get(monitor.url, timeout=10.0)
        status_code = response.status_code
        latency_ms = int((asyncio.get_event_loop().time() - start) * 1000)

        monitor.last_latency_ms = latency_ms
        monitor.status = (
            "up" if status_code == monitor.expected_status_code else "down"
        )
    except Exception:
        monitor.last_latency_ms = None
        monitor.status = "down"
        status_code = None

    monitor.last_status_code = status_code
    monitor.last_checked_at = datetime.now(timezone.utc)


async def monitor_loop() -> None:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        while True:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(models.Monitor))
                monitors = result.scalars().all()

                for monitor in monitors:
                    await check_single_monitor(monitor, client)

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
    allow_origins=["*"],  # Autoriser toutes les origines (DEV/PROD ok)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.head("/health")
async def health_head():
    return


app.include_router(auth_router)
app.include_router(monitors.router)
