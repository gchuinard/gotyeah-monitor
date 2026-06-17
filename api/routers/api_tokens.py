import secrets
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
import models
import schemas
from auth import get_current_user, _hash_token

# Gestion des tokens d'API : toujours via le JWT (la web UI), jamais via un token d'API.
router = APIRouter(prefix="/api-tokens", tags=["api-tokens"])


@router.get("", response_model=List[schemas.ApiTokenRead])
async def list_api_tokens(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> List[schemas.ApiTokenRead]:
    res = await db.execute(
        select(models.ApiToken)
        .where(models.ApiToken.user_id == current_user.id)
        .order_by(models.ApiToken.id.desc())
    )
    return list(res.scalars().all())


@router.post("", response_model=schemas.ApiTokenCreated, status_code=status.HTTP_201_CREATED)
async def create_api_token(
    payload: schemas.ApiTokenCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.ApiTokenCreated:
    raw = "gym_" + secrets.token_urlsafe(32)
    token = models.ApiToken(
        user_id=current_user.id,
        name=payload.name,
        token_hash=_hash_token(raw),
        prefix=raw[:12],
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    # Le token brut n'est renvoyé qu'ICI, une seule fois (seul le hash est stocké).
    return schemas.ApiTokenCreated(
        id=token.id,
        name=token.name,
        prefix=token.prefix,
        last_used_at=token.last_used_at,
        created_at=token.created_at,
        token=raw,
    )


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_token(
    token_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    token = await db.get(models.ApiToken, token_id)
    if not token or token.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await db.delete(token)
    await db.commit()
    return None
