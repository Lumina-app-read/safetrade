"""Reçu de paiement et rappel avant l'échéance, envoyés par e-mail dans la langue du client."""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.auth.mailer import Mailer, render
from app.billing import service
from app.config import Settings
from app.db.models import PaymentOrder, Subscription, User

RECONCILE_AFTER_SECONDS = 300
ORDER_LIFETIME_SECONDS = 24 * 3600
REMINDER_BEFORE = timedelta(hours=24)


def _ends(row: Subscription) -> str:
    return row.ends_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _link(settings: Settings, user: User) -> str:
    return f"{settings.public_app_url}/{user.locale}/subscription"


def receipt(db: DbSession, mailer: Mailer, settings: Settings, row: Subscription) -> None:
    user = db.get_one(User, row.user_id)
    order = db.get_one(PaymentOrder, row.order_id)
    mailer.send(
        render(
            "payment_received",
            user.locale,
            user.email,
            first_name=user.first_name,
            link=_link(settings, user),
            amount=f"{order.amount} {order.currency}",
            ends=_ends(row),
        )
    )


def remind_expiring(factory: Any, mailer: Mailer, settings: Settings, now: datetime) -> None:
    """Un seul rappel par abonnement, et aucun si une prolongation est déjà payée."""
    with factory() as db:
        rows = db.scalars(
            select(Subscription).where(
                Subscription.reminded_at.is_(None),
                Subscription.ends_at > now,
                Subscription.ends_at <= now + REMINDER_BEFORE,
            )
        )
        for row in list(rows):
            row.reminded_at = now
            current = service.latest(db, row.user_id)
            if current is None or current.id != row.id:
                continue
            user = db.get_one(User, row.user_id)
            mailer.send(
                render(
                    "subscription_expiring",
                    user.locale,
                    user.email,
                    first_name=user.first_name,
                    link=_link(settings, user),
                    ends=_ends(row),
                )
            )
        db.commit()
