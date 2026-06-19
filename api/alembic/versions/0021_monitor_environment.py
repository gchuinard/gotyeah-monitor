"""M8 : monitors.environment (étiquette prod/staging/dev ou libre)

Revision ID: 0021
Revises: 0020
Create Date: 2026-06-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspect(op.get_bind()).get_columns(table))


def upgrade() -> None:
    if not _column_exists("monitors", "environment"):
        op.add_column("monitors", sa.Column("environment", sa.String(50), nullable=True))


def downgrade() -> None:
    if _column_exists("monitors", "environment"):
        op.drop_column("monitors", "environment")
