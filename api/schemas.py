from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, HttpUrl


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = None


class UserRead(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MonitorBase(BaseModel):
    name: str
    url: HttpUrl
    type: str = "http"


class MonitorCreate(MonitorBase):
    expected_status_code: int = 200


class MonitorUpdate(MonitorBase):
    expected_status_code: int = 200


class MonitorRead(MonitorBase):
    id: int
    status: str
    last_latency_ms: Optional[int] = None
    last_checked_at: Optional[datetime] = None
    expected_status_code: int
    last_status_code: Optional[int] = None
    ssl_expiry_at: Optional[datetime] = None
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
