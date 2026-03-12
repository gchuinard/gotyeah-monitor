from datetime import datetime, timedelta, timezone
from typing import Optional
import hashlib
import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
import models
import schemas


SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not set")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


router = APIRouter(prefix="/auth", tags=["auth"])


pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
)


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


@router.post("/register", response_model=schemas.UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: schemas.UserCreate, db: AsyncSession = Depends(get_db)
) -> schemas.UserRead:
    existing = await get_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = models.User(
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


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

    # Migration transparente: si le compte est encore en SHA-256, on rehash en Argon2 au premier login.
    if is_legacy_sha256_hash(user.hashed_password):
        user.hashed_password = get_password_hash(form_data.password)
        await db.commit()

    access_token = create_access_token(data={"sub": str(user.id)})
    return schemas.Token(access_token=access_token)

