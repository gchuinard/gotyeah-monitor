from datetime import datetime, timedelta, timezone
from typing import Optional
import hashlib
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
import models
import schemas
from mail_service import (
    send_verification_email,
    send_password_reset_email,
    send_email_change_confirm,
    send_email_change_cancel,
)


SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


router = APIRouter(prefix="/auth", tags=["auth"])


pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
)


def _is_expired(dt: datetime) -> bool:
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt < now


def is_legacy_sha256_hash(value: str) -> bool:
    # Ancien format: sha256 hex (64 chars)
    return len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if is_legacy_sha256_hash(hashed_password):
        return get_legacy_password_hash(plain_password) == hashed_password
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    # Norme actuelle: Argon2id (via passlib)
    return pwd_context.hash(password)


def get_legacy_password_hash(password: str) -> str:
    # Ancien hash (à migrer automatiquement)
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_user_by_email(
    db: AsyncSession, email: str
) -> Optional[models.User]:
    result = await db.execute(select(models.User).where(models.User.email == email))
    return result.scalars().first()


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: Optional[int] = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await db.get(models.User, int(user_id))
    if user is None:
        raise credentials_exception
    return user


@router.get("/me", response_model=schemas.UserRead)
async def read_me(current_user: models.User = Depends(get_current_user)) -> schemas.UserRead:
    return current_user


@router.post("/register", response_model=schemas.MessageResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: schemas.UserCreate, db: AsyncSession = Depends(get_db)
) -> schemas.MessageResponse:
    existing = await get_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = models.User(
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        is_verified=False,
    )
    db.add(user)
    await db.flush()

    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=24)
    verification = models.EmailVerification(
        user_id=user.id,
        token=token,
        expires_at=expires,
    )
    db.add(verification)

    await send_verification_email(user.email, token)
    await db.commit()

    return schemas.MessageResponse(message="Compte créé. Vérifiez votre email pour activer votre compte.")


@router.get("/verify-email", response_model=schemas.MessageResponse)
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> schemas.MessageResponse:
    result = await db.execute(
        select(models.EmailVerification).where(models.EmailVerification.token == token)
    )
    verification = result.scalars().first()

    if not verification:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lien invalide ou expiré.",
        )

    if _is_expired(verification.expires_at):
        await db.delete(verification)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lien expiré.",
        )

    user = await db.get(models.User, verification.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Utilisateur introuvable.",
        )

    user.is_verified = True
    await db.delete(verification)
    await db.commit()

    return schemas.MessageResponse(message="Email vérifié. Vous pouvez vous connecter.")


@router.post("/forgot-password", response_model=schemas.MessageResponse)
async def forgot_password(
    payload: schemas.ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> schemas.MessageResponse:
    user = await get_user_by_email(db, payload.email)

    if user and user.is_verified:
        result = await db.execute(
            select(models.PasswordResetToken).where(
                models.PasswordResetToken.user_id == user.id
            )
        )
        for existing in result.scalars().all():
            await db.delete(existing)

        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        reset_token = models.PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=expires,
        )
        db.add(reset_token)
        await send_password_reset_email(user.email, token)
        await db.commit()

    return schemas.MessageResponse(
        message="Si cet email existe, un lien de réinitialisation a été envoyé."
    )


@router.post("/reset-password", response_model=schemas.MessageResponse)
async def reset_password(
    payload: schemas.ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> schemas.MessageResponse:
    result = await db.execute(
        select(models.PasswordResetToken).where(
            models.PasswordResetToken.token == payload.token
        )
    )
    reset_token = result.scalars().first()

    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lien invalide ou expiré.",
        )

    if _is_expired(reset_token.expires_at):
        await db.delete(reset_token)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lien expiré.",
        )

    user = await db.get(models.User, reset_token.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Utilisateur introuvable.",
        )

    user.hashed_password = get_password_hash(payload.new_password)
    await db.delete(reset_token)
    await db.commit()

    return schemas.MessageResponse(message="Mot de passe mis à jour. Vous pouvez vous connecter.")


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    from sqlalchemy import select as sa_select
    result = await db.execute(sa_select(models.Monitor).where(models.Monitor.user_id == current_user.id))
    for monitor in result.scalars().all():
        await db.delete(monitor)
    await db.delete(current_user)
    await db.commit()


@router.put("/me", response_model=schemas.UserRead)
async def update_me(
    payload: schemas.UserUpdate,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.UserRead:
    if payload.email and payload.email != current_user.email:
        result = await db.execute(
            select(models.User).where(models.User.email == payload.email)
        )
        if result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use",
            )
        current_user.email = payload.email

    if payload.password:
        current_user.hashed_password = get_password_hash(payload.password)

    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post("/change-email", response_model=schemas.MessageResponse)
async def change_email(
    payload: schemas.ChangeEmailRequest,
    current_user: models.User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.MessageResponse:
    if payload.new_email == current_user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="C'est déjà votre adresse email.",
        )

    existing = await get_user_by_email(db, payload.new_email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already in use",
        )

    # Annule toute demande précédente
    result = await db.execute(
        select(models.EmailChangeRequest).where(
            models.EmailChangeRequest.user_id == current_user.id
        )
    )
    for req in result.scalars().all():
        await db.delete(req)

    confirm_token = secrets.token_urlsafe(32)
    cancel_token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=24)

    change_req = models.EmailChangeRequest(
        user_id=current_user.id,
        old_email=current_user.email,
        new_email=str(payload.new_email),
        confirm_token=confirm_token,
        cancel_token=cancel_token,
        expires_at=expires,
    )
    db.add(change_req)

    await send_email_change_confirm(str(payload.new_email), confirm_token)
    await send_email_change_cancel(current_user.email, cancel_token, str(payload.new_email))
    await db.commit()

    return schemas.MessageResponse(
        message=f"Un email de confirmation a été envoyé à {payload.new_email}."
    )


@router.get("/confirm-email-change", response_model=schemas.MessageResponse)
async def confirm_email_change(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> schemas.MessageResponse:
    result = await db.execute(
        select(models.EmailChangeRequest).where(
            models.EmailChangeRequest.confirm_token == token
        )
    )
    req = result.scalars().first()

    if not req:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lien invalide ou expiré.")

    if _is_expired(req.expires_at):
        await db.delete(req)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lien expiré.")

    user = await db.get(models.User, req.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Utilisateur introuvable.")

    user.email = req.new_email
    req.confirmed = True
    await db.commit()

    return schemas.MessageResponse(message="Adresse email mise à jour. Vous pouvez vous connecter avec votre nouvelle adresse.")


@router.get("/cancel-email-change", response_model=schemas.MessageResponse)
async def cancel_email_change(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> schemas.MessageResponse:
    result = await db.execute(
        select(models.EmailChangeRequest).where(
            models.EmailChangeRequest.cancel_token == token
        )
    )
    req = result.scalars().first()

    if not req:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lien invalide ou expiré.")

    if _is_expired(req.expires_at):
        await db.delete(req)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lien expiré.")

    user = await db.get(models.User, req.user_id)
    if user and req.confirmed:
        user.email = req.old_email

    await db.delete(req)
    await db.commit()

    return schemas.MessageResponse(message="Changement d'email annulé. Votre ancienne adresse est conservée.")


@router.post("/login", response_model=schemas.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> schemas.Token:
    user = await get_user_by_email(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email non vérifié. Vérifiez votre boîte mail.",
        )

    # Migration transparente: si le compte est encore en SHA-256, on rehash en Argon2 au premier login.
    if is_legacy_sha256_hash(user.hashed_password):
        user.hashed_password = get_password_hash(form_data.password)
        await db.commit()

    access_token = create_access_token(data={"sub": str(user.id)})
    return schemas.Token(access_token=access_token)
