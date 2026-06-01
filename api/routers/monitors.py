from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
import models
import schemas
from auth import get_current_user

router = APIRouter(prefix="/monitors", tags=["monitors"])


async def _uptime_pct(
    db: AsyncSession, monitor_ids: List[int], cutoff: datetime
) -> Dict[int, Optional[float]]:
    """{monitor_id: % de checks 'up'} sur la fenêtre [cutoff, now] (agrégation SQL,
    via l'index composite (monitor_id, checked_at))."""
    if not monitor_ids:
        return {}
    stmt = (
        select(
            models.MonitorCheck.monitor_id,
            func.count().label("total"),
            func.sum(case((models.MonitorCheck.status == "up", 1), else_=0)).label("up"),
        )
        .where(models.MonitorCheck.monitor_id.in_(monitor_ids))
        .where(models.MonitorCheck.checked_at >= cutoff)
        .group_by(models.MonitorCheck.monitor_id)
    )
    out: Dict[int, Optional[float]] = {}
    for mid, total, up in (await db.execute(stmt)).all():
        # MySQL SUM() renvoie un Decimal -> float() avant le calcul (100.0 * Decimal lève TypeError).
        out[mid] = round(100.0 * float(up or 0) / total, 2) if total else None
    return out


async def _attach_uptime(db: AsyncSession, monitors: List[models.Monitor]) -> None:
    """Calcule et attache uptime_24h / uptime_7d sur les instances (lecture seule)."""
    ids = [m.id for m in monitors]
    now = datetime.now(timezone.utc)
    u24 = await _uptime_pct(db, ids, now - timedelta(hours=24))
    u7 = await _uptime_pct(db, ids, now - timedelta(days=7))
    for m in monitors:
        m.uptime_24h = u24.get(m.id)
        m.uptime_7d = u7.get(m.id)


@router.get("", response_model=List[schemas.MonitorRead])
async def list_monitors(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> List[schemas.MonitorRead]:
    result = await db.execute(
        select(models.Monitor).where(models.Monitor.user_id == current_user.id)
    )
    monitors = list(result.scalars().all())
    await _attach_uptime(db, monitors)
    return monitors


@router.post(
    "", response_model=schemas.MonitorRead, status_code=status.HTTP_201_CREATED
)
async def create_monitor(
    payload: schemas.MonitorCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.MonitorRead:
    monitor = models.Monitor(
        name=payload.name,
        url=str(payload.url),
        type=payload.type,
        expected_status_code=payload.expected_status_code,
        user_id=current_user.id,
    )
    db.add(monitor)
    await db.commit()
    await db.refresh(monitor)
    return monitor


@router.get("/{monitor_id}", response_model=schemas.MonitorRead)
async def get_monitor(
    monitor_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.MonitorRead:
    monitor = await db.get(models.Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if monitor.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    await _attach_uptime(db, [monitor])
    return monitor


@router.put(
    "/{monitor_id}", response_model=schemas.MonitorRead, status_code=status.HTTP_200_OK
)
async def update_monitor(
    monitor_id: int,
    payload: schemas.MonitorUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.MonitorRead:
    monitor = await db.get(models.Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    if monitor.user_id is None:
        monitor.user_id = current_user.id
    elif monitor.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    monitor.name = payload.name
    monitor.url = str(payload.url)
    monitor.type = payload.type
    monitor.expected_status_code = payload.expected_status_code

    await db.commit()
    await db.refresh(monitor)
    return monitor


@router.delete("/{monitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_monitor(
    monitor_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    monitor = await db.get(models.Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    if monitor.user_id is None:
        monitor.user_id = current_user.id
    elif monitor.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    await db.delete(monitor)
    await db.commit()
    return None


@router.get("/{monitor_id}/history", response_model=List[schemas.MonitorCheckRead])
async def get_monitor_history(
    monitor_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> List[schemas.MonitorCheckRead]:
    monitor = await db.get(models.Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if monitor.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    result = await db.execute(
        select(models.MonitorCheck)
        .where(models.MonitorCheck.monitor_id == monitor_id)
        .order_by(models.MonitorCheck.checked_at.asc())
    )
    return list(result.scalars().all())
