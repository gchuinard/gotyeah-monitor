"""M8 : suppression différée d'équipe (teams.deletion_scheduled_at)

Quand renseigné, l'équipe est désactivée (monitoring suspendu) et purgée après une
période de grâce (cf. main.TEAM_DELETION_GRACE_DAYS). Réactivable en remettant NULL.

Revision ID: 0023
Revises: 0022
Create Date: 2026-06-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspect(op.get_bind()).get_columns(table))


def upgrade() -> None:
    if not _column_exists("teams", "deletion_scheduled_at"):
        op.add_column(
            "teams", sa.Column("deletion_scheduled_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    if _column_exists("teams", "deletion_scheduled_at"):
        op.drop_column("teams", "deletion_scheduled_at")
