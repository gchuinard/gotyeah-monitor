"""M8 : équipes (teams + team_members) + backfill équipe personnelle par user

Chaque user existant reçoit une équipe personnelle ("Mon espace") dont il est admin.
Le webhook d'alerte (jusque-là par-user) et le drapeau alert_email_enabled sont copiés
sur l'équipe / l'appartenance.

Revision ID: 0018
Revises: 0017
Create Date: 2026-06-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    return name in inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _table_exists("teams"):
        op.create_table(
            "teams",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("alert_webhook_url", sa.String(512), nullable=True),
            sa.Column("alert_webhook_kind", sa.String(20), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )

    if not _table_exists("team_members"):
        op.create_table(
            "team_members",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "team_id",
                sa.Integer(),
                sa.ForeignKey("teams.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "role",
                sa.Enum("admin", "member", "readonly", name="team_role"),
                nullable=False,
                server_default="member",
            ),
            sa.Column(
                "alert_email_enabled",
                sa.Boolean(),
                nullable=False,
                server_default="1",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.UniqueConstraint("team_id", "user_id", name="uq_team_members_team_user"),
        )
        op.create_index("ix_team_members_team_id", "team_members", ["team_id"])
        op.create_index("ix_team_members_user_id", "team_members", ["user_id"])

    # Backfill : une équipe personnelle par user (admin), idempotent (saute les users
    # qui ont déjà une appartenance). lastrowid fonctionne sur MySQL et SQLite.
    conn = op.get_bind()
    users = conn.execute(
        sa.text(
            "SELECT id, alert_email_enabled, alert_webhook_url, alert_webhook_kind FROM users"
        )
    ).fetchall()
    for u in users:
        already = conn.execute(
            sa.text("SELECT 1 FROM team_members WHERE user_id = :uid LIMIT 1"),
            {"uid": u.id},
        ).first()
        if already:
            continue
        res = conn.execute(
            sa.text(
                "INSERT INTO teams (name, alert_webhook_url, alert_webhook_kind) "
                "VALUES (:name, :wu, :wk)"
            ),
            {"name": "Mon espace", "wu": u.alert_webhook_url, "wk": u.alert_webhook_kind},
        )
        team_id = res.lastrowid
        conn.execute(
            sa.text(
                "INSERT INTO team_members (team_id, user_id, role, alert_email_enabled) "
                "VALUES (:tid, :uid, 'admin', :ee)"
            ),
            {"tid": team_id, "uid": u.id, "ee": u.alert_email_enabled},
        )


def downgrade() -> None:
    if _table_exists("team_members"):
        op.drop_index("ix_team_members_user_id", table_name="team_members")
        op.drop_index("ix_team_members_team_id", table_name="team_members")
        op.drop_table("team_members")
    if _table_exists("teams"):
        op.drop_table("teams")
