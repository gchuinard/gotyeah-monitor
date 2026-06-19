"""Autorisation par équipe : remplace les checks `resource.user_id == current_user.id`.

L'ownership des ressources (monitors, groupes, page de statut) passe par l'équipe.
Rôles, du moins au plus permissif : readonly < member < admin.
- readonly : lecture seule.
- member   : CRUD des ressources (monitors/groupes/maintenance/destinataires/incidents).
- admin    : en plus, gestion des membres + paramètres d'équipe + suppression.

Helpers appelés dans les handlers (même style que l'ancien `_owned_monitor`), pas des
dépendances FastAPI : la plupart des routes résolvent l'équipe depuis la ressource
chargée (monitor.team_id), pas depuis un team_id de chemin.
"""
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import models
import schemas

ROLE_RANK = {"readonly": 0, "member": 1, "admin": 2}


def _has_rank(role: str, min_role: str) -> bool:
    return ROLE_RANK.get(role, -1) >= ROLE_RANK[min_role]


async def get_membership(
    db: AsyncSession, team_id: Optional[int], user_id: int
) -> Optional[models.TeamMember]:
    if team_id is None:
        return None
    res = await db.execute(
        select(models.TeamMember).where(
            models.TeamMember.team_id == team_id,
            models.TeamMember.user_id == user_id,
        )
    )
    return res.scalar_one_or_none()


async def user_team_ids(db: AsyncSession, user_id: int) -> List[int]:
    res = await db.execute(
        select(models.TeamMember.team_id).where(models.TeamMember.user_id == user_id)
    )
    return [row[0] for row in res.all()]


async def require_team(
    db: AsyncSession, team_id: int, user: models.User, min_role: str = "readonly"
) -> models.TeamMember:
    """Vérifie que `user` est membre de l'équipe avec au moins `min_role`. 403 sinon."""
    member = await get_membership(db, team_id, user.id)
    if member is None:
        # On renvoie 403 (pas 404) : l'existence d'une équipe n'est pas un secret, mais
        # l'absence d'appartenance interdit l'accès.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès interdit à cette équipe")
    if not _has_rank(member.role, min_role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Droits insuffisants")
    return member


async def require_monitor(
    db: AsyncSession, monitor_id: int, user: models.User, min_role: str = "readonly"
) -> Tuple[models.Monitor, models.TeamMember]:
    monitor = await db.get(models.Monitor, monitor_id)
    if not monitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    member = await require_team(db, monitor.team_id, user, min_role)
    return monitor, member


async def require_group(
    db: AsyncSession, group_id: int, user: models.User, min_role: str = "readonly"
) -> Tuple[models.MonitorGroup, models.TeamMember]:
    group = await db.get(models.MonitorGroup, group_id)
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    member = await require_team(db, group.team_id, user, min_role)
    return group, member


async def create_team(
    db: AsyncSession,
    name: str,
    owner_user_id: int,
    webhook_url: Optional[str] = None,
    webhook_kind: Optional[str] = None,
    alert_email_enabled: bool = True,
) -> models.Team:
    """Crée une équipe et son premier membre (owner_user_id en admin). flush pour avoir
    l'id ; le commit est laissé à l'appelant."""
    team = models.Team(name=name, alert_webhook_url=webhook_url, alert_webhook_kind=webhook_kind)
    db.add(team)
    await db.flush()
    db.add(
        models.TeamMember(
            team_id=team.id,
            user_id=owner_user_id,
            role="admin",
            alert_email_enabled=alert_email_enabled,
        )
    )
    return team


async def count_admins(db: AsyncSession, team_id: int) -> int:
    res = await db.execute(
        select(func.count())
        .select_from(models.TeamMember)
        .where(models.TeamMember.team_id == team_id, models.TeamMember.role == "admin")
    )
    return int(res.scalar_one())


async def _team_member_count(db: AsyncSession, team_id: int) -> int:
    res = await db.execute(
        select(func.count()).select_from(models.TeamMember).where(
            models.TeamMember.team_id == team_id
        )
    )
    return int(res.scalar_one())


async def delete_user_cascade(db: AsyncSession, user: models.User) -> None:
    """Supprime un compte en respectant la règle "toujours >= 1 admin par équipe" :
    refus (409) si le compte est le DERNIER admin d'une équipe comptant d'autres membres
    (il faut d'abord transférer le rôle). Les équipes dont il est le SEUL membre sont
    supprimées (cascade monitors/groupes). Les ressources des équipes survivantes ne sont
    pas supprimées : la FK créateur (user_id) est en SET NULL (migration 0022). Commit inclus."""
    res = await db.execute(
        select(models.TeamMember).where(models.TeamMember.user_id == user.id)
    )
    memberships = list(res.scalars().all())

    sole_member_team_ids = []
    for mem in memberships:
        total = await _team_member_count(db, mem.team_id)
        if mem.role == "admin" and await count_admins(db, mem.team_id) <= 1 and total > 1:
            team = await db.get(models.Team, mem.team_id)
            name = team.name if team else mem.team_id
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Ce compte est le dernier admin de l'équipe « {name} ». "
                    "Transférez le rôle admin à un autre membre (ou supprimez l'équipe) "
                    "avant de supprimer le compte."
                ),
            )
        if total <= 1:
            sole_member_team_ids.append(mem.team_id)

    for tid in sole_member_team_ids:
        team = await db.get(models.Team, tid)
        if team:
            await db.delete(team)

    await db.delete(user)
    await db.commit()


# ── Destinataires d'alerte (partagé monitors + groupes) ───────────────────────


async def validate_recipient_member(
    db: AsyncSession, member_user_id: Optional[int], team_id: int
) -> None:
    """Un destinataire-membre doit appartenir à l'équipe de la ressource."""
    if member_user_id is None:
        return
    if await get_membership(db, team_id, member_user_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le membre désigné n'appartient pas à cette équipe.",
        )


async def recipient_read(
    db: AsyncSession, rec: models.AlertRecipient
) -> schemas.AlertRecipientRead:
    member_email = None
    if rec.member_user_id is not None:
        user = await db.get(models.User, rec.member_user_id)
        member_email = user.email if user else None
    return schemas.AlertRecipientRead(
        id=rec.id,
        email=rec.email,
        member_user_id=rec.member_user_id,
        member_email=member_email,
        created_at=rec.created_at,
    )
