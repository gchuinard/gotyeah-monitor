"""M1 : champs de check étendus sur monitors

Ajoute : check_interval_seconds (intervalle par monitor), keyword + keyword_mode
(check de contenu), latency_threshold_ms (+ latency_alert_sent, état anti-répétition),
port (cible TCP du type 'port').

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    insp = inspect(op.get_bind())
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if not _column_exists("monitors", "check_interval_seconds"):
        op.add_column("monitors", sa.Column("check_interval_seconds", sa.Integer(), nullable=True))
    if not _column_exists("monitors", "keyword"):
        op.add_column("monitors", sa.Column("keyword", sa.String(255), nullable=True))
    if not _column_exists("monitors", "keyword_mode"):
        op.add_column(
            "monitors",
            sa.Column("keyword_mode", sa.String(10), nullable=False, server_default="present"),
        )
    if not _column_exists("monitors", "latency_threshold_ms"):
        op.add_column("monitors", sa.Column("latency_threshold_ms", sa.Integer(), nullable=True))
    if not _column_exists("monitors", "port"):
        op.add_column("monitors", sa.Column("port", sa.Integer(), nullable=True))
    if not _column_exists("monitors", "latency_alert_sent"):
        op.add_column(
            "monitors",
            sa.Column("latency_alert_sent", sa.Boolean(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    for col in (
        "latency_alert_sent",
        "port",
        "latency_threshold_ms",
        "keyword_mode",
        "keyword",
        "check_interval_seconds",
    ):
        if _column_exists("monitors", col):
            op.drop_column("monitors", col)
