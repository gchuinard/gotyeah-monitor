import os
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
import models
import schemas
from auth import get_current_user

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_EMAILS = set(
    e.strip() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()
)


async def get_current_admin(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    if current_user.email not in ADMIN_EMAILS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return current_user


@router.get("/check")
async def check_admin(
    current_user: models.User = Depends(get_current_user),
) -> dict:
    return {"is_admin": current_user.email in ADMIN_EMAILS}


@router.put("/monitors/{monitor_id}", response_model=schemas.MonitorRead)
async def admin_update_monitor(
    monitor_id: int,
    payload: schemas.MonitorUpdate,
    db: AsyncSession = Depends(get_db),
    _: models.User = Depends(get_current_admin),
) -> schemas.MonitorRead:
    monitor = await db.get(models.Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    monitor.name = payload.name
    monitor.url = str(payload.url)
    monitor.type = payload.type
    monitor.expected_status_code = payload.expected_status_code
    await db.commit()
    await db.refresh(monitor)
    return monitor


@router.delete("/monitors/{monitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_monitor(
    monitor_id: int,
    db: AsyncSession = Depends(get_db),
    _: models.User = Depends(get_current_admin),
) -> None:
    monitor = await db.get(models.Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.delete(monitor)
    await db.commit()


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: models.User = Depends(get_current_admin),
) -> None:
    user = await db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    result = await db.execute(select(models.Monitor).where(models.Monitor.user_id == user_id))
    monitors = result.scalars().all()
    for monitor in monitors:
        await db.delete(monitor)
    await db.delete(user)
    await db.commit()


@router.get("/users", response_model=List[schemas.UserWithMonitors])
async def list_users_with_monitors(
    db: AsyncSession = Depends(get_db),
    _: models.User = Depends(get_current_admin),
) -> List[schemas.UserWithMonitors]:
    result = await db.execute(
        select(models.User).options(selectinload(models.User.monitors))
    )
    users = result.scalars().all()
    return list(users)
