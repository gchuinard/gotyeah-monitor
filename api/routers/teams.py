from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
import models
import schemas
import team_access
from auth import get_current_user, get_user_by_email
from ssrf_guard import url_is_safe

router = APIRouter(prefix="/teams", tags=["teams"])


def _team_read(team: models.Team, role: str, member_count: int) -> schemas.TeamRead:
    return schemas.TeamRead(
        id=team.id,
        name=team.name,
        alert_webhook_url=team.alert_webhook_url,
        alert_webhook_kind=team.alert_webhook_kind,
        deletion_scheduled_at=team.deletion_scheduled_at,
        created_at=team.created_at,
        role=role,
        member_count=member_count,
    )


def _member_read(member: models.TeamMember, email: str) -> schemas.TeamMemberRead:
    return schemas.TeamMemberRead(
        id=member.id,
        user_id=member.user_id,
        email=email,
        role=member.role,
        alert_email_enabled=member.alert_email_enabled,
        created_at=member.created_at,
    )


async def _member_count(db: AsyncSession, team_id: int) -> int:
    res = await db.execute(
        select(func.count()).select_from(models.TeamMember).where(
            models.TeamMember.team_id == team_id
        )
    )
    return int(res.scalar_one())


@router.get("", response_model=List[schemas.TeamRead])
async def list_teams(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> List[schemas.TeamRead]:
    res = await db.execute(
        select(models.TeamMember, models.Team)
        .join(models.Team, models.Team.id == models.TeamMember.team_id)
        .where(models.TeamMember.user_id == current_user.id)
        .order_by(models.Team.id.asc())
    )
    rows = res.all()
    team_ids = [t.id for _, t in rows]
    counts = {}
    if team_ids:
        cres = await db.execute(
            select(models.TeamMember.team_id, func.count())
            .where(models.TeamMember.team_id.in_(team_ids))
            .group_by(models.TeamMember.team_id)
        )
        counts = {tid: c for tid, c in cres.all()}
    return [_team_read(t, m.role, counts.get(t.id, 1)) for m, t in rows]


@router.post("", response_model=schemas.TeamRead, status_code=status.HTTP_201_CREATED)
async def create_team(
    payload: schemas.TeamCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.TeamRead:
    team = await team_access.create_team(db, payload.name, current_user.id)
    await db.commit()
    await db.refresh(team)
    return _team_read(team, "admin", 1)


@router.put("/{team_id}", response_model=schemas.TeamRead)
async def update_team(
    team_id: int,
    payload: schemas.TeamUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.TeamRead:
    member = await team_access.require_team(db, team_id, current_user, "admin")
    team = await db.get(models.Team, team_id)
    if payload.name is not None:
        team.name = payload.name
    # Webhook d'équipe : "" => effacer, valeur => définir, None => ne pas toucher.
    if payload.alert_webhook_url is not None:
        url = payload.alert_webhook_url.strip()
        if url and not await url_is_safe(url):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="URL de webhook invalide ou pointant vers une cible interne.",
            )
        team.alert_webhook_url = url or None
        team.alert_webhook_kind = (payload.alert_webhook_kind or None) if url else None
    await db.commit()
    await db.refresh(team)
    return _team_read(team, member.role, await _member_count(db, team_id))


@router.delete("/{team_id}", response_model=schemas.TeamRead)
async def schedule_delete_team(
    team_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.TeamRead:
    """Suppression DIFFÉRÉE : on ne supprime pas tout de suite. L'équipe est marquée
    pour suppression (désactivée, monitoring suspendu) et sera purgée après la période
    de grâce par la boucle. Réactivable d'ici là via /restore. Refus si c'est le dernier
    espace ACTIF de l'utilisateur (il doit toujours garder un espace utilisable)."""
    member = await team_access.require_team(db, team_id, current_user, "admin")
    # Garde "dernier espace actif" : il faut au moins un AUTRE espace non planifié.
    res = await db.execute(
        select(func.count())
        .select_from(models.TeamMember)
        .join(models.Team, models.Team.id == models.TeamMember.team_id)
        .where(
            models.TeamMember.user_id == current_user.id,
            models.Team.id != team_id,
            models.Team.deletion_scheduled_at.is_(None),
        )
    )
    if int(res.scalar_one()) < 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Impossible de supprimer votre dernier espace actif. Créez-en un autre d'abord.",
        )
    team = await db.get(models.Team, team_id)
    if team.deletion_scheduled_at is None:
        team.deletion_scheduled_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(team)
    return _team_read(team, member.role, await _member_count(db, team_id))


@router.post("/{team_id}/restore", response_model=schemas.TeamRead)
async def restore_team(
    team_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.TeamRead:
    """Annule une suppression différée (réactive l'équipe)."""
    member = await team_access.require_team(db, team_id, current_user, "admin")
    team = await db.get(models.Team, team_id)
    team.deletion_scheduled_at = None
    await db.commit()
    await db.refresh(team)
    return _team_read(team, member.role, await _member_count(db, team_id))


# ── Membres ───────────────────────────────────────────────────────────────────


@router.get("/{team_id}/members", response_model=List[schemas.TeamMemberRead])
async def list_members(
    team_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> List[schemas.TeamMemberRead]:
    await team_access.require_team(db, team_id, current_user, "readonly")
    res = await db.execute(
        select(models.TeamMember)
        .options(selectinload(models.TeamMember.user))
        .where(models.TeamMember.team_id == team_id)
        .order_by(models.TeamMember.id.asc())
    )
    return [_member_read(m, m.user.email) for m in res.scalars().all()]


@router.post(
    "/{team_id}/members",
    response_model=schemas.TeamMemberRead,
    status_code=status.HTTP_201_CREATED,
)
async def invite_member(
    team_id: int,
    payload: schemas.TeamMemberInvite,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.TeamMemberRead:
    await team_access.require_team(db, team_id, current_user, "admin")
    # On n'ajoute qu'un compte EXISTANT (pas de création/invitation par email ici).
    user = await get_user_by_email(db, str(payload.email))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun compte avec cet email. La personne doit d'abord créer un compte.",
        )
    if await team_access.get_membership(db, team_id, user.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cette personne est déjà membre de l'équipe.",
        )
    member = models.TeamMember(team_id=team_id, user_id=user.id, role=payload.role)
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return _member_read(member, user.email)


@router.patch("/{team_id}/members/{member_id}", response_model=schemas.TeamMemberRead)
async def update_member_role(
    team_id: int,
    member_id: int,
    payload: schemas.TeamMemberRoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.TeamMemberRead:
    await team_access.require_team(db, team_id, current_user, "admin")
    member = await db.get(models.TeamMember, member_id)
    if not member or member.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    # Garde "toujours >= 1 admin" : on ne peut pas rétrograder le dernier admin.
    if member.role == "admin" and payload.role != "admin":
        if await team_access.count_admins(db, team_id) <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Impossible de rétrograder le dernier admin de l'équipe.",
            )
    member.role = payload.role
    await db.commit()
    await db.refresh(member)
    user = await db.get(models.User, member.user_id)
    return _member_read(member, user.email)


@router.delete("/{team_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    team_id: int,
    member_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    member = await db.get(models.TeamMember, member_id)
    if not member or member.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    # Un admin retire qui il veut ; un membre peut se retirer lui-même (quitter l'équipe).
    is_self = member.user_id == current_user.id
    await team_access.require_team(
        db, team_id, current_user, "readonly" if is_self else "admin"
    )
    if member.role == "admin" and await team_access.count_admins(db, team_id) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Impossible de retirer le dernier admin (promouvez d'abord quelqu'un).",
        )
    await db.delete(member)
    await db.commit()
    return None


@router.patch("/{team_id}/me", response_model=schemas.TeamMemberRead)
async def update_my_membership(
    team_id: int,
    payload: schemas.MembershipPrefsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.TeamMemberRead:
    """Préférences de l'utilisateur courant DANS cette équipe (couper ses alertes email)."""
    member = await team_access.require_team(db, team_id, current_user, "readonly")
    member.alert_email_enabled = payload.alert_email_enabled
    await db.commit()
    await db.refresh(member)
    return _member_read(member, current_user.email)
