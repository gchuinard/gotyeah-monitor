"""monitors.user_id : FK ON DELETE CASCADE

Aligne monitors.user_id sur les autres FK du schéma (toutes en CASCADE) : la
suppression d'un utilisateur supprime ses monitors (puis, en cascade, leurs checks
et incidents). Garantit l'atomicité même hors du chemin applicatif, qui supprimait
déjà les monitors à la main avant l'utilisateur.

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-17
"""
from alembic import op
from sqlalchemy import inspect

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

_FK_NAME = "fk_monitors_user_id_users"


def _user_id_fk(insp):
    for fk in insp.get_foreign_keys("monitors"):
        if fk.get("constrained_columns") == ["user_id"]:
            return fk
    return None


def upgrade() -> None:
    insp = inspect(op.get_bind())
    fk = _user_id_fk(insp)

    # Déjà en CASCADE (migration rejouée / DB dev créée par create_all) : rien à faire.
    if fk and (fk.get("options") or {}).get("ondelete", "").upper() == "CASCADE":
        return

    # Drop de l'ancienne FK (nom auto-généré par MySQL, ex. monitors_ibfk_1).
    if fk and fk.get("name"):
        op.drop_constraint(fk["name"], "monitors", type_="foreignkey")

    op.create_foreign_key(
        _FK_NAME, "monitors", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )


def downgrade() -> None:
    insp = inspect(op.get_bind())
    fk = _user_id_fk(insp)
    if fk and fk.get("name"):
        op.drop_constraint(fk["name"], "monitors", type_="foreignkey")
    # Recrée sans action ON DELETE (état d'origine).
    op.create_foreign_key(_FK_NAME, "monitors", "users", ["user_id"], ["id"])
