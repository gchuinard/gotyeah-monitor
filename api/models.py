from sqlalchemy import Column, Integer, String, Enum, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    monitors = relationship("Monitor", back_populates="user")


class Monitor(Base):
    __tablename__ = "monitors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    url = Column(String(512), nullable=False)
    type = Column(
        Enum("http", "ping", "port", name="monitor_type"),
        nullable=False,
        default="http",
    )
    status = Column(
        Enum("up", "down", "unknown", name="monitor_status"),
        nullable=False,
        default="unknown",
    )
    expected_status_code = Column(Integer, nullable=False, default=200)
    last_status_code = Column(Integer, nullable=True)
    last_latency_ms = Column(Integer, nullable=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    user = relationship("User", back_populates="monitors")
