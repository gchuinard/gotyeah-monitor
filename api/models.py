from sqlalchemy import Column, Integer, String, Text, Enum, DateTime, Date, Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    # Divergence volontaire de server_default : le modèle/create_all (dev) pose "0"
    # (nouveaux comptes non vérifiés), alors que la migration 0003 (prod) a posé "1"
    # pour grandfather les comptes pré-existants lors de l'ajout de la colonne. Sans
    # impact : l'app fournit toujours is_verified explicitement à l'INSERT (register),
    # le DEFAULT SQL n'est donc jamais sollicité.
    is_verified = Column(Boolean, nullable=False, default=False, server_default="0")
    # Incrémenté à chaque reset de mot de passe / changement d'email confirmé :
    # invalide les JWT émis avant (le token porte la version, vérifiée au login check).
    token_version = Column(Integer, nullable=False, default=0, server_default="0")
    # Alertes par email (panne / rétablissement / SSL) : activées par défaut,
    # l'utilisateur peut les couper (ex. s'il ne veut que le webhook).
    alert_email_enabled = Column(Boolean, nullable=False, default=True, server_default="1")
    # Canal d'alerte optionnel (en plus de l'email) : Discord / Slack / ntfy / générique.
    alert_webhook_url = Column(String(512), nullable=True)
    alert_webhook_kind = Column(String(20), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    monitors = relationship("Monitor", back_populates="user")
    monitor_groups = relationship("MonitorGroup", back_populates="user", cascade="all, delete-orphan")
    status_page = relationship("StatusPage", back_populates="user", uselist=False, cascade="all, delete-orphan")
    email_verifications = relationship("EmailVerification", back_populates="user", cascade="all, delete-orphan")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")
    email_change_requests = relationship("EmailChangeRequest", back_populates="user", cascade="all, delete-orphan")


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
    # M1 : configuration de check étendue
    check_interval_seconds = Column(Integer, nullable=True)  # None = défaut global (CHECK_INTERVAL_SECONDS)
    keyword = Column(String(255), nullable=True)  # texte attendu/interdit dans la réponse (type http)
    keyword_mode = Column(String(10), nullable=False, default="present", server_default="present")  # present|absent
    latency_threshold_ms = Column(Integer, nullable=True)  # alerte si latence au-dessus (None = off)
    port = Column(Integer, nullable=True)  # cible TCP pour le type 'port'
    last_status_code = Column(Integer, nullable=True)
    last_latency_ms = Column(Integer, nullable=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    ssl_expiry_at = Column(DateTime(timezone=False), nullable=True)
    # État pour l'alerting (anti-flapping + non-répétition)
    consecutive_failures = Column(Integer, nullable=False, default=0, server_default="0")
    down_alert_sent = Column(Boolean, nullable=False, default=False, server_default="0")
    down_since = Column(DateTime(timezone=True), nullable=True)
    ssl_alert_level = Column(Integer, nullable=True)  # dernier palier SSL (jours) alerté
    latency_alert_sent = Column(Boolean, nullable=False, default=False, server_default="0")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    user = relationship("User", back_populates="monitors")
    # Groupe d'appartenance : SET NULL -> supprimer un groupe dégroupe ses monitors
    # (ne les supprime pas).
    group_id = Column(Integer, ForeignKey("monitor_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    group = relationship("MonitorGroup", back_populates="monitors")
    # Exposé sur la page de statut publique (sinon privé)
    is_public = Column(Boolean, nullable=False, default=False, server_default="0")
    checks = relationship("MonitorCheck", back_populates="monitor", cascade="all, delete-orphan")
    incidents = relationship("Incident", back_populates="monitor", cascade="all, delete-orphan")
    maintenance_windows = relationship("MaintenanceWindow", back_populates="monitor", cascade="all, delete-orphan")

    # Non mappés (pas des colonnes) : remplis à la lecture par le routeur via une
    # agrégation SQL, exposés via MonitorRead. Défaut None si pas calculé.
    uptime_24h = None
    uptime_7d = None
    uptime_30d = None
    uptime_90d = None
    # Défaut False (pas None) : les routes qui ne le calculent pas sérialisent un bool valide.
    in_maintenance = False


class MonitorGroup(Base):
    # 'groups' est un mot réservé MySQL 8 -> table préfixée 'monitor_groups'.
    __tablename__ = "monitor_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="monitor_groups")
    monitors = relationship("Monitor", back_populates="group")


class StatusPage(Base):
    # Page de statut publique de l'utilisateur (une par user), accessible via /status/{slug}.
    __tablename__ = "status_pages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    slug = Column(String(64), nullable=False, unique=True, index=True)
    title = Column(String(255), nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="status_page")


class MaintenanceWindow(Base):
    # Fenêtre de maintenance planifiée : pendant [start_at, end_at], alertes et
    # ouvertures d'incident sont muettes pour le monitor (les checks continuent).
    __tablename__ = "maintenance_windows"

    id = Column(Integer, primary_key=True, index=True)
    monitor_id = Column(
        Integer, ForeignKey("monitors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=False)
    label = Column(String(255), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    monitor = relationship("Monitor", back_populates="maintenance_windows")


class MonitorCheck(Base):
    __tablename__ = "monitor_checks"
    # Index composite pour la requête d'historique (WHERE monitor_id=? ORDER BY checked_at).
    __table_args__ = (
        Index("ix_monitor_checks_monitor_id_checked_at", "monitor_id", "checked_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    monitor_id = Column(
        Integer, ForeignKey("monitors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status = Column(
        Enum("up", "down", name="check_status"), nullable=False
    )
    latency_ms = Column(Integer, nullable=True)
    checked_at = Column(DateTime(timezone=True), nullable=False, index=True)

    monitor = relationship("Monitor", back_populates="checks")


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    monitor_id = Column(
        Integer, ForeignKey("monitors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)  # NULL = incident en cours
    last_status_code = Column(Integer, nullable=True)
    # M6 : workflow incident
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)  # NULL = non acquitté
    postmortem = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    monitor = relationship("Monitor", back_populates="incidents")


class MonitorUptimeDaily(Base):
    # Rollup quotidien des checks (1 ligne par monitor et par jour) : base de l'uptime
    # 30j/90j et du SLA, alimenté avant que la rétention 7j ne purge monitor_checks.
    __tablename__ = "monitor_uptime_daily"
    __table_args__ = (
        UniqueConstraint("monitor_id", "day", name="uq_monitor_uptime_daily_monitor_day"),
    )

    id = Column(Integer, primary_key=True, index=True)
    monitor_id = Column(
        Integer, ForeignKey("monitors.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day = Column(Date, nullable=False)
    up_count = Column(Integer, nullable=False)
    total_count = Column(Integer, nullable=False)


class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="email_verifications")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="password_reset_tokens")


class EmailChangeRequest(Base):
    __tablename__ = "email_change_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    old_email = Column(String(255), nullable=False)
    new_email = Column(String(255), nullable=False)
    confirm_token = Column(String(64), nullable=False, unique=True, index=True)
    cancel_token = Column(String(64), nullable=False, unique=True, index=True)
    confirmed = Column(Boolean, nullable=False, default=False, server_default="0")
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="email_change_requests")
