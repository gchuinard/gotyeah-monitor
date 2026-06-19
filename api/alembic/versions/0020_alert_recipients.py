"""M8 : destinataires d'alerte (alert_recipients)

Destinataire attaché à un monitor OU un groupe (exactement un), désignant une adresse
email libre OU un membre d'équipe (exactement un). La contrainte d'exclusivité est
applicative (cf. routeur recipients), pas en base.

Revision ID: 0020
Revises: 0019
Create Date: 2026-06-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    return name in inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _table_exists("alert_recipients"):
        op.create_table(
            "alert_recipients",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "monitor_id",
                sa.Integer(),
                sa.ForeignKey("monitors.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column(
                "group_id",
                sa.Integer(),
                sa.ForeignKey("monitor_groups.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column("email", sa.String(255), nullable=True),
            sa.Column(
                "member_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index("ix_alert_recipients_monitor_id", "alert_recipients", ["monitor_id"])
        op.create_index("ix_alert_recipients_group_id", "alert_recipients", ["group_id"])
        op.create_index("ix_alert_recipients_member_user_id", "alert_recipients", ["member_user_id"])


def downgrade() -> None:
    if _table_exists("alert_recipients"):
        op.drop_index("ix_alert_recipients_member_user_id", table_name="alert_recipients")
        op.drop_index("ix_alert_recipients_group_id", table_name="alert_recipients")
        op.drop_index("ix_alert_recipients_monitor_id", table_name="alert_recipients")
        op.drop_table("alert_recipients")
