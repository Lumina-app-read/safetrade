"""Abonnement du client, commandes et notifications des fournisseurs de paiement."""

import json
import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.affiliate.service import fingerprint
from app.auth.mailer import Mailer
from app.auth.rate_limit import FailureCounter
from app.authz import CurrentSession
from app.billing import notices, service
from app.billing.gateway import (
    GatewayUnavailableError,
    Payer,
    PaymentGateway,
    PaymentState,
    Quote,
    valid_signature,
)
from app.config import Settings
from app.db.models import PaymentEvent, PaymentOrder, Plan
from app.deps import AppSettings, Db, check_origin, client_ip, get_failures, get_mailer
from app.errors import ApiError

logger = logging.getLogger("safetrade.billing")

router = APIRouter(prefix="/billing", tags=["billing"], dependencies=[Depends(check_origin)])
# Appels de serveur à serveur : authentifiés par signature, sans en-tête Origin.
webhooks = APIRouter(prefix="/billing", tags=["billing"])

MAX_CHECKOUTS = 10
CHECKOUT_WINDOW = 3600
PROVIDER = "chariow"


class CheckoutIn(BaseModel):
    plan: Literal["weekly", "monthly", "annual"]
    provider: Literal["chariow"] = "chariow"
    last_name: str = Field(min_length=1, max_length=50)
    phone_number: str = Field(pattern=r"^\d{6,15}$")
    phone_country: str = Field(pattern=r"^[A-Z]{2}$")


def gateways(request: Request) -> dict[str, PaymentGateway]:
    found: dict[str, PaymentGateway] = request.app.state.gateways
    return found


Gateways = Annotated[dict[str, PaymentGateway], Depends(gateways)]


def overview(db: DbSession, session: Any, available: dict[str, PaymentGateway]) -> dict[str, Any]:
    user = session.user
    access = service.access_of(db, user)
    plans = db.scalars(
        select(Plan).where(Plan.active, Plan.code != service.TRIAL).order_by(Plan.duration_days)
    )
    orders = db.scalars(
        select(PaymentOrder)
        .where(PaymentOrder.user_id == user.id)
        .order_by(PaymentOrder.created_at.desc())
        .limit(20)
    )
    return {
        "access": {
            "status": access.status,
            "plan": access.plan,
            "ends_at": access.ends_at,
            "allowed": access.allowed,
        },
        "plans": [
            {
                "code": p.code,
                "duration_days": p.duration_days,
                "price": str(p.price),
                "currency": p.currency,
                "providers": [g.name for g in available.values() if g.supports(p.code)],
            }
            for p in plans
        ],
        "orders": [service.order_view(o) for o in orders],
    }


@router.get("/me")
def me(db: Db, session: CurrentSession, available: Gateways) -> dict[str, Any]:
    return overview(db, session, available)


def return_url(settings: Settings, locale: str, order_id: object) -> str | None:
    """Chariow exige une adresse active : pas d'adresse locale en développement."""
    if "127.0.0.1" in settings.public_app_url or "localhost" in settings.public_app_url:
        return None
    return f"{settings.public_app_url}/{locale}/subscription?order={order_id}"


@router.post("/checkout", status_code=201)
async def checkout(
    body: CheckoutIn,
    request: Request,
    db: Db,
    settings: AppSettings,
    session: CurrentSession,
    available: Gateways,
    failures: Annotated[FailureCounter, Depends(get_failures)],
) -> dict[str, object]:
    user = session.user
    gateway = available.get(body.provider)
    if gateway is None or not gateway.supports(body.plan):
        raise ApiError(503, "billing.provider_unavailable")
    key = f"billing:checkout:{user.id}"
    if failures.count(key) >= MAX_CHECKOUTS:
        raise ApiError(429, "auth.too_many_attempts", {"Retry-After": str(CHECKOUT_WINDOW)})
    failures.add(key, CHECKOUT_WINDOW)

    def prepare() -> tuple[Any, str, Quote]:
        plan = db.get(Plan, body.plan)
        if plan is None or not plan.active:
            raise ApiError(404, "billing.unknown_plan")
        payer = fingerprint(settings, body.phone_number)
        order = service.create_order(db, user, plan, gateway.name, payer)
        db.commit()
        return order.id, user.email, Quote(plan.price, plan.currency)

    order_id, email, reference = await run_in_threadpool(prepare)
    payer = Payer(
        email=email,
        first_name=user.first_name,
        last_name=body.last_name.strip(),
        phone_number=body.phone_number,
        phone_country=body.phone_country,
        ip=client_ip(request),
    )
    try:
        result = await gateway.create_checkout(
            body.plan,
            payer,
            str(order_id),
            return_url(settings, user.locale, order_id),
            reference,
        )
    except GatewayUnavailableError:
        await run_in_threadpool(_close, db, order_id)
        raise ApiError(503, "billing.provider_unavailable") from None
    except ApiError:
        await run_in_threadpool(_close, db, order_id)
        raise

    def remember() -> None:
        row = db.get_one(PaymentOrder, order_id)
        row.provider_ref = result.reference
        row.checkout_url = result.url
        row.product_ref = result.product
        row.expected_amount = result.amount
        row.expected_currency = result.currency
        db.commit()

    await run_in_threadpool(remember)
    return {"order": str(order_id), "checkout_url": result.url}


def _close(db: DbSession, order_id: Any) -> None:
    service.close_order(db, order_id, service.FAILED)
    db.commit()


def _record(
    db: DbSession, delivery: str, event: str, order_id: Any, reference: str, payload: dict[str, Any]
) -> None:
    amount = payload.get("sale", {}).get("amount") or {}
    db.add(
        PaymentEvent(
            provider=PROVIDER,
            delivery_id=delivery,
            event=event,
            order_id=order_id,
            reference=reference,
            amount=Decimal(str(amount["value"])) if amount.get("value") is not None else None,
            currency=amount.get("currency"),
        )
    )


def order_of(sale: dict[str, Any]) -> uuid.UUID | None:
    """Identifiant de commande transmis à la création de la vente, jamais pris pour acquis."""
    raw = (sale.get("custom_metadata") or {}).get("order_id")
    try:
        return uuid.UUID(str(raw)) if raw else None
    except ValueError:
        return None


@webhooks.post("/webhooks/chariow")
async def chariow_pulse(
    request: Request,
    db: Db,
    settings: AppSettings,
    available: Gateways,
    mailer: Annotated[Mailer, Depends(get_mailer)],
) -> dict[str, str]:
    """Signature vérifiée sur le corps brut, puis paiement confirmé auprès de Chariow."""
    if settings.chariow_webhook_secret is None:
        raise ApiError(503, "billing.provider_unavailable")
    raw = await request.body()
    signature = request.headers.get("x-chariow-signature")
    secret = settings.chariow_webhook_secret.get_secret_value()
    if not valid_signature(raw, signature, secret):
        raise ApiError(401, "billing.bad_signature")
    delivery = request.headers.get("x-pulse-delivery-id", "")
    event = request.headers.get("x-pulse-event", "")
    payload = json.loads(raw)
    sale = payload.get("sale") or {}
    reference = str(sale.get("id", ""))
    # Essai envoyé depuis le tableau de bord Chariow : signature valide, aucune vente réelle.
    if not delivery or reference.startswith("test_"):
        return {"status": "ignored"}
    if await run_in_threadpool(service.seen, db, PROVIDER, delivery):
        return {"status": "duplicate"}
    order_id = order_of(sale)
    state = None
    gateway = available.get(PROVIDER)
    if event == "successful.sale" and order_id:
        if gateway is None:
            raise ApiError(503, "billing.provider_unavailable")
        try:
            state = await gateway.fetch_payment(reference)
        except GatewayUnavailableError:
            # Réponse d'erreur : Chariow renverra la notification, rien n'est enregistré.
            raise ApiError(503, "billing.provider_unavailable") from None

    def apply() -> None:
        _record(db, delivery, event, order_id, reference, payload)
        if order_id and event == "failed.sale":
            service.close_order(db, order_id, service.FAILED)
        if order_id and event == "abandoned.sale":
            service.close_order(db, order_id, service.EXPIRED)
        granted = None
        if state is not None and state.status == "paid" and order_id:
            granted = service.settle(db, order_id, state)
        db.commit()
        if granted is not None:
            notices.receipt(db, mailer, settings, granted)

    await run_in_threadpool(apply)
    return {"status": "processed"}


def _apply_state(
    factory: Any,
    order: PaymentOrder,
    state: PaymentState,
    mailer: Mailer,
    settings: Settings,
    now: datetime,
) -> None:
    age = (now - order.created_at).total_seconds()
    with factory() as db:
        granted = None
        if state.status == "paid":
            granted = service.settle(db, order.id, state, now)
        elif state.status == "failed":
            service.close_order(db, order.id, service.FAILED)
        elif state.status == "expired" or age > notices.ORDER_LIFETIME_SECONDS:
            service.close_order(db, order.id, service.EXPIRED)
        db.commit()
        if granted is not None:
            notices.receipt(db, mailer, settings, granted)


async def reconcile(
    factory: Any, gateway: PaymentGateway, mailer: Mailer, settings: Settings, now: datetime
) -> None:
    """Commandes restées en attente : une notification perdue ne fait pas perdre un paiement."""

    def pending() -> list[PaymentOrder]:
        with factory() as db:
            return list(
                db.scalars(
                    select(PaymentOrder).where(
                        # Chariow peut rouvrir une vente échouée ou abandonnée, puis la terminer.
                        PaymentOrder.status.in_(service.OPEN_STATUSES),
                        PaymentOrder.created_at >= now - timedelta(seconds=notices.RECHECK_SECONDS),
                        PaymentOrder.provider == gateway.name,
                        PaymentOrder.provider_ref.is_not(None),
                    )
                )
            )

    for order in await run_in_threadpool(pending):
        if (now - order.created_at).total_seconds() < notices.RECONCILE_AFTER_SECONDS:
            continue
        try:
            state = await gateway.fetch_payment(order.provider_ref or "")
        except GatewayUnavailableError:
            logger.warning("rapprochement reporté", extra={"event": "billing.reconcile_failed"})
            return
        await run_in_threadpool(_apply_state, factory, order, state, mailer, settings, now)
