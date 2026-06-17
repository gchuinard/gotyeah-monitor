from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field, HttpUrl, model_validator

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
    # None = champ non fourni (pas de changement).
    alert_email_enabled: Optional[bool] = None
    # "" pour effacer le webhook ; None = champ non fourni (pas de changement).
    alert_webhook_url: Optional[str] = Field(default=None, max_length=512)
    alert_webhook_kind: Optional[WebhookKind] = None


class UserRead(UserBase):
    id: int
    created_at: datetime
    alert_email_enabled: bool = True
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
    # None = intervalle global par défaut (CHECK_INTERVAL_SECONDS côté loop)
    check_interval_seconds: Optional[int] = Field(default=None, ge=60, le=86400)
    # Check de contenu (type http) : texte attendu (present) ou interdit (absent)
    keyword: Optional[str] = Field(default=None, max_length=255)
    keyword_mode: Literal["present", "absent"] = "present"
    # Alerte si la latence dépasse ce seuil (None = pas d'alerte de latence)
    latency_threshold_ms: Optional[int] = Field(default=None, ge=1, le=600000)
    # Cible TCP pour le type 'port'
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    # Groupe d'appartenance (None = sans groupe)
    group_id: Optional[int] = None


def _require_port_for_port_type(model: "MonitorBase") -> "MonitorBase":
    # Validation côté écriture uniquement (pas sur MonitorRead) : un ancien monitor
    # 'port' sans port en base ne doit pas faire échouer la lecture.
    if model.type == "port" and model.port is None:
        raise ValueError("Le port est requis pour un monitor de type 'port'.")
    return model


class MonitorCreate(MonitorBase):
    expected_status_code: int = Field(default=200, ge=100, le=599)

    @model_validator(mode="after")
    def _validate(self) -> "MonitorCreate":
        return _require_port_for_port_type(self)


class MonitorUpdate(MonitorBase):
    expected_status_code: int = Field(default=200, ge=100, le=599)

    @model_validator(mode="after")
    def _validate(self) -> "MonitorUpdate":
        return _require_port_for_port_type(self)


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
    uptime_30d: Optional[float] = None
    uptime_90d: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MonitorGroupBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class MonitorGroupCreate(MonitorGroupBase):
    pass


class MonitorGroupUpdate(MonitorGroupBase):
    pass


class MonitorGroupRead(MonitorGroupBase):
    id: int
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


class IncidentRead(BaseModel):
    id: int
    started_at: datetime
    ended_at: Optional[datetime] = None  # None = incident en cours
    last_status_code: Optional[int] = None

    class Config:
        from_attributes = True


class SlaMonth(BaseModel):
    month: str  # "YYYY-MM"
    uptime: Optional[float] = None  # % (None si aucune donnée)


class MessageResponse(BaseModel):
    message: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)


class ChangeEmailRequest(BaseModel):
    new_email: EmailStr


class TokenRequest(BaseModel):
    # Token d'action (vérif email / changement d'email) transmis dans le CORPS et non
    # en query string, pour qu'il n'apparaisse pas dans les logs serveur/proxy.
    token: str
