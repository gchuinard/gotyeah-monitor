from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, HttpUrl

# Borne haute sur le mot de passe : Argon2 n'a pas de limite, mais hacher une
# valeur énorme est un vecteur de DoS (coût CPU). 8 mini = minimum raisonnable.
PASSWORD_MIN = 8
PASSWORD_MAX = 128


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)


WebhookKind = Literal["discord", "slack", "ntfy", "generic"]


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(default=None, min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)
    # "" pour effacer le webhook ; None = champ non fourni (pas de changement).
    alert_webhook_url: Optional[str] = Field(default=None, max_length=512)
    alert_webhook_kind: Optional[WebhookKind] = None


class UserRead(UserBase):
    id: int
    created_at: datetime
    alert_webhook_url: Optional[str] = None
    alert_webhook_kind: Optional[str] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MonitorBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    url: HttpUrl
    type: Literal["http", "ping", "port"] = "http"


class MonitorCreate(MonitorBase):
    expected_status_code: int = Field(default=200, ge=100, le=599)


class MonitorUpdate(MonitorBase):
    expected_status_code: int = Field(default=200, ge=100, le=599)


class MonitorRead(MonitorBase):
    id: int
    status: str
    last_latency_ms: Optional[int] = None
    last_checked_at: Optional[datetime] = None
    expected_status_code: int
    last_status_code: Optional[int] = None
    ssl_expiry_at: Optional[datetime] = None
    # Pourcentage de disponibilité (None si aucun check sur la fenêtre).
    uptime_24h: Optional[float] = None
    uptime_7d: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UserWithMonitors(UserRead):
    monitors: List[MonitorRead] = []


class MonitorCheckRead(BaseModel):
    id: int
    status: str
    latency_ms: Optional[int] = None
    checked_at: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    message: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)


class ChangeEmailRequest(BaseModel):
    new_email: EmailStr
