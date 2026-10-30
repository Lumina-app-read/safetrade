"""Socle : utilisateurs, sessions, journal d'audit (étape 1.4).

Revision ID: 0001
Revises:
Create Date: 2026-10-30 04:04:59
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

USER_ROLE = postgresql.ENUM(
    "client", "affiliate", "super_admin", "support", "finance", name="user_role"
)
USER_STATUS = postgresql.ENUM("active", "suspended", name="user_status")


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=True),
        sa.Column("target_id", sa.String(length=100), nullable=True),
        sa.Column("result", sa.String(length=10), nullable=False),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column(
            "details", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.CheckConstraint(
            "result IN ('success', 'failure', 'denied')", name=op.f("ck_audit_log_result")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index("ix_audit_log_action_occurred", "audit_log", ["action", "occurred_at"])
    op.create_index("ix_audit_log_actor_occurred", "audit_log", ["actor_user_id", "occurred_at"])

    # Journal non modifiable (section 14) : toute modification ou suppression est refusée
    # par la base elle-même, quel que soit le code applicatif.
    op.execute(
        """
        CREATE FUNCTION audit_log_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log est en ajout seul (% refusé)', TG_OP
                USING ERRCODE = 'insufficient_privilege';
        END;
        $$;
        CREATE TRIGGER audit_log_no_update_delete
            BEFORE UPDATE OR DELETE ON audit_log
            FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();
        CREATE TRIGGER audit_log_no_truncate
            BEFORE TRUNCATE ON audit_log
            FOR EACH STATEMENT EXECUTE FUNCTION audit_log_immutable();
        """
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("role", USER_ROLE, server_default="client", nullable=False),
        sa.Column("status", USER_STATUS, server_default="active", nullable=False),
        sa.Column("locale", sa.String(length=2), server_default="fr", nullable=False),
        sa.Column("theme", sa.String(length=5), server_default="auto", nullable=False),
        sa.Column("time_zone", sa.String(length=64), server_default="UTC", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("locale IN ('fr', 'en')", name=op.f("ck_users_locale")),
        sa.CheckConstraint("theme IN ('light', 'dark', 'auto')", name=op.f("ck_users_theme")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(
        "uq_users_email_lower", "users", [sa.literal_column("lower(email)")], unique=True
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sessions_token_hash")),
    )
    op.create_index("ix_sessions_user_active", "sessions", ["user_id", "revoked_at"])


def downgrade() -> None:
    op.drop_index("ix_sessions_user_active", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_table("users")
    USER_STATUS.drop(op.get_bind(), checkfirst=True)
    USER_ROLE.drop(op.get_bind(), checkfirst=True)
    # La suppression de la table emporte ses déclencheurs ; la fonction reste à supprimer.
    op.drop_index("ix_audit_log_actor_occurred", table_name="audit_log")
    op.drop_index("ix_audit_log_action_occurred", table_name="audit_log")
    op.drop_table("audit_log")
    op.execute("DROP FUNCTION audit_log_immutable()")
