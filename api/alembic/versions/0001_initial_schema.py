"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "monitors",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(512), nullable=False),
        sa.Column("type", sa.Enum("http", "ping", "port", name="monitor_type"), nullable=False, server_default="http"),
        sa.Column("status", sa.Enum("up", "down", "unknown", name="monitor_status"), nullable=False, server_default="unknown"),
        sa.Column("expected_status_code", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("last_status_code", sa.Integer(), nullable=True),
        sa.Column("last_latency_ms", sa.Integer(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ssl_expiry_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, index=True),
    )

    op.create_table(
        "monitor_checks",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("monitor_id", sa.Integer(), sa.ForeignKey("monitors.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("status", sa.Enum("up", "down", name="check_status"), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table("monitor_checks")
    op.drop_table("monitors")
    op.drop_table("users")
