"""add incidents table

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return table in insp.get_table_names()


def upgrade() -> None:
    if not _table_exists("incidents"):
        op.create_table(
            "incidents",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("monitor_id", sa.Integer(), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_status_code", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["monitor_id"], ["monitors.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_incidents_id", "incidents", ["id"])
        op.create_index("ix_incidents_monitor_id", "incidents", ["monitor_id"])


def downgrade() -> None:
    op.drop_table("incidents")
