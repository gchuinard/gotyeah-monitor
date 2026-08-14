"""Pont de confiance HTTP `/api/mcp/*` pour le hub MCP central (gotyeah-mcp).

Le hub est la SEULE porte d'entrée MCP/OAuth pour claude.ai : il authentifie la personne
via l'IdP (Pocket ID), extrait l'email VÉRIFIÉ, puis appelle ces endpoints avec
`X-MCP-Secret` (secret partagé) + `X-Act-As-Email`. Ici on ne refait AUCUNE auth OAuth :
le secret authentifie le hub comme appelant de confiance, on résout l'email → compte
Monitor, et **toute l'autorisation reste celle de l'app** — `team_access.require_team` /
`require_monitor` avec les mêmes rôles (`readonly` en lecture, `member` en écriture).
Le pont n'est PAS un contournement des droits : il agit AVEC ceux de la personne.

Default-deny : sans `MONITOR_MCP_SHARED_SECRET` (ou avec un mauvais secret), toute route
renvoie 401. Le secret DOIT être identique à `MONITOR_MCP_SECRET` côté gotyeah-mcp.
Symétrique du pont déjà utilisé par gotyeah-sonar et gotyeah-notes.

⚠️ **C'est la première surface d'ÉCRITURE non-JWT de l'API.** Les tokens d'API (`gym_…`)
sont volontairement en lecture seule (`auth.get_user_flexible` n'est monté que sur les GET) ;
ce pont, lui, crée / modifie / supprime — c'est son objet. La compensation : il n'écrit que
sous une identité d'email VÉRIFIÉE par l'IdP, et jamais au-delà du rôle d'équipe de cette
identité. Ne pas relâcher l'un des deux.

Les routes sont montées via `register(app)` (`add_api_route` → APIRoute normales), et non un
APIRouter/include_router, pour rester robuste à toutes les versions FastAPI.
"""
from __future__ import annotations

import hmac
import os
from typing import Any, Dict, List, Optional

from fastapi import Body, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
import models
import schemas
import team_access
from auth import get_user_by_email
from routers.monitors import _attach_maintenance, _attach_uptime, _validate_group

# Champs de MonitorUpdate qui acceptent NULL en base. Seuls ceux-là peuvent figurer dans
# le `clear` d'update_monitor : remettre `name` ou `url` à NULL casserait le monitor.
CLEARABLE_FIELDS = frozenset(
    {"check_interval_seconds", "keyword", "latency_threshold_ms", "port", "group_id", "environment"}
)


def bridge_enabled() -> bool:
    """Vrai si le pont est configuré (secret partagé présent). Purement indicatif :
    la garde réelle est par-requête dans `_require_bridge` (default-deny)."""
    return bool((os.environ.get("MONITOR_MCP_SHARED_SECRET") or "").strip())


async def _require_bridge(
    db: AsyncSession, secret: Optional[str], email: Optional[str]
) -> models.User:
    """Vérifie le secret partagé (temps constant) puis résout l'email → compte Monitor.

    Le hub ne transmet QUE des emails vérifiés par l'IdP ; le secret prouve que l'appel
    vient bien du hub. 401 si secret absent/invalide, email manquant, ou compte inconnu.
    """
    expected = (os.environ.get("MONITOR_MCP_SHARED_SECRET") or "").strip()
    # Comparaison en bytes : compare_digest lève TypeError sur une str non-ASCII (un
    # X-MCP-Secret forgé avec des octets latin-1 renverrait alors 500 au lieu de 401).
    if (
        not expected
        or not secret
        or not hmac.compare_digest(secret.encode("utf-8"), expected.encode("utf-8"))
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Secret MCP invalide.")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-Act-As-Email requis.")
    user = await get_user_by_email(db, email.strip())
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                f"Aucun compte Monitor pour {email.strip()}. Connecte-toi une fois sur "
                "l'interface web (bouton Pocket ID) pour créer le compte."
            ),
        )
    return user


async def _teams_of(db: AsyncSession, user: models.User) -> List[models.TeamMember]:
    """Appartenances du user, équipe chargée. Ordre stable (id) pour des sorties reproductibles."""
    res = await db.execute(
        select(models.TeamMember)
        .where(models.TeamMember.user_id == user.id)
        .order_by(models.TeamMember.team_id.asc())
    )
    memberships = list(res.scalars().all())
    for mem in memberships:
        mem.team = await db.get(models.Team, mem.team_id)
    return memberships


async def _resolve_team_id(db: AsyncSession, user: models.User, team_id: Optional[int]) -> int:
    """Équipe cible d'une création. Fourni -> tel quel (droits vérifiés par l'appelant).

    Absent -> repli sur l'UNIQUE équipe où le user peut écrire (le cas courant : chacun a
    son équipe personnelle). Dès qu'il y en a plusieurs on REFUSE en listant les choix,
    plutôt que d'en deviner une : créer un monitor dans la mauvaise équipe le rend invisible
    à ceux qui devaient le voir, et l'alerte part aux mauvaises personnes.
    """
    if team_id is not None:
        return team_id
    memberships = await _teams_of(db, user)
    writable = [
        m
        for m in memberships
        if team_access.ROLE_RANK.get(m.role, -1) >= team_access.ROLE_RANK["member"]
        and (m.team is None or m.team.deletion_scheduled_at is None)
    ]
    if len(writable) == 1:
        return writable[0].team_id
    if not writable:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Aucune équipe active où tu as le droit d'écrire (rôle 'member' minimum).",
        )
    choices = ", ".join(f"{m.team_id} ({m.team.name})" for m in writable if m.team)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"team_id requis : tu peux écrire dans plusieurs équipes — {choices}.",
    )


def _apply_patch(monitor: models.Monitor, patch: Dict[str, Any], clear: List[str]) -> schemas.MonitorUpdate:
    """Fusionne un patch PARTIEL sur l'état courant, puis revalide via MonitorUpdate.

    ⚠️ Raison d'être : `PUT /monitors/{id}` est un remplacement TOTAL (tout champ absent du
    payload est écrasé). Exposé tel quel à un agent, « renomme ce monitor » effacerait son
    mot-clé, son seuil de latence, son intervalle et son groupe sans rien dire. On lit donc
    l'existant, on n'écrase que ce qui est fourni, et on repasse par le MÊME schéma Pydantic
    que la web UI — bornes, `keyword_mode`, et « port requis pour le type port » restent
    validés à un seul endroit.

    `clear` est la façon EXPLICITE de remettre un champ à NULL : sans lui, `None` ne peut
    signifier que « non fourni », et un champ nullable serait ineffaçable via le pont.
    """
    current = {
        "name": monitor.name,
        "url": monitor.url,
        "type": monitor.type,
        "expected_status_code": monitor.expected_status_code,
        "check_interval_seconds": monitor.check_interval_seconds,
        "keyword": monitor.keyword,
        "keyword_mode": monitor.keyword_mode,
        "latency_threshold_ms": monitor.latency_threshold_ms,
        "port": monitor.port,
        "group_id": monitor.group_id,
        "environment": monitor.environment,
        "is_public": monitor.is_public,
    }
    for field in clear:
        if field not in CLEARABLE_FIELDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Champ '{field}' non effaçable. Effaçables : "
                    f"{', '.join(sorted(CLEARABLE_FIELDS))}."
                ),
            )
        current[field] = None
    for key, value in patch.items():
        if value is not None:
            current[key] = value
    try:
        return schemas.MonitorUpdate(**current)
    except ValueError as exc:
        # Erreur de validation Pydantic -> 400 lisible plutôt qu'une 500 opaque côté hub.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# --------------------------------------------------------------------------- #
# Endpoints. Miroir de mcp_remote/monitor_tools.py côté hub.
# --------------------------------------------------------------------------- #
async def _list_teams(
    db: AsyncSession = Depends(get_db),
    x_mcp_secret: Optional[str] = Header(None, alias="X-MCP-Secret"),
    x_act_as_email: Optional[str] = Header(None, alias="X-Act-As-Email"),
):
    """Équipes du compte + leurs groupes : de quoi choisir un `team_id` et un `group_id`.

    Les groupes voyagent AVEC leur équipe (et pas dans un outil séparé) parce qu'ils ne
    servent qu'à ça : un `group_id` n'est valide que dans l'équipe du monitor.
    """
    user = await _require_bridge(db, x_mcp_secret, x_act_as_email)
    memberships = await _teams_of(db, user)
    team_ids = [m.team_id for m in memberships]
    groups_by_team: Dict[int, List[Dict[str, Any]]] = {tid: [] for tid in team_ids}
    if team_ids:
        res = await db.execute(
            select(models.MonitorGroup)
            .where(models.MonitorGroup.team_id.in_(team_ids))
            .order_by(models.MonitorGroup.id.asc())
        )
        for group in res.scalars().all():
            groups_by_team.setdefault(group.team_id, []).append(
                {"id": group.id, "name": group.name}
            )
    out = []
    for mem in memberships:
        if mem.team is None:
            continue
        out.append(
            {
                "team_id": mem.team_id,
                "name": mem.team.name,
                "role": mem.role,
                # can_write reflète la règle appliquée par team_access : 'member' minimum.
                "can_write": team_access.ROLE_RANK.get(mem.role, -1)
                >= team_access.ROLE_RANK["member"],
                # Équipe en suppression différée : listée, mais son monitoring est SUSPENDU
                # (la boucle l'écarte). Le dire évite de croire à une panne.
                "deletion_scheduled_at": mem.team.deletion_scheduled_at,
                "groups": groups_by_team.get(mem.team_id, []),
            }
        )
    return out


async def _list_monitors(
    team_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    x_mcp_secret: Optional[str] = Header(None, alias="X-MCP-Secret"),
    x_act_as_email: Optional[str] = Header(None, alias="X-Act-As-Email"),
):
    user = await _require_bridge(db, x_mcp_secret, x_act_as_email)
    if team_id is not None:
        await team_access.require_team(db, team_id, user, "readonly")
        team_ids = [team_id]
    else:
        team_ids = await team_access.user_team_ids(db, user.id)
    if not team_ids:
        return []
    res = await db.execute(select(models.Monitor).where(models.Monitor.team_id.in_(team_ids)))
    monitors = list(res.scalars().all())
    await _attach_uptime(db, monitors)
    await _attach_maintenance(db, monitors)
    return monitors


async def _get_monitor(
    monitor_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    x_mcp_secret: Optional[str] = Header(None, alias="X-MCP-Secret"),
    x_act_as_email: Optional[str] = Header(None, alias="X-Act-As-Email"),
):
    user = await _require_bridge(db, x_mcp_secret, x_act_as_email)
    monitor, _ = await team_access.require_monitor(db, monitor_id, user, "readonly")
    await _attach_uptime(db, [monitor])
    await _attach_maintenance(db, [monitor])
    return monitor


async def _create_monitor(
    name: str = Body(..., embed=True),
    url: str = Body(..., embed=True),
    team_id: Optional[int] = Body(None, embed=True),
    type: str = Body("http", embed=True),
    expected_status_code: int = Body(200, embed=True),
    check_interval_seconds: Optional[int] = Body(None, embed=True),
    keyword: Optional[str] = Body(None, embed=True),
    keyword_mode: str = Body("present", embed=True),
    latency_threshold_ms: Optional[int] = Body(None, embed=True),
    port: Optional[int] = Body(None, embed=True),
    group_id: Optional[int] = Body(None, embed=True),
    environment: Optional[str] = Body(None, embed=True),
    is_public: bool = Body(False, embed=True),
    db: AsyncSession = Depends(get_db),
    x_mcp_secret: Optional[str] = Header(None, alias="X-MCP-Secret"),
    x_act_as_email: Optional[str] = Header(None, alias="X-Act-As-Email"),
):
    user = await _require_bridge(db, x_mcp_secret, x_act_as_email)
    resolved_team = await _resolve_team_id(db, user, team_id)
    await team_access.require_team(db, resolved_team, user, "member")
    try:
        payload = schemas.MonitorCreate(
            name=name,
            url=url,
            team_id=resolved_team,
            type=type,
            expected_status_code=expected_status_code,
            check_interval_seconds=check_interval_seconds,
            keyword=keyword,
            keyword_mode=keyword_mode,
            latency_threshold_ms=latency_threshold_ms,
            port=port,
            group_id=group_id,
            environment=environment,
            is_public=is_public,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    await _validate_group(db, payload.group_id, resolved_team)
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
        environment=payload.environment,
        is_public=payload.is_public,
        team_id=resolved_team,
        # Créateur (audit) : le compte résolu depuis l'email vérifié, comme via la web UI.
        user_id=user.id,
    )
    db.add(monitor)
    await db.commit()
    await db.refresh(monitor)
    return monitor


async def _update_monitor(
    monitor_id: int = Body(..., embed=True),
    name: Optional[str] = Body(None, embed=True),
    url: Optional[str] = Body(None, embed=True),
    type: Optional[str] = Body(None, embed=True),
    expected_status_code: Optional[int] = Body(None, embed=True),
    check_interval_seconds: Optional[int] = Body(None, embed=True),
    keyword: Optional[str] = Body(None, embed=True),
    keyword_mode: Optional[str] = Body(None, embed=True),
    latency_threshold_ms: Optional[int] = Body(None, embed=True),
    port: Optional[int] = Body(None, embed=True),
    group_id: Optional[int] = Body(None, embed=True),
    environment: Optional[str] = Body(None, embed=True),
    is_public: Optional[bool] = Body(None, embed=True),
    clear: Optional[List[str]] = Body(None, embed=True),
    db: AsyncSession = Depends(get_db),
    x_mcp_secret: Optional[str] = Header(None, alias="X-MCP-Secret"),
    x_act_as_email: Optional[str] = Header(None, alias="X-Act-As-Email"),
):
    user = await _require_bridge(db, x_mcp_secret, x_act_as_email)
    monitor, _ = await team_access.require_monitor(db, monitor_id, user, "member")
    payload = _apply_patch(
        monitor,
        {
            "name": name,
            "url": url,
            "type": type,
            "expected_status_code": expected_status_code,
            "check_interval_seconds": check_interval_seconds,
            "keyword": keyword,
            "keyword_mode": keyword_mode,
            "latency_threshold_ms": latency_threshold_ms,
            "port": port,
            "group_id": group_id,
            "environment": environment,
            "is_public": is_public,
        },
        clear or [],
    )
    await _validate_group(db, payload.group_id, monitor.team_id)

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
    monitor.environment = payload.environment
    monitor.is_public = payload.is_public

    await db.commit()
    await db.refresh(monitor)
    await _attach_uptime(db, [monitor])
    await _attach_maintenance(db, [monitor])
    return monitor


async def _delete_monitor(
    monitor_id: int = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    x_mcp_secret: Optional[str] = Header(None, alias="X-MCP-Secret"),
    x_act_as_email: Optional[str] = Header(None, alias="X-Act-As-Email"),
):
    user = await _require_bridge(db, x_mcp_secret, x_act_as_email)
    monitor, _ = await team_access.require_monitor(db, monitor_id, user, "member")
    name = monitor.name
    await db.delete(monitor)
    await db.commit()
    # On rend le nom supprimé : le hub s'en sert pour confirmer QUOI a disparu, et l'agent
    # ne peut pas le relire après coup (suppression définitive, aucune corbeille ici).
    return {"deleted": True, "monitor_id": monitor_id, "name": name}


def register(app) -> None:
    """Monte /api/mcp/* sur l'app. `add_api_route` produit des APIRoute normales (avec `.path`)
    — robuste à toutes les versions FastAPI, contrairement à include_router."""
    app.add_api_route("/api/mcp/list_teams", _list_teams, methods=["GET"])
    app.add_api_route(
        "/api/mcp/list_monitors",
        _list_monitors,
        methods=["GET"],
        response_model=List[schemas.MonitorRead],
    )
    app.add_api_route(
        "/api/mcp/get_monitor", _get_monitor, methods=["GET"], response_model=schemas.MonitorRead
    )
    app.add_api_route(
        "/api/mcp/create_monitor",
        _create_monitor,
        methods=["POST"],
        response_model=schemas.MonitorRead,
        status_code=status.HTTP_201_CREATED,
    )
    app.add_api_route(
        "/api/mcp/update_monitor",
        _update_monitor,
        methods=["POST"],
        response_model=schemas.MonitorRead,
    )
    app.add_api_route("/api/mcp/delete_monitor", _delete_monitor, methods=["POST"])
