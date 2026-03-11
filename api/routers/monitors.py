from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
import models
import schemas
from auth import get_current_user

router = APIRouter(prefix="/monitors", tags=["monitors"])


@router.get("/", response_model=List[schemas.MonitorRead])
async def list_monitors(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> List[schemas.MonitorRead]:
    result = await db.execute(
        select(models.Monitor).where(models.Monitor.user_id == current_user.id)
    )
    monitors = result.scalars().all()
    return list(monitors)


@router.post(
    "/", response_model=schemas.MonitorRead, status_code=status.HTTP_201_CREATED
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

    # Si le monitor est ancien et n'a pas encore d'utilisateur associé,
    # on l'associe au user courant. Sinon on vérifie l'appartenance.
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

    # Même logique que pour update : on permet de "récupérer" les vieux monitors
    # qui n'avaient pas encore de user_id.
    if monitor.user_id is None:
        monitor.user_id = current_user.id
    elif monitor.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    await db.delete(monitor)
    await db.commit()
    return None
