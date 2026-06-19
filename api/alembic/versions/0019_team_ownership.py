"""M8 : team_id sur monitors / monitor_groups + backfill

L'autorité d'ownership passe du user (created_by, conservé) à l'équipe. Backfill :
chaque ressource est rattachée à l'équipe où son propriétaire (user_id) est admin
(son équipe personnelle créée en 0018). La page de statut reste par-utilisateur.

Revision ID: 0019
Revises: 0018
Create Date: 2026-06-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspect(op.get_bind()).get_columns(table))


# Rattache les lignes de `table` (avec une colonne user_id) à l'équipe perso de leur
# propriétaire. Sous-requête corrélée : compatible MySQL et SQLite.
def _backfill_team_id(table: str) -> None:
    op.get_bind().execute(
        sa.text(
            f"UPDATE {table} SET team_id = ("
            "  SELECT tm.team_id FROM team_members tm"
            f"  WHERE tm.user_id = {table}.user_id AND tm.role = 'admin'"
            "  LIMIT 1"
            ") WHERE team_id IS NULL AND user_id IS NOT NULL"
        )
    )


def upgrade() -> None:
    # monitors.team_id
    if not _column_exists("monitors", "team_id"):
        op.add_column("monitors", sa.Column("team_id", sa.Integer(), nullable=True))
        op.create_index("ix_monitors_team_id", "monitors", ["team_id"])
        op.create_foreign_key(
            "fk_monitors_team_id_teams", "monitors", "teams",
            ["team_id"], ["id"], ondelete="CASCADE",
        )
        _backfill_team_id("monitors")

    # monitor_groups.team_id
    if not _column_exists("monitor_groups", "team_id"):
        op.add_column("monitor_groups", sa.Column("team_id", sa.Integer(), nullable=True))
        op.create_index("ix_monitor_groups_team_id", "monitor_groups", ["team_id"])
        op.create_foreign_key(
            "fk_monitor_groups_team_id_teams", "monitor_groups", "teams",
            ["team_id"], ["id"], ondelete="CASCADE",
        )
        _backfill_team_id("monitor_groups")


def downgrade() -> None:
    if _column_exists("monitor_groups", "team_id"):
        op.drop_constraint("fk_monitor_groups_team_id_teams", "monitor_groups", type_="foreignkey")
        op.drop_index("ix_monitor_groups_team_id", table_name="monitor_groups")
        op.drop_column("monitor_groups", "team_id")
    if _column_exists("monitors", "team_id"):
        op.drop_constraint("fk_monitors_team_id_teams", "monitors", type_="foreignkey")
        op.drop_index("ix_monitors_team_id", table_name="monitors")
        op.drop_column("monitors", "team_id")
