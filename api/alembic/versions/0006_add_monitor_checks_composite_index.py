"""add composite index on monitor_checks(monitor_id, checked_at)

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-01
"""
from alembic import op
from sqlalchemy import inspect

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

INDEX_NAME = "ix_monitor_checks_monitor_id_checked_at"


def _index_exists(table: str, name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return any(ix["name"] == name for ix in insp.get_indexes(table))


def upgrade() -> None:
    if not _index_exists("monitor_checks", INDEX_NAME):
        op.create_index(INDEX_NAME, "monitor_checks", ["monitor_id", "checked_at"])


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="monitor_checks")
