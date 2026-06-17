"""M2 : table monitor_groups + monitors.group_id (FK SET NULL)

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    return name in inspect(op.get_bind()).get_table_names()


def _column_exists(table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspect(op.get_bind()).get_columns(table))


def upgrade() -> None:
    if not _table_exists("monitor_groups"):
        op.create_table(
            "monitor_groups",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index("ix_monitor_groups_user_id", "monitor_groups", ["user_id"])

    if not _column_exists("monitors", "group_id"):
        op.add_column("monitors", sa.Column("group_id", sa.Integer(), nullable=True))
        op.create_index("ix_monitors_group_id", "monitors", ["group_id"])
        op.create_foreign_key(
            "fk_monitors_group_id_monitor_groups",
            "monitors",
            "monitor_groups",
            ["group_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    if _column_exists("monitors", "group_id"):
        op.drop_constraint("fk_monitors_group_id_monitor_groups", "monitors", type_="foreignkey")
        op.drop_index("ix_monitors_group_id", table_name="monitors")
        op.drop_column("monitors", "group_id")
    if _table_exists("monitor_groups"):
        op.drop_index("ix_monitor_groups_user_id", table_name="monitor_groups")
        op.drop_table("monitor_groups")
