"""acces admin et abonnements manuels

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-04 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("admin_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sessions", sa.Column("admin_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sessions", sa.Column("admin_ip", postgresql.INET(), nullable=True))
    op.add_column("subscriptions", sa.Column("granted_by", sa.Uuid(), nullable=True))
    op.add_column("subscriptions", sa.Column("grant_note", sa.String(length=300), nullable=True))
    op.add_column(
        "subscriptions", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("subscriptions", sa.Column("revoked_by", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_subscriptions_granted_by_users", "subscriptions", "users", ["granted_by"], ["id"]
    )
    op.create_foreign_key(
        "fk_subscriptions_revoked_by_users", "subscriptions", "users", ["revoked_by"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_subscriptions_revoked_by_users", "subscriptions", type_="foreignkey")
    op.drop_constraint("fk_subscriptions_granted_by_users", "subscriptions", type_="foreignkey")
    op.drop_column("subscriptions", "revoked_by")
    op.drop_column("subscriptions", "revoked_at")
    op.drop_column("subscriptions", "grant_note")
    op.drop_column("subscriptions", "granted_by")
    op.drop_column("sessions", "admin_ip")
    op.drop_column("sessions", "admin_seen_at")
    op.drop_column("sessions", "admin_until")
