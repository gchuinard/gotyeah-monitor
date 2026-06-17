"""M3 : table de rollup monitor_uptime_daily (uptime 30/90j + SLA)

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    return name in inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _table_exists("monitor_uptime_daily"):
        op.create_table(
            "monitor_uptime_daily",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "monitor_id",
                sa.Integer(),
                sa.ForeignKey("monitors.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("day", sa.Date(), nullable=False),
            sa.Column("up_count", sa.Integer(), nullable=False),
            sa.Column("total_count", sa.Integer(), nullable=False),
            sa.UniqueConstraint("monitor_id", "day", name="uq_monitor_uptime_daily_monitor_day"),
        )
        op.create_index("ix_monitor_uptime_daily_monitor_id", "monitor_uptime_daily", ["monitor_id"])


def downgrade() -> None:
    if _table_exists("monitor_uptime_daily"):
        op.drop_index("ix_monitor_uptime_daily_monitor_id", table_name="monitor_uptime_daily")
        op.drop_table("monitor_uptime_daily")
