"""Tables du socle : utilisateurs, sessions, journal d'audit (étape 1.4)."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
    true,
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
    # Actifs de la barre de trading, dans l'ordre choisi. Vide : les actifs par défaut.
    market_watchlist: Mapped[list[str] | None] = mapped_column(JSONB)
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
    # Empreinte du cookie d'appareil : sert à refuser l'auto-parrainage (section 13).
    device_hash: Mapped[bytes | None] = mapped_column(LargeBinary(32), index=True)

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


class DerivConnectionRecord(Base):
    """Compte Deriv connecté : un par client. Jeton chiffré, jamais renvoyé au front-end."""

    __tablename__ = "deriv_connections"
    __table_args__ = (
        CheckConstraint("auth_method IN ('pat', 'oauth')", name="auth_method"),
        CheckConstraint("account_kind IN ('demo', 'real')", name="account_kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    auth_method: Mapped[str] = mapped_column(String(10))
    token_encrypted: Mapped[str] = mapped_column(Text)
    # Issue de `expires_in` pour OAuth ; aucune expiration annoncée pour un PAT.
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    account_id: Mapped[str | None] = mapped_column(String(50))
    account_kind: Mapped[str | None] = mapped_column(String(10))
    currency: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


Money = Numeric(14, 2)


class BotState(enum.StrEnum):
    STARTING = "starting"
    ANALYZING = "analyzing"
    POSITION_OPEN = "position_open"
    PAUSED = "paused"
    TARGET_REACHED = "target_reached"
    LIMIT_REACHED = "limit_reached"
    ERROR = "error"
    STOPPING = "stopping"
    STOPPED = "stopped"


class PositionStatus(enum.StrEnum):
    OPENING = "opening"  # enregistrée avant tout envoi
    UNKNOWN = "unknown"  # envoyée, issue incertaine : statement obligatoire
    OPEN = "open"
    CLOSED = "closed"
    VOID = "void"  # jamais exécutée


class TradingSettings(Base):
    """Paramètres de risque du client. Bornes appliquées par `app.trading.risk`."""

    __tablename__ = "trading_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    stake: Mapped[Decimal] = mapped_column(Money)
    multiplier: Mapped[int] = mapped_column(Integer)
    capital_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    max_positions: Mapped[int] = mapped_column(Integer)
    stop_loss_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    session_target_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    session_loss_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    daily_target_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    daily_loss_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    max_consecutive_losses: Mapped[int] = mapped_column(Integer)
    pause_minutes: Mapped[int] = mapped_column(Integer)
    activation_r: Mapped[Decimal] = mapped_column(Numeric(6, 3))
    locked_fraction: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    allowed_symbols: Mapped[list[str]] = mapped_column(JSONB)
    timezone: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BotSession(Base):
    """Une exécution du bot. L'index partiel interdit deux bots actifs sur un compte."""

    __tablename__ = "bot_sessions"
    __table_args__ = (
        Index(
            "uq_bot_sessions_active_account",
            "account_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
        Index("ix_bot_sessions_user_started", "user_id", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    account_id: Mapped[str] = mapped_column(String(50))
    account_kind: Mapped[str] = mapped_column(String(10))
    symbol: Mapped[str] = mapped_column(String(30))
    state: Mapped[str] = mapped_column(String(20), default=BotState.STARTING)
    # Demande du client, lue et effacée par le moteur.
    command: Mapped[str | None] = mapped_column(String(20))
    stop_reason: Mapped[str | None] = mapped_column(String(50))
    error_code: Mapped[str | None] = mapped_column(String(80))
    # Signal de vie du moteur : le client voit s'il est réellement suivi.
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deriv_connected: Mapped[bool] = mapped_column(server_default=false())
    start_balance: Mapped[Decimal | None] = mapped_column(Money)
    paused_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TradingPosition(Base):
    """
    Écrite avant tout envoi à Deriv. Un seul ordre en attente par compte : un second achat
    est impossible tant qu'une issue reste inconnue, même après un redémarrage.
    """

    __tablename__ = "trading_positions"
    __table_args__ = (
        Index(
            "uq_trading_positions_pending_account",
            "account_id",
            unique=True,
            postgresql_where=text("status IN ('opening', 'unknown')"),
        ),
        Index("ix_trading_positions_session", "session_id", "status"),
        Index("ix_trading_positions_user_closed", "user_id", "closed_at"),
        UniqueConstraint("contract_id", name="uq_trading_positions_contract"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bot_sessions.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    account_id: Mapped[str] = mapped_column(String(50))
    symbol: Mapped[str] = mapped_column(String(30))
    direction: Mapped[str] = mapped_column(String(10))
    stake: Mapped[Decimal] = mapped_column(Money)
    multiplier: Mapped[int] = mapped_column(Integer)
    stop_loss: Mapped[Decimal] = mapped_column(Money)
    status: Mapped[str] = mapped_column(String(10), default=PositionStatus.OPENING)
    contract_id: Mapped[int | None] = mapped_column(BigInteger)
    buy_price: Mapped[Decimal | None] = mapped_column(Money)
    commission: Mapped[Decimal | None] = mapped_column(Money)
    current_stop: Mapped[Decimal | None] = mapped_column(Money)
    entry_spot: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    stop_spot: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    current_profit: Mapped[Decimal | None] = mapped_column(Money)
    peak_profit: Mapped[Decimal] = mapped_column(Money, default=Decimal(0))
    close_requested: Mapped[bool] = mapped_column(server_default=false())
    close_reason: Mapped[str | None] = mapped_column(String(50))
    sell_price: Mapped[Decimal | None] = mapped_column(Money)
    net_result: Mapped[Decimal | None] = mapped_column(Money)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TradingDecision(Base):
    """Journal des décisions avec leurs données d'entrée, en ajout seul."""

    __tablename__ = "trading_decisions"
    __table_args__ = (Index("ix_trading_decisions_session", "session_id", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bot_sessions.id"))
    position_id: Mapped[uuid.UUID | None]
    kind: Mapped[str] = mapped_column(String(30))
    code: Mapped[str | None] = mapped_column(String(80))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Plan(Base):
    """Formules et durée de l'essai : des données, modifiables sans changer le code."""

    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    duration_days: Mapped[int] = mapped_column(Integer)
    price: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3))
    active: Mapped[bool] = mapped_column(server_default=true())


class PaymentOrder(Base):
    __tablename__ = "payment_orders"
    __table_args__ = (
        UniqueConstraint("provider", "provider_ref", name="uq_payment_orders_provider_ref"),
        Index("ix_payment_orders_user", "user_id", "created_at"),
        Index("ix_payment_orders_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    plan_code: Mapped[str] = mapped_column(ForeignKey("plans.code"))
    provider: Mapped[str] = mapped_column(String(20))
    amount: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(12), default="pending")
    provider_ref: Mapped[str | None] = mapped_column(String(80))
    checkout_url: Mapped[str | None] = mapped_column(Text)
    amount_received: Mapped[Decimal | None] = mapped_column(Money)
    # Ce que le fournisseur doit encaisser : devise du produit, figée à la création de la vente.
    product_ref: Mapped[str | None] = mapped_column(String(80))
    expected_amount: Mapped[Decimal | None] = mapped_column(Money)
    expected_currency: Mapped[str | None] = mapped_column(String(3))
    # Ce que le client a réellement payé, dans sa devise. Informatif : jamais comparé au prix.
    paid_amount: Mapped[Decimal | None] = mapped_column(Money)
    paid_currency: Mapped[str | None] = mapped_column(String(3))
    # Empreinte du téléphone du payeur, jamais le numéro : détecte un même moyen de paiement.
    payer_hash: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Subscription(Base):
    """Une ligne par période d'accès. L'unicité sur `order_id` empêche un double crédit."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("ix_subscriptions_user_ends", "user_id", "ends_at"),
        Index(
            "uq_subscriptions_one_trial",
            "user_id",
            unique=True,
            postgresql_where=text("plan_code = 'trial'"),
        ),
        UniqueConstraint("order_id", name="uq_subscriptions_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    plan_code: Mapped[str] = mapped_column(ForeignKey("plans.code"))
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payment_orders.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PaymentEvent(Base):
    """Notifications reçues, en ajout seul. Aucune donnée personnelle du payeur."""

    __tablename__ = "payment_events"
    __table_args__ = (
        UniqueConstraint("provider", "delivery_id", name="uq_payment_events_delivery"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    provider: Mapped[str] = mapped_column(String(20))
    delivery_id: Mapped[str] = mapped_column(String(120))
    event: Mapped[str] = mapped_column(String(50))
    order_id: Mapped[uuid.UUID | None]
    reference: Mapped[str] = mapped_column(String(80))
    amount: Mapped[Decimal | None] = mapped_column(Money)
    currency: Mapped[str | None] = mapped_column(String(3))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AffiliateProgram(Base):
    """Barème unique de l'affiliation : une seule ligne, modifiable dans l'administration."""

    __tablename__ = "affiliate_program"
    __table_args__ = (CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    rate_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    # Faux : premier paiement du filleul uniquement. Vrai : chaque paiement.
    recurring: Mapped[bool] = mapped_column(server_default=false())
    attribution_days: Mapped[int] = mapped_column(Integer)
    hold_days: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Affiliate(Base):
    """Demande d'affiliation, puis compte d'affilié. Une seule ligne par utilisateur."""

    __tablename__ = "affiliates"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_affiliates_user"),
        UniqueConstraint("code", name="uq_affiliates_code"),
        Index("ix_affiliates_status", "status"),
        CheckConstraint("status IN ('pending', 'approved', 'refused', 'suspended')", name="status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(10), default="pending")
    # Attribué à la première approbation, conservé ensuite : un lien publié reste le même.
    code: Mapped[str | None] = mapped_column(String(16))
    message: Mapped[str] = mapped_column(String(500))
    payout_details: Mapped[str] = mapped_column(String(200))
    payout_hash: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    terms_accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Note interne de l'administrateur, jamais montrée au client.
    review_note: Mapped[str | None] = mapped_column(String(300))
    reviewed_by: Mapped[uuid.UUID | None]
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Referral(Base):
    """Rattachement d'un filleul : unique, décidé une seule fois à l'inscription."""

    __tablename__ = "referrals"
    __table_args__ = (
        UniqueConstraint("referred_user_id", name="uq_referrals_referred"),
        Index("ix_referrals_affiliate", "affiliate_id", "attributed_at"),
        CheckConstraint("status IN ('active', 'review', 'blocked')", name="status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    affiliate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("affiliates.id"))
    referred_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(10), default="active")
    reason: Mapped[str | None] = mapped_column(String(30))
    attributed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AffiliatePayout(Base):
    """Versement validé par un administrateur, en ajout seul. Montant calculé par le serveur."""

    __tablename__ = "affiliate_payouts"
    __table_args__ = (Index("ix_affiliate_payouts_affiliate", "affiliate_id", "paid_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    affiliate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("affiliates.id"))
    amount: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3))
    method: Mapped[str] = mapped_column(String(20))
    reference: Mapped[str] = mapped_column(String(120))
    paid_by: Mapped[uuid.UUID]
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AffiliateCommission(Base):
    """
    Commission d'une commande : au plus une, garanti par l'unicité sur `order_id`. « Disponible »
    n'est pas un statut : c'est `held`, sans réserve, une fois `available_at` passé.
    """

    __tablename__ = "affiliate_commissions"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_affiliate_commissions_order"),
        Index("ix_affiliate_commissions_affiliate", "affiliate_id", "status"),
        CheckConstraint("status IN ('held', 'paid', 'cancelled')", name="status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    affiliate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("affiliates.id"))
    referral_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("referrals.id"))
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payment_orders.id"))
    # Calculée sur le prix de référence de la commande, jamais sur le montant converti.
    base_amount: Mapped[Decimal] = mapped_column(Money)
    rate_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    amount: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(10), default="held")
    # Motif de réserve (`held`) ou d'annulation (`cancelled`).
    reason: Mapped[str | None] = mapped_column(String(30))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payout_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("affiliate_payouts.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SiteSetting(Base):
    """Réglages du site modifiables dans l'administration, sans changer le code."""

    __tablename__ = "site_settings"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_by: Mapped[uuid.UUID | None]
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
