"""M8 : créateur (user_id) en ON DELETE SET NULL sur monitors et monitor_groups

L'ownership est désormais porté par team_id. user_id n'est plus qu'un créateur (audit).
Supprimer un compte ne doit donc PAS effacer en cascade des monitors/groupes d'équipes
partagées : on relâche ces FK en SET NULL (et monitor_groups.user_id devient nullable).
Le nettoyage des équipes dont le compte est seul membre est fait côté applicatif.

Revision ID: 0022
Revises: 0021
Create Date: 2026-06-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def _user_id_fk(insp, table: str):
    for fk in insp.get_foreign_keys(table):
        if fk.get("constrained_columns") == ["user_id"]:
            return fk
    return None


def _relax_fk(table: str, fk_name: str) -> None:
    insp = inspect(op.get_bind())
    fk = _user_id_fk(insp, table)
    # Déjà en SET NULL (migration rejouée / DB dev create_all) : rien à faire.
    if fk and (fk.get("options") or {}).get("ondelete", "").upper() == "SET NULL":
        return
    if fk and fk.get("name"):
        op.drop_constraint(fk["name"], table, type_="foreignkey")
    op.create_foreign_key(fk_name, table, "users", ["user_id"], ["id"], ondelete="SET NULL")


def upgrade() -> None:
    # monitors.user_id est déjà nullable -> on relâche juste la FK.
    _relax_fk("monitors", "fk_monitors_user_id_users")
    # monitor_groups.user_id : rendre nullable PUIS relâcher la FK.
    op.alter_column(
        "monitor_groups", "user_id", existing_type=sa.Integer(), nullable=True
    )
    _relax_fk("monitor_groups", "fk_monitor_groups_user_id_users")


def downgrade() -> None:
    insp = inspect(op.get_bind())
    for table, fk_name in (
        ("monitors", "fk_monitors_user_id_users"),
        ("monitor_groups", "fk_monitor_groups_user_id_users"),
    ):
        fk = _user_id_fk(inspect(op.get_bind()), table)
        if fk and fk.get("name"):
            op.drop_constraint(fk["name"], table, type_="foreignkey")
        op.create_foreign_key(fk_name, table, "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.alter_column(
        "monitor_groups", "user_id", existing_type=sa.Integer(), nullable=False
    )
