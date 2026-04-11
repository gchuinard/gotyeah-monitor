"""add email change requests table

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return table in insp.get_table_names()


def upgrade() -> None:
    if not _table_exists("email_change_requests"):
        op.create_table(
            "email_change_requests",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("old_email", sa.String(255), nullable=False),
            sa.Column("new_email", sa.String(255), nullable=False),
            sa.Column("confirm_token", sa.String(64), nullable=False),
            sa.Column("cancel_token", sa.String(64), nullable=False),
            sa.Column("confirmed", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_email_change_requests_id", "email_change_requests", ["id"])
        op.create_index("ix_email_change_requests_user_id", "email_change_requests", ["user_id"])
        op.create_index("ix_email_change_requests_confirm_token", "email_change_requests", ["confirm_token"], unique=True)
        op.create_index("ix_email_change_requests_cancel_token", "email_change_requests", ["cancel_token"], unique=True)


def downgrade() -> None:
    op.drop_table("email_change_requests")
