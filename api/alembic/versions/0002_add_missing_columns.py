"""add missing columns and monitor_checks table

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return any(c["name"] == column for c in insp.get_columns(table))


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return table in insp.get_table_names()


def upgrade() -> None:
    # Colonnes ajoutées à monitors après la création initiale
    if not _column_exists("monitors", "last_status_code"):
        op.add_column("monitors", sa.Column("last_status_code", sa.Integer(), nullable=True))
    if not _column_exists("monitors", "last_latency_ms"):
        op.add_column("monitors", sa.Column("last_latency_ms", sa.Integer(), nullable=True))
    if not _column_exists("monitors", "last_checked_at"):
        op.add_column("monitors", sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True))
    if not _column_exists("monitors", "ssl_expiry_at"):
        op.add_column("monitors", sa.Column("ssl_expiry_at", sa.DateTime(timezone=False), nullable=True))

    # Table d'historique des checks
    if not _table_exists("monitor_checks"):
        op.create_table(
            "monitor_checks",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("monitor_id", sa.Integer(), sa.ForeignKey("monitors.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("status", sa.Enum("up", "down", name="check_status"), nullable=False),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False, index=True),
        )


def downgrade() -> None:
    op.drop_table("monitor_checks")
    op.drop_column("monitors", "ssl_expiry_at")
    op.drop_column("monitors", "last_checked_at")
    op.drop_column("monitors", "last_latency_ms")
    op.drop_column("monitors", "last_status_code")
