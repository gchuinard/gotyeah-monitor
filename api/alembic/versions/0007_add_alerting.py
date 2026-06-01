"""add alerting state (monitors) and webhook config (users)

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if not _column_exists("monitors", "consecutive_failures"):
        op.add_column(
            "monitors",
            sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        )
    if not _column_exists("monitors", "down_alert_sent"):
        op.add_column(
            "monitors",
            sa.Column("down_alert_sent", sa.Boolean(), nullable=False, server_default="0"),
        )
    if not _column_exists("monitors", "down_since"):
        op.add_column(
            "monitors",
            sa.Column("down_since", sa.DateTime(timezone=True), nullable=True),
        )
    if not _column_exists("monitors", "ssl_alert_level"):
        op.add_column(
            "monitors",
            sa.Column("ssl_alert_level", sa.Integer(), nullable=True),
        )
    if not _column_exists("users", "alert_webhook_url"):
        op.add_column(
            "users",
            sa.Column("alert_webhook_url", sa.String(512), nullable=True),
        )
    if not _column_exists("users", "alert_webhook_kind"):
        op.add_column(
            "users",
            sa.Column("alert_webhook_kind", sa.String(20), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("users", "alert_webhook_kind")
    op.drop_column("users", "alert_webhook_url")
    op.drop_column("monitors", "ssl_alert_level")
    op.drop_column("monitors", "down_since")
    op.drop_column("monitors", "down_alert_sent")
    op.drop_column("monitors", "consecutive_failures")
