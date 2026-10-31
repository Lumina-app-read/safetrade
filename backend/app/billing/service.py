"""
Abonnements : statut calculé côté serveur, essai, activation atomique d'un paiement.

Une activation ne vient jamais du navigateur du client : uniquement d'une notification signée
ou du rapprochement, tous deux confirmés auprès du fournisseur.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app import audit
from app.db.models import (
    PaymentEvent,
    PaymentOrder,
    Plan,
    Subscription,
    User,
    UserStatus,
)
from app.errors import ApiError

TRIAL = "trial"
PENDING = "pending"
PAID = "paid"
PARTIAL = "partial"
FAILED = "failed"
EXPIRED = "expired"


@dataclass(frozen=True)
class Access:
    """`status` : trial, active, expired, suspended ou none. Le bot : trial et active."""

    status: str
    plan: str
    ends_at: datetime | None

    @property
    def allowed(self) -> bool:
        return self.status in ("trial", "active")


def latest(db: DbSession, user_id: uuid.UUID) -> Subscription | None:
    return db.scalars(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.ends_at.desc())
    ).first()


def access_of(db: DbSession, user: User, now: datetime | None = None) -> Access:
    moment = now or datetime.now(UTC)
    row = latest(db, user.id)
    plan = row.plan_code if row else "none"
    ends = row.ends_at if row else None
    if user.status == UserStatus.SUSPENDED:
        return Access("suspended", plan, ends)
    if row is None:
        return Access("none", "none", None)
    if row.ends_at <= moment:
        return Access("expired", plan, ends)
    return Access("trial" if row.plan_code == TRIAL else "active", plan, ends)


def has_access(db: DbSession, user_id: uuid.UUID, now: datetime | None = None) -> bool:
    user = db.get(User, user_id)
    return user is not None and access_of(db, user, now).allowed


def require_access(db: DbSession, user: User) -> None:
    if not access_of(db, user).allowed:
        raise ApiError(402, "billing.access_required")


def grant_trial(db: DbSession, user: User, now: datetime | None = None) -> None:
    """Un seul essai par compte, garanti par un index unique. La durée vient de la table."""
    existing = db.scalars(
        select(Subscription.id).where(
            Subscription.user_id == user.id, Subscription.plan_code == TRIAL
        )
    ).first()
    if existing is not None:
        return
    moment = now or datetime.now(UTC)
    plan = db.get_one(Plan, TRIAL)
    db.add(
        Subscription(
            user_id=user.id,
            plan_code=TRIAL,
            starts_at=moment,
            ends_at=moment + timedelta(days=plan.duration_days),
        )
    )


def create_order(db: DbSession, user: User, plan: Plan, provider: str) -> PaymentOrder:
    order = PaymentOrder(
        user_id=user.id,
        plan_code=plan.code,
        provider=provider,
        # Prix figé à la commande : un changement de tarif ne touche pas un paiement en cours.
        amount=plan.price,
        currency=plan.currency,
    )
    db.add(order)
    db.flush()
    return order


def settle(
    db: DbSession, order_id: uuid.UUID, amount: Decimal, currency: str, now: datetime | None = None
) -> Subscription | None:
    """
    Active ou prolonge l'accès, d'un seul geste. Commande verrouillée, et une seule ligne
    d'abonnement par commande : un paiement ne prolonge jamais deux fois.
    """
    moment = now or datetime.now(UTC)
    order = db.scalars(
        select(PaymentOrder).where(PaymentOrder.id == order_id).with_for_update()
    ).first()
    if order is None or order.status == PAID:
        return None
    order.amount_received = amount
    if currency != order.currency or amount < order.amount:
        order.status = PARTIAL
        audit.record(
            db,
            "billing.payment",
            "failure",
            actor_user_id=order.user_id,
            target_type="order",
            target_id=str(order.id),
            details={"reason": "amount_mismatch", "amount": str(amount), "currency": currency},
        )
        return None
    plan = db.get_one(Plan, order.plan_code)
    current = latest(db, order.user_id)
    start = max(moment, current.ends_at) if current else moment
    subscription = Subscription(
        user_id=order.user_id,
        plan_code=order.plan_code,
        order_id=order.id,
        starts_at=start,
        ends_at=start + timedelta(days=plan.duration_days),
    )
    db.add(subscription)
    order.status = PAID
    order.paid_at = moment
    audit.record(
        db,
        "billing.payment",
        "success",
        actor_user_id=order.user_id,
        target_type="order",
        target_id=str(order.id),
        details={"plan": order.plan_code, "amount": str(amount), "currency": currency},
    )
    db.flush()
    return subscription


def close_order(db: DbSession, order_id: uuid.UUID, status: str) -> None:
    order = db.scalars(
        select(PaymentOrder).where(PaymentOrder.id == order_id).with_for_update()
    ).first()
    if order is not None and order.status == PENDING:
        order.status = status


def seen(db: DbSession, provider: str, delivery_id: str) -> bool:
    return (
        db.scalars(
            select(PaymentEvent.id).where(
                PaymentEvent.provider == provider, PaymentEvent.delivery_id == delivery_id
            )
        ).first()
        is not None
    )


def order_view(order: PaymentOrder) -> dict[str, Any]:
    return {
        "id": order.id,
        "plan": order.plan_code,
        "provider": order.provider,
        "amount": str(order.amount),
        "currency": order.currency,
        "status": order.status,
        "created_at": order.created_at,
        "paid_at": order.paid_at,
    }
