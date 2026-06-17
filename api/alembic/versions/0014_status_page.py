"""M4 : page de statut publique (status_pages + monitors.is_public)

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    return name in inspect(op.get_bind()).get_table_names()


def _column_exists(table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspect(op.get_bind()).get_columns(table))


def upgrade() -> None:
    if not _column_exists("monitors", "is_public"):
        op.add_column(
            "monitors",
            sa.Column("is_public", sa.Boolean(), nullable=False, server_default="0"),
        )
    if not _table_exists("status_pages"):
        op.create_table(
            "status_pages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column("slug", sa.String(64), nullable=False),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index("ix_status_pages_slug", "status_pages", ["slug"], unique=True)


def downgrade() -> None:
    if _table_exists("status_pages"):
        op.drop_index("ix_status_pages_slug", table_name="status_pages")
        op.drop_table("status_pages")
    if _column_exists("monitors", "is_public"):
        op.drop_column("monitors", "is_public")
