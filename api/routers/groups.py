from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
import models
import schemas
from auth import get_current_user

router = APIRouter(prefix="/groups", tags=["groups"])


@router.get("", response_model=List[schemas.MonitorGroupRead])
async def list_groups(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> List[schemas.MonitorGroupRead]:
    result = await db.execute(
        select(models.MonitorGroup)
        .where(models.MonitorGroup.user_id == current_user.id)
        .order_by(models.MonitorGroup.id.asc())
    )
    return list(result.scalars().all())


@router.post("", response_model=schemas.MonitorGroupRead, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: schemas.MonitorGroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.MonitorGroupRead:
    group = models.MonitorGroup(name=payload.name, user_id=current_user.id)
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return group


@router.put("/{group_id}", response_model=schemas.MonitorGroupRead)
async def update_group(
    group_id: int,
    payload: schemas.MonitorGroupUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.MonitorGroupRead:
    group = await db.get(models.MonitorGroup, group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if group.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    group.name = payload.name
    await db.commit()
    await db.refresh(group)
    return group


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    group = await db.get(models.MonitorGroup, group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if group.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    # FK monitors.group_id ON DELETE SET NULL -> les monitors du groupe sont dégroupés
    # (pas supprimés).
    await db.delete(group)
    await db.commit()
    return None
