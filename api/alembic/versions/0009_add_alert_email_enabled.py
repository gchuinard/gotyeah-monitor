"""add alert_email_enabled (users)

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if not _column_exists("users", "alert_email_enabled"):
        op.add_column(
            "users",
            sa.Column("alert_email_enabled", sa.Boolean(), nullable=False, server_default="1"),
        )


def downgrade() -> None:
    op.drop_column("users", "alert_email_enabled")
