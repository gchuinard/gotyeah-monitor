from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
import models
import schemas
from auth import get_current_user
from rate_limit import limiter
from routers.monitors import _attach_uptime


# ── Gestion (authentifiée) de la page publique de l'utilisateur ───────────────
manage_router = APIRouter(prefix="/status-page", tags=["status-page"])


@manage_router.get("", response_model=Optional[schemas.StatusPageRead])
async def get_my_status_page(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    res = await db.execute(
        select(models.StatusPage).where(models.StatusPage.user_id == current_user.id)
    )
    return res.scalars().first()


@manage_router.put("", response_model=schemas.StatusPageRead)
async def upsert_my_status_page(
    payload: schemas.StatusPageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.StatusPageRead:
    # Slug unique (sauf si c'est déjà le nôtre).
    res = await db.execute(
        select(models.StatusPage).where(models.StatusPage.slug == payload.slug)
    )
    other = res.scalars().first()
    if other and other.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ce slug est déjà pris.")

    res2 = await db.execute(
        select(models.StatusPage).where(models.StatusPage.user_id == current_user.id)
    )
    page = res2.scalars().first()
    if page:
        page.slug = payload.slug
        page.title = payload.title
    else:
        page = models.StatusPage(user_id=current_user.id, slug=payload.slug, title=payload.title)
        db.add(page)
    await db.commit()
    await db.refresh(page)
    return page


# ── Endpoints PUBLICS (non authentifiés, rate-limités) ────────────────────────
public_router = APIRouter(prefix="/public", tags=["public"])


async def _load_public(db: AsyncSession, slug: str):
    """Page par slug + ses monitors PUBLICS uniquement (jamais les privés)."""
    res = await db.execute(select(models.StatusPage).where(models.StatusPage.slug == slug))
    page = res.scalars().first()
    if not page:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page introuvable")
    res2 = await db.execute(
        select(models.Monitor).where(
            models.Monitor.user_id == page.user_id,
            models.Monitor.is_public.is_(True),
        )
    )
    return page, list(res2.scalars().all())


@public_router.get("/{slug}", response_model=schemas.PublicStatusResponse)
@limiter.limit("60/minute")
async def public_status(
    request: Request, slug: str, db: AsyncSession = Depends(get_db)
) -> schemas.PublicStatusResponse:
    page, monitors = await _load_public(db, slug)
    await _attach_uptime(db, monitors)
    open_ids: set = set()
    if monitors:
        ids = [m.id for m in monitors]
        res = await db.execute(
            select(models.Incident.monitor_id).where(
                models.Incident.monitor_id.in_(ids),
                models.Incident.ended_at.is_(None),
            )
        )
        open_ids = {row[0] for row in res.all()}
    items = [
        schemas.PublicMonitorStatus(
            name=m.name,
            status=m.status,
            uptime_24h=m.uptime_24h,
            uptime_30d=m.uptime_30d,
            has_open_incident=m.id in open_ids,
        )
        for m in monitors
    ]
    return schemas.PublicStatusResponse(title=page.title, monitors=items)


def _render_badge(label: str, message: str, color: str) -> str:
    """SVG style shields.io (largeurs approximées, aucune donnée utilisateur injectée)."""
    def width(s: str) -> int:
        return len(s) * 7 + 12

    lw = width(label)
    mw = width(message)
    total = lw + mw
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="20" '
        f'role="img" aria-label="{label}: {message}">'
        f'<linearGradient id="g" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/>'
        f'<stop offset="1" stop-opacity=".1"/></linearGradient>'
        f'<rect width="{total}" height="20" rx="3" fill="#555"/>'
        f'<rect x="{lw}" width="{mw}" height="20" rx="3" fill="{color}"/>'
        f'<rect width="{total}" height="20" rx="3" fill="url(#g)"/>'
        f'<g fill="#fff" text-anchor="middle" font-family="Verdana,DejaVu Sans,sans-serif" font-size="11">'
        f'<text x="{lw / 2:.0f}" y="14">{label}</text>'
        f'<text x="{lw + mw / 2:.0f}" y="14">{message}</text>'
        f"</g></svg>"
    )


@public_router.get("/{slug}/badge/{monitor_id}.svg")
@limiter.limit("120/minute")
async def public_badge(
    request: Request, slug: str, monitor_id: int, db: AsyncSession = Depends(get_db)
) -> Response:
    _, monitors = await _load_public(db, slug)
    monitor = next((m for m in monitors if m.id == monitor_id), None)
    if not monitor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitor introuvable")
    await _attach_uptime(db, [monitor])
    pct = monitor.uptime_24h
    if pct is None:
        message, color = "n/a", "#9f9f9f"
    else:
        message = f"{pct}%"
        color = "#4c1" if pct >= 99.5 else "#dfb317" if pct >= 95 else "#e05d44"
    svg = _render_badge("uptime", message, color)
    return Response(content=svg, media_type="image/svg+xml", headers={"Cache-Control": "max-age=300"})
