"""add token_version to users

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if not _column_exists("users", "token_version"):
        op.add_column(
            "users",
            sa.Column(
                "token_version", sa.Integer(), nullable=False, server_default="0"
            ),
        )


def downgrade() -> None:
    op.drop_column("users", "token_version")
