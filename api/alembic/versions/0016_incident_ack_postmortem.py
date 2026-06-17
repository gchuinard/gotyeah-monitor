"""M6 : acquittement + post-mortem d'incident

Revision ID: 0016
Revises: 0015
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspect(op.get_bind()).get_columns(table))


def upgrade() -> None:
    if not _column_exists("incidents", "acknowledged_at"):
        op.add_column(
            "incidents", sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True)
        )
    if not _column_exists("incidents", "postmortem"):
        op.add_column("incidents", sa.Column("postmortem", sa.Text(), nullable=True))


def downgrade() -> None:
    for col in ("postmortem", "acknowledged_at"):
        if _column_exists("incidents", col):
            op.drop_column("incidents", col)
