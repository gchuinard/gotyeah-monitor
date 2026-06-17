from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
import models
import schemas
from auth import get_current_user, get_user_flexible

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


async def _rollup_pct(
    db: AsyncSession, monitor_ids: List[int], since_day
) -> Dict[int, Optional[float]]:
    """{monitor_id: % d'uptime} depuis `since_day` (inclus), via la table de rollup
    quotidien (monitor_uptime_daily) — pour les fenêtres longues (30j/90j)."""
    if not monitor_ids:
        return {}
    stmt = (
        select(
            models.MonitorUptimeDaily.monitor_id,
            func.sum(models.MonitorUptimeDaily.total_count).label("total"),
            func.sum(models.MonitorUptimeDaily.up_count).label("up"),
        )
        .where(models.MonitorUptimeDaily.monitor_id.in_(monitor_ids))
        .where(models.MonitorUptimeDaily.day >= since_day)
        .group_by(models.MonitorUptimeDaily.monitor_id)
    )
    out: Dict[int, Optional[float]] = {}
    for mid, total, up in (await db.execute(stmt)).all():
        total = float(total or 0)
        out[mid] = round(100.0 * float(up or 0) / total, 2) if total else None
    return out


async def _attach_uptime(db: AsyncSession, monitors: List[models.Monitor]) -> None:
    """Attache uptime_24h/_7d (depuis monitor_checks) et uptime_30d/_90d (depuis le rollup)."""
    ids = [m.id for m in monitors]
    now = datetime.now(timezone.utc)
    today = now.date()
    u24 = await _uptime_pct(db, ids, now - timedelta(hours=24))
    u7 = await _uptime_pct(db, ids, now - timedelta(days=7))
    u30 = await _rollup_pct(db, ids, today - timedelta(days=30))
    u90 = await _rollup_pct(db, ids, today - timedelta(days=90))
    for m in monitors:
        m.uptime_24h = u24.get(m.id)
        m.uptime_7d = u7.get(m.id)
        m.uptime_30d = u30.get(m.id)
        m.uptime_90d = u90.get(m.id)


async def _attach_maintenance(db: AsyncSession, monitors: List[models.Monitor]) -> None:
    """Marque in_maintenance=True les monitors couverts par une fenêtre active maintenant."""
    ids = [m.id for m in monitors]
    if not ids:
        return
    now = datetime.now(timezone.utc)
    res = await db.execute(
        select(models.MaintenanceWindow.monitor_id).where(
            models.MaintenanceWindow.monitor_id.in_(ids),
            models.MaintenanceWindow.start_at <= now,
            models.MaintenanceWindow.end_at >= now,
        )
    )
    active = {row[0] for row in res.all()}
    for m in monitors:
        m.in_maintenance = m.id in active


async def _validate_group(
    db: AsyncSession, group_id: Optional[int], user: models.User
) -> None:
    """Si un group_id est fourni, vérifie qu'il existe et appartient à l'utilisateur."""
    if group_id is None:
        return
    group = await db.get(models.MonitorGroup, group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Groupe introuvable")
    if group.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Groupe non autorisé")


@router.get("", response_model=List[schemas.MonitorRead])
async def list_monitors(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_user_flexible),
) -> List[schemas.MonitorRead]:
    result = await db.execute(
        select(models.Monitor).where(models.Monitor.user_id == current_user.id)
    )
    monitors = list(result.scalars().all())
    await _attach_uptime(db, monitors)
    await _attach_maintenance(db, monitors)
    return monitors


@router.post(
    "", response_model=schemas.MonitorRead, status_code=status.HTTP_201_CREATED
)
async def create_monitor(
    payload: schemas.MonitorCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.MonitorRead:
    await _validate_group(db, payload.group_id, current_user)
    monitor = models.Monitor(
        name=payload.name,
        url=str(payload.url),
        type=payload.type,
        expected_status_code=payload.expected_status_code,
        check_interval_seconds=payload.check_interval_seconds,
        keyword=payload.keyword,
        keyword_mode=payload.keyword_mode,
        latency_threshold_ms=payload.latency_threshold_ms,
        port=payload.port,
        group_id=payload.group_id,
        is_public=payload.is_public,
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
    current_user: models.User = Depends(get_user_flexible),
) -> schemas.MonitorRead:
    monitor = await db.get(models.Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if monitor.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    await _attach_uptime(db, [monitor])
    await _attach_maintenance(db, [monitor])
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

    await _validate_group(db, payload.group_id, current_user)

    monitor.name = payload.name
    monitor.url = str(payload.url)
    monitor.type = payload.type
    monitor.expected_status_code = payload.expected_status_code
    monitor.check_interval_seconds = payload.check_interval_seconds
    monitor.keyword = payload.keyword
    monitor.keyword_mode = payload.keyword_mode
    monitor.latency_threshold_ms = payload.latency_threshold_ms
    monitor.port = payload.port
    monitor.group_id = payload.group_id
    monitor.is_public = payload.is_public

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
    current_user: models.User = Depends(get_user_flexible),
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


@router.get("/{monitor_id}/incidents", response_model=List[schemas.IncidentRead])
async def get_monitor_incidents(
    monitor_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_user_flexible),
) -> List[schemas.IncidentRead]:
    monitor = await db.get(models.Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if monitor.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    result = await db.execute(
        select(models.Incident)
        .where(models.Incident.monitor_id == monitor_id)
        .order_by(models.Incident.started_at.desc())
        .limit(50)
    )
    return list(result.scalars().all())


@router.get("/{monitor_id}/sla", response_model=List[schemas.SlaMonth])
async def get_monitor_sla(
    monitor_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_user_flexible),
) -> List[schemas.SlaMonth]:
    """Uptime mensuel (12 derniers mois) depuis le rollup quotidien."""
    monitor = await db.get(models.Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if monitor.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    month = func.date_format(models.MonitorUptimeDaily.day, "%Y-%m")
    stmt = (
        select(
            month.label("month"),
            func.sum(models.MonitorUptimeDaily.total_count).label("total"),
            func.sum(models.MonitorUptimeDaily.up_count).label("up"),
        )
        .where(models.MonitorUptimeDaily.monitor_id == monitor_id)
        .group_by(month)
        .order_by(month.desc())
        .limit(12)
    )
    out: List[schemas.SlaMonth] = []
    for mo, total, up in (await db.execute(stmt)).all():
        total = float(total or 0)
        pct = round(100.0 * float(up or 0) / total, 2) if total else None
        out.append(schemas.SlaMonth(month=mo, uptime=pct))
    return out


@router.patch("/{monitor_id}/incidents/{incident_id}", response_model=schemas.IncidentRead)
async def update_incident(
    monitor_id: int,
    incident_id: int,
    payload: schemas.IncidentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.IncidentRead:
    """Acquitte un incident et/ou enregistre un post-mortem."""
    await _owned_monitor(db, monitor_id, current_user)
    incident = await db.get(models.Incident, incident_id)
    if not incident or incident.monitor_id != monitor_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if payload.acknowledged is not None:
        incident.acknowledged_at = datetime.now(timezone.utc) if payload.acknowledged else None
    if payload.postmortem is not None:
        incident.postmortem = payload.postmortem.strip() or None
    await db.commit()
    await db.refresh(incident)
    return incident


async def _owned_monitor(db: AsyncSession, monitor_id: int, current_user: models.User) -> models.Monitor:
    monitor = await db.get(models.Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if monitor.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return monitor


@router.get("/{monitor_id}/maintenance", response_model=List[schemas.MaintenanceWindowRead])
async def list_maintenance(
    monitor_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> List[schemas.MaintenanceWindowRead]:
    await _owned_monitor(db, monitor_id, current_user)
    res = await db.execute(
        select(models.MaintenanceWindow)
        .where(models.MaintenanceWindow.monitor_id == monitor_id)
        .order_by(models.MaintenanceWindow.start_at.desc())
        .limit(50)
    )
    return list(res.scalars().all())


@router.post(
    "/{monitor_id}/maintenance",
    response_model=schemas.MaintenanceWindowRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_maintenance(
    monitor_id: int,
    payload: schemas.MaintenanceWindowCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.MaintenanceWindowRead:
    await _owned_monitor(db, monitor_id, current_user)
    window = models.MaintenanceWindow(
        monitor_id=monitor_id,
        start_at=payload.start_at,
        end_at=payload.end_at,
        label=payload.label,
    )
    db.add(window)
    await db.commit()
    await db.refresh(window)
    return window


@router.delete("/{monitor_id}/maintenance/{window_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_maintenance(
    monitor_id: int,
    window_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    await _owned_monitor(db, monitor_id, current_user)
    window = await db.get(models.MaintenanceWindow, window_id)
    if not window or window.monitor_id != monitor_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.delete(window)
    await db.commit()
    return None
