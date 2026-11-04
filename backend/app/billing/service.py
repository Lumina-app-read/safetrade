"""
Abonnements : statut calculé côté serveur, essai, activation atomique d'un paiement.

Une activation ne vient jamais du navigateur du client : uniquement d'une notification signée
ou du rapprochement, tous deux confirmés auprès du fournisseur.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app import audit
from app.affiliate.service import credit
from app.billing.gateway import PaymentState
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
OPEN_STATUSES = (PENDING, FAILED, EXPIRED)


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
        .where(Subscription.user_id == user_id, Subscription.revoked_at.is_(None))
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


MAX_GRANT_DAYS = 366


def grant(
    db: DbSession,
    admin: User,
    user: User,
    *,
    plan_code: str,
    days: int | None,
    note: str,
    ip: str | None,
    now: datetime | None = None,
) -> Subscription:
    """
    Accès accordé à la main, par exemple en attendant un paiement. Jamais de commission
    d'affiliation : aucune somme n'a été encaissée. Réservé au super administrateur, qui peut
    s'en accorder un (décision du propriétaire) ; le journal d'audit le montre.
    """
    plan = db.get(Plan, plan_code)
    if plan is None or plan.code == TRIAL or not plan.active:
        raise ApiError(422, "admin.invalid_plan")
    length = plan.duration_days if days is None else days
    if not 1 <= length <= MAX_GRANT_DAYS:
        raise ApiError(422, "admin.invalid_days")
    moment = now or datetime.now(UTC)
    current = latest(db, user.id)
    start = max(moment, current.ends_at) if current else moment
    row = Subscription(
        user_id=user.id,
        plan_code=plan.code,
        starts_at=start,
        ends_at=start + timedelta(days=length),
        granted_by=admin.id,
        grant_note=note,
    )
    db.add(row)
    db.flush()
    audit.record(
        db,
        "admin.subscription.grant",
        "success",
        actor_user_id=admin.id,
        target_type="user",
        target_id=str(user.id),
        ip_address=ip,
        details={"subscription": str(row.id), "plan": plan.code, "days": length, "note": note},
    )
    return row


def revoke(
    db: DbSession,
    admin: User,
    user: User,
    subscription_id: uuid.UUID,
    *,
    note: str,
    ip: str | None,
    now: datetime | None = None,
) -> None:
    """Retire un accès accordé à la main. Un accès payé ne se retire pas ici : il se rembourse."""
    row = db.scalars(
        select(Subscription)
        .where(Subscription.id == subscription_id, Subscription.user_id == user.id)
        .with_for_update()
    ).first()
    if row is None:
        raise ApiError(404, "admin.subscription_not_found")
    if row.granted_by is None:
        raise ApiError(409, "admin.subscription_not_manual")
    if row.revoked_at is not None:
        raise ApiError(409, "admin.subscription_revoked")
    current = latest(db, user.id)
    if current is not None and current.id != row.id:
        # Une période plus tardive s'enchaîne sur celle-ci : retirer d'abord la dernière.
        raise ApiError(409, "admin.subscription_followed")
    row.revoked_at = now or datetime.now(UTC)
    row.revoked_by = admin.id
    audit.record(
        db,
        "admin.subscription.revoke",
        "success",
        actor_user_id=admin.id,
        target_type="user",
        target_id=str(user.id),
        ip_address=ip,
        details={"subscription": str(row.id), "note": note},
    )


def history_view(db: DbSession, user: User) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(Subscription)
        .where(Subscription.user_id == user.id)
        .order_by(Subscription.starts_at.desc())
        .limit(50)
    )
    emails = {}
    result = []
    for row in rows:
        source = "trial" if row.plan_code == TRIAL else "manual" if row.granted_by else "payment"
        by = row.granted_by
        if by is not None and by not in emails:
            emails[by] = db.get_one(User, by).email
        result.append(
            {
                "id": row.id,
                "plan": row.plan_code,
                "source": source,
                "starts_at": row.starts_at,
                "ends_at": row.ends_at,
                "granted_by": emails.get(by) if by else None,
                "note": row.grant_note,
                "revoked_at": row.revoked_at,
            }
        )
    return result


def create_order(
    db: DbSession, user: User, plan: Plan, provider: str, payer_hash: bytes | None = None
) -> PaymentOrder:
    order = PaymentOrder(
        user_id=user.id,
        plan_code=plan.code,
        provider=provider,
        # Prix figé à la commande : un changement de tarif ne touche pas un paiement en cours.
        amount=plan.price,
        currency=plan.currency,
        payer_hash=payer_hash,
    )
    db.add(order)
    db.flush()
    return order


def mismatch(order: PaymentOrder, state: PaymentState) -> str | None:
    """
    Motif de refus, ou None. La comparaison se fait en devise du produit : le client peut payer
    en devise locale, mais `amount` reste celui du produit. Le montant converti n'est jamais
    comparé au prix : le taux appartient à Chariow.
    """
    expected = order.expected_amount if order.expected_amount is not None else order.amount
    currency = order.expected_currency or order.currency
    if state.reference != order.provider_ref:
        return "wrong_sale"
    if order.product_ref and state.product != order.product_ref:
        return "wrong_product"
    if state.currency != currency:
        return "wrong_currency"
    if state.amount < expected:
        return "amount_too_low"
    return None


def settle(
    db: DbSession, order_id: uuid.UUID, state: PaymentState, now: datetime | None = None
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
    order.amount_received = state.amount
    order.paid_amount = state.payment_amount
    order.paid_currency = state.payment_currency
    reason = mismatch(order, state)
    if reason:
        order.status = PARTIAL
        audit.record(
            db,
            "billing.payment",
            "failure",
            actor_user_id=order.user_id,
            target_type="order",
            target_id=str(order.id),
            details={"reason": reason, "amount": str(state.amount), "currency": state.currency},
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
        details={
            "plan": order.plan_code,
            "amount": str(state.amount),
            "currency": state.currency,
            "paid_amount": str(state.payment_amount),
            "paid_currency": state.payment_currency,
        },
    )
    db.flush()
    # Même transaction que l'activation : un paiement validé, jamais deux commissions.
    credit(db, order, moment)
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
