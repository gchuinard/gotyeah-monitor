"""M5 : fenêtres de maintenance (maintenance_windows)

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    return name in inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _table_exists("maintenance_windows"):
        op.create_table(
            "maintenance_windows",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "monitor_id",
                sa.Integer(),
                sa.ForeignKey("monitors.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("label", sa.String(255), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_maintenance_windows_monitor_id", "maintenance_windows", ["monitor_id"]
        )


def downgrade() -> None:
    if _table_exists("maintenance_windows"):
        op.drop_index("ix_maintenance_windows_monitor_id", table_name="maintenance_windows")
        op.drop_table("maintenance_windows")
