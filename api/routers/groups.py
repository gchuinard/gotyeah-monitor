from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
import models
import schemas
import team_access
from auth import get_current_user

router = APIRouter(prefix="/groups", tags=["groups"])


@router.get("", response_model=List[schemas.MonitorGroupRead])
async def list_groups(
    team_id: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> List[schemas.MonitorGroupRead]:
    # team_id fourni -> cette équipe (appartenance vérifiée) ; sinon toutes les équipes du user.
    if team_id is not None:
        await team_access.require_team(db, team_id, current_user, "readonly")
        team_ids = [team_id]
    else:
        team_ids = await team_access.user_team_ids(db, current_user.id)
    if not team_ids:
        return []
    result = await db.execute(
        select(models.MonitorGroup)
        .where(models.MonitorGroup.team_id.in_(team_ids))
        .order_by(models.MonitorGroup.id.asc())
    )
    return list(result.scalars().all())


@router.post("", response_model=schemas.MonitorGroupRead, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: schemas.MonitorGroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.MonitorGroupRead:
    await team_access.require_team(db, payload.team_id, current_user, "member")
    group = models.MonitorGroup(
        name=payload.name, team_id=payload.team_id, user_id=current_user.id
    )
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
    group, _ = await team_access.require_group(db, group_id, current_user, "member")
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
    group, _ = await team_access.require_group(db, group_id, current_user, "member")
    # FK monitors.group_id ON DELETE SET NULL -> les monitors du groupe sont dégroupés
    # (pas supprimés). Les alert_recipients du groupe (FK CASCADE) sont supprimés.
    await db.delete(group)
    await db.commit()
    return None


# ── Destinataires d'alerte du groupe (s'appliquent à tous ses monitors) ───────


@router.get("/{group_id}/recipients", response_model=List[schemas.AlertRecipientRead])
async def list_group_recipients(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> List[schemas.AlertRecipientRead]:
    await team_access.require_group(db, group_id, current_user, "readonly")
    res = await db.execute(
        select(models.AlertRecipient)
        .where(models.AlertRecipient.group_id == group_id)
        .order_by(models.AlertRecipient.id.asc())
    )
    return [await team_access.recipient_read(db, r) for r in res.scalars().all()]


@router.post(
    "/{group_id}/recipients",
    response_model=schemas.AlertRecipientRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_group_recipient(
    group_id: int,
    payload: schemas.AlertRecipientCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.AlertRecipientRead:
    group, _ = await team_access.require_group(db, group_id, current_user, "member")
    await team_access.validate_recipient_member(db, payload.member_user_id, group.team_id)
    rec = models.AlertRecipient(
        group_id=group_id,
        email=str(payload.email) if payload.email else None,
        member_user_id=payload.member_user_id,
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return await team_access.recipient_read(db, rec)


@router.delete(
    "/{group_id}/recipients/{recipient_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_group_recipient(
    group_id: int,
    recipient_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    await team_access.require_group(db, group_id, current_user, "member")
    rec = await db.get(models.AlertRecipient, recipient_id)
    if not rec or rec.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.delete(rec)
    await db.commit()
    return None
