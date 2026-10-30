"""Connexion du compte Deriv (etape 2.3).

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-31 01:40:27.873415
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "deriv_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("auth_method", sa.String(length=10), nullable=False),
        sa.Column("token_encrypted", sa.Text(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("account_id", sa.String(length=50), nullable=True),
        sa.Column("account_kind", sa.String(length=10), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
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
        sa.CheckConstraint(
            "account_kind IN ('demo', 'real')", name=op.f("ck_deriv_connections_account_kind")
        ),
        sa.CheckConstraint(
            "auth_method IN ('pat', 'oauth')", name=op.f("ck_deriv_connections_auth_method")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_deriv_connections_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deriv_connections")),
        sa.UniqueConstraint("user_id", name=op.f("uq_deriv_connections_user_id")),
    )


def downgrade() -> None:
    op.drop_table("deriv_connections")
