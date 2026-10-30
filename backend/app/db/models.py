"""Tables du socle : utilisateurs, sessions, journal d'audit (étape 1.4)."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    LargeBinary,
    String,
    Text,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(enum.StrEnum):
    CLIENT = "client"
    AFFILIATE = "affiliate"
    # Rôles administrateur différenciés (section 3) : accès au strict nécessaire.
    SUPER_ADMIN = "super_admin"
    SUPPORT = "support"
    FINANCE = "finance"


class UserStatus(enum.StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


def _pg_enum(cls: type[enum.StrEnum], name: str) -> Enum:
    # Valeurs en base = valeurs de l'énumération (minuscules), pas les noms Python.
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        # Unicité de l'e-mail sans tenir compte de la casse.
        Index("uq_users_email_lower", text("lower(email)"), unique=True),
        CheckConstraint("locale IN ('fr', 'en')", name="locale"),
        CheckConstraint("theme IN ('light', 'dark', 'auto')", name="theme"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Empreinte Argon2id uniquement (étape 1.5) ; jamais le mot de passe.
    password_hash: Mapped[str] = mapped_column(Text)
    first_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[UserRole] = mapped_column(
        _pg_enum(UserRole, "user_role"),
        default=UserRole.CLIENT,
        server_default=UserRole.CLIENT.value,
    )
    status: Mapped[UserStatus] = mapped_column(
        _pg_enum(UserStatus, "user_status"),
        default=UserStatus.ACTIVE,
        server_default=UserStatus.ACTIVE.value,
    )
    locale: Mapped[str] = mapped_column(String(2), default="fr", server_default="fr")
    theme: Mapped[str] = mapped_column(String(5), default="auto", server_default="auto")
    # Fuseau du client : la « journée » des limites de risque se calcule dans ce fuseau (section 7).
    time_zone: Mapped[str] = mapped_column(String(64), default="UTC", server_default="UTC")
    # Double authentification : secret chiffré (AES-256-GCM, app/crypto.py), activée ou non,
    # et dernier pas de temps accepté (un même code ne sert jamais deux fois).
    totp_secret_encrypted: Mapped[str | None] = mapped_column(Text)
    totp_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    totp_last_step: Mapped[int | None] = mapped_column(BigInteger)
    # Reconnaissance du risque de perte en capital à l'inscription (date tracée).
    risk_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Session(Base):
    """Session de connexion. Seule l'empreinte SHA-256 du jeton est stockée."""

    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_user_active", "user_id", "revoked_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    # « Se souvenir de moi » : expirations plus longues (voir app/config.py).
    remember: Mapped[bool] = mapped_column(default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(String(512))

    user: Mapped[User] = relationship(back_populates="sessions")


class AuditLog(Base):
    """
    Journal d'audit des actions sensibles. Non modifiable : un déclencheur
    PostgreSQL refuse toute mise à jour et toute suppression (voir la migration).
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_actor_occurred", "actor_user_id", "occurred_at"),
        Index("ix_audit_log_action_occurred", "action", "occurred_at"),
        CheckConstraint("result IN ('success', 'failure', 'denied')", name="result"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Pas de clé étrangère : l'audit survit à la suppression d'un compte (droit à l'effacement).
    actor_user_id: Mapped[uuid.UUID | None]
    action: Mapped[str] = mapped_column(String(100))
    target_type: Mapped[str | None] = mapped_column(String(50))
    target_id: Mapped[str | None] = mapped_column(String(100))
    result: Mapped[str] = mapped_column(String(10))
    ip_address: Mapped[str | None] = mapped_column(INET)
    # Détails sans secret ni donnée sensible (jamais de jeton, mot de passe ou token Deriv).
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default="{}")


class EmailVerificationToken(Base):
    """Lien de vérification d'e-mail : à usage unique, expirant, stocké sous forme d'empreinte."""

    __tablename__ = "email_verification_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MfaChallenge(Base):
    """Connexion en attente du code de double authentification (mot de passe déjà vérifié)."""

    __tablename__ = "mfa_challenges"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    remember: Mapped[bool] = mapped_column(default=False, server_default=false())
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RecoveryCode(Base):
    """Code de secours de la double authentification : empreinte SHA-256, usage unique."""

    __tablename__ = "recovery_codes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    code_hash: Mapped[bytes] = mapped_column(LargeBinary(32))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PasswordResetToken(Base):
    """Lien de réinitialisation du mot de passe : à usage unique, expirant, en empreinte."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
