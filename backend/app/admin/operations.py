"""
Tableau de bord, formules, paiements, trading et risque (section 10).

Une formule modifiée ne touche ni les abonnements déjà payés ni les commandes en cours : le
prix est figé à la commande. Chaque modification est inscrite au journal d'audit, avant et
après, ce qui en garde l'historique.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from app import audit
from app.authz import Permission, permissions_of, require_permission
from app.billing import service as billing
from app.billing.gateway import GatewayUnavailableError
from app.billing.router import _apply_state
from app.billing.router import gateways as billing_gateways
from app.db.models import (
    AuditLog,
    BotSession,
    PaymentOrder,
    Plan,
    Session,
    Subscription,
    TradingPosition,
    User,
    UserRole,
)
from app.deps import AppSettings, Db, client_ip, get_mailer
from app.errors import ApiError
from app.trading import controls

router = APIRouter()

MAX_PRICE = Decimal(10000)


def _now() -> datetime:
    return datetime.now(UTC)


# Tableau de bord.


@router.get("/stats")
def stats(
    db: Db, admin: Annotated[User, Depends(require_permission(Permission.USERS_READ))]
) -> dict[str, object]:
    now = _now()
    week = now - timedelta(days=7)
    live = (
        Subscription.revoked_at.is_(None),
        Subscription.starts_at <= now,
        Subscription.ends_at > now,
    )

    def count(stmt: object) -> int:
        return int(db.scalar(stmt) or 0)  # type: ignore[call-overload]

    clients = select(func.count()).select_from(User).where(User.role == UserRole.CLIENT)
    figures: dict[str, object] = {
        "users": count(clients),
        "new_users_7d": count(clients.where(User.created_at >= week)),
        "active_users_7d": count(
            select(func.count(func.distinct(Session.user_id)))
            .join(User, User.id == Session.user_id)
            .where(User.role == UserRole.CLIENT, Session.last_seen_at >= week)
        ),
        "trials": count(
            select(func.count(func.distinct(Subscription.user_id))).where(
                Subscription.plan_code == billing.TRIAL, *live
            )
        ),
        "subscribers": count(
            select(func.count(func.distinct(Subscription.user_id))).where(
                Subscription.plan_code != billing.TRIAL, *live
            )
        ),
        "bots": count(
            select(func.count()).select_from(BotSession).where(BotSession.ended_at.is_(None))
        ),
        "bot_errors_24h": count(
            select(func.count())
            .select_from(BotSession)
            .where(
                BotSession.error_code.is_not(None), BotSession.updated_at >= now - timedelta(days=1)
            )
        ),
        "open_positions": count(
            select(func.count())
            .select_from(TradingPosition)
            .where(TradingPosition.closed_at.is_(None), TradingPosition.status != "void")
        ),
        "halted": controls.read(db).halted,
    }
    if Permission.PAYMENTS_READ in permissions_of(admin):
        rows = db.execute(
            select(PaymentOrder.currency, func.sum(PaymentOrder.amount), func.count())
            .where(
                PaymentOrder.status == billing.PAID,
                PaymentOrder.paid_at >= now - timedelta(days=30),
            )
            .group_by(PaymentOrder.currency)
        ).all()
        figures["revenue_30d"] = [{"currency": c, "amount": str(a), "count": n} for c, a, n in rows]
    return figures


# Formules.


class PlanIn(BaseModel):
    price: Decimal | None = Field(default=None, ge=0, le=MAX_PRICE, decimal_places=2)
    duration_days: int | None = Field(default=None, ge=1, le=366)
    active: bool | None = None
    note: str = Field(min_length=5, max_length=300)


def plan_view(plan: Plan) -> dict[str, object]:
    return {
        "code": plan.code,
        "price": str(plan.price),
        "currency": plan.currency,
        "duration_days": plan.duration_days,
        "active": plan.active,
    }


@router.get("/plans")
def plans(
    db: Db, _: Annotated[User, Depends(require_permission(Permission.SETTINGS_WRITE))]
) -> dict[str, object]:
    changes = db.scalars(
        select(AuditLog)
        .where(AuditLog.action == "admin.plan.update")
        .order_by(AuditLog.id.desc())
        .limit(30)
    )
    return {
        "plans": [plan_view(p) for p in db.scalars(select(Plan).order_by(Plan.duration_days))],
        "changes": [
            {"at": c.occurred_at, "plan": c.target_id, "details": c.details} for c in changes
        ],
    }


@router.put("/plans/{code}")
def update_plan(
    code: str,
    body: PlanIn,
    request: Request,
    db: Db,
    admin: Annotated[User, Depends(require_permission(Permission.SETTINGS_WRITE))],
) -> dict[str, object]:
    plan = db.get(Plan, code)
    if plan is None:
        raise ApiError(404, "admin.plan_not_found")
    if code == billing.TRIAL and body.price not in (None, Decimal(0)):
        raise ApiError(422, "admin.trial_is_free")
    if code == billing.TRIAL and body.active is False:
        raise ApiError(422, "admin.trial_required")
    before = plan_view(plan)
    if body.price is not None:
        plan.price = body.price
    if body.duration_days is not None:
        plan.duration_days = body.duration_days
    if body.active is not None:
        plan.active = body.active
    after = plan_view(plan)
    if after == before:
        raise ApiError(409, "admin.nothing_changed")
    audit.record(
        db, "admin.plan.update", "success", actor_user_id=admin.id, target_type="plan",
        target_id=code, ip_address=client_ip(request),
        details={"before": before, "after": after, "note": body.note.strip()},
    )  # fmt: skip
    db.commit()
    return plan_view(plan)


# Paiements.


@router.get("/payments")
def payments(
    db: Db,
    _: Annotated[User, Depends(require_permission(Permission.PAYMENTS_READ))],
    status: Annotated[str | None, Query(max_length=12)] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict[str, object]:
    stmt = (
        select(PaymentOrder, User.email)
        .join(User, User.id == PaymentOrder.user_id)
        .order_by(PaymentOrder.created_at.desc())
        .limit(limit)
    )
    if status:
        stmt = stmt.where(PaymentOrder.status == status)
    if q:
        term = q.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(
            or_(
                func.lower(User.email).like(f"%{term}%", escape="\\"),
                PaymentOrder.provider_ref == q.strip(),
            )
        )
    return {
        "orders": [
            {
                **billing.order_view(order),
                "email": email,
                "user_id": order.user_id,
                "reference": order.provider_ref,
                "amount_received": None
                if order.amount_received is None
                else str(order.amount_received),
                "paid_amount": None if order.paid_amount is None else str(order.paid_amount),
                "paid_currency": order.paid_currency,
            }
            for order, email in db.execute(stmt).all()
        ]
    }


@router.post("/payments/{order_id}/check")
async def check_payment(
    order_id: uuid.UUID,
    request: Request,
    db: Db,
    settings: AppSettings,
    admin: Annotated[User, Depends(require_permission(Permission.PAYMENTS_READ))],
) -> dict[str, object]:
    """Rapprochement à la demande : l'état est relu chez le fournisseur, jamais saisi ici."""
    order = db.get(PaymentOrder, order_id)
    if order is None:
        raise ApiError(404, "admin.order_not_found")
    found = await run_in_threadpool(billing_gateways, request, db, settings)
    gateway = found.get(order.provider)
    if gateway is None or not order.provider_ref:
        raise ApiError(409, "admin.order_not_checkable")
    try:
        state = await gateway.fetch_payment(order.provider_ref)
    except GatewayUnavailableError as error:
        raise ApiError(503, "billing.provider_unavailable") from error
    factory = request.app.state.session_factory
    mailer = get_mailer(request)
    await run_in_threadpool(_apply_state, factory, order, state, mailer, settings, _now())

    def record() -> None:
        audit.record(
            db, "admin.payment.check", "success", actor_user_id=admin.id, target_type="order",
            target_id=str(order_id), ip_address=client_ip(request),
            details={"provider_status": state.status},
        )  # fmt: skip
        db.commit()
        db.refresh(order)

    await run_in_threadpool(record)
    return {"order": billing.order_view(order), "provider_status": state.status}


# Trading et risque.


class ControlsIn(BaseModel):
    max_stake: Decimal | None = Field(default=None, ge=1, le=50, decimal_places=2)
    max_positions: int | None = Field(default=None, ge=1, le=3)
    disabled_symbols: list[str] = Field(default_factory=list, max_length=200)
    note: str = Field(min_length=5, max_length=300)


class HaltIn(BaseModel):
    halted: bool
    # Arrêt d'urgence : demande aussi la fermeture de toutes les positions ouvertes.
    close_positions: bool = False
    note: str = Field(min_length=5, max_length=300)


def _bots(db: Db) -> list[dict[str, object]]:
    rows = db.execute(
        select(BotSession, User.email)
        .join(User, User.id == BotSession.user_id)
        .where(BotSession.ended_at.is_(None))
        .order_by(BotSession.started_at.desc())
    ).all()
    result = []
    for bot, email in rows:
        open_positions = db.scalar(
            select(func.count())
            .select_from(TradingPosition)
            .where(TradingPosition.session_id == bot.id, TradingPosition.closed_at.is_(None))
        )
        result.append(
            {
                "id": bot.id,
                "email": email,
                "user_id": bot.user_id,
                "symbol": bot.symbol,
                "account_kind": bot.account_kind,
                "state": bot.state,
                "command": bot.command,
                "error_code": bot.error_code,
                "heartbeat_at": bot.heartbeat_at,
                "started_at": bot.started_at,
                "open_positions": open_positions or 0,
            }
        )
    return result


@router.get("/trading")
def trading(
    db: Db, _: Annotated[User, Depends(require_permission(Permission.RISK_WRITE))]
) -> dict[str, object]:
    return {"controls": controls.read(db).view(), "bots": _bots(db)}


@router.put("/trading/controls")
def set_controls(
    body: ControlsIn,
    request: Request,
    db: Db,
    admin: Annotated[User, Depends(require_permission(Permission.RISK_WRITE))],
) -> dict[str, object]:
    current = controls.read(db)
    symbols = tuple(sorted({s.strip() for s in body.disabled_symbols if s.strip()}))
    if any(len(s) > 30 for s in symbols):
        raise ApiError(422, "admin.invalid_symbol")
    updated = controls.Controls(current.halted, body.max_stake, body.max_positions, symbols)
    controls.write(db, updated, admin.id)
    audit.record(
        db, "admin.trading.controls", "success", actor_user_id=admin.id,
        ip_address=client_ip(request),
        details={"before": current.view(), "after": updated.view(), "note": body.note.strip()},
    )  # fmt: skip
    db.commit()
    return {"controls": updated.view(), "bots": _bots(db)}


@router.put("/trading/halt")
def set_halt(
    body: HaltIn,
    request: Request,
    db: Db,
    admin: Annotated[User, Depends(require_permission(Permission.RISK_WRITE))],
) -> dict[str, object]:
    """Arrêt d'urgence global, ou reprise. Le moteur arrête chaque bot à son prochain tour."""
    current = controls.read(db)
    updated = controls.Controls(
        body.halted, current.max_stake, current.max_positions, current.disabled_symbols
    )
    controls.write(db, updated, admin.id)
    sessions = 0
    if body.halted and body.close_positions:
        for bot in db.scalars(select(BotSession).where(BotSession.ended_at.is_(None))):
            bot.command = "emergency"
            sessions += 1
    audit.record(
        db, "admin.trading.halt", "success", actor_user_id=admin.id, ip_address=client_ip(request),
        details={"halted": body.halted, "close_positions": body.close_positions,
                 "sessions": sessions, "note": body.note.strip()},
    )  # fmt: skip
    db.commit()
    return {"controls": updated.view(), "bots": _bots(db)}


@router.post("/trading/bots/{session_id}/stop")
def stop_bot(
    session_id: uuid.UUID,
    request: Request,
    db: Db,
    admin: Annotated[User, Depends(require_permission(Permission.RISK_WRITE))],
) -> dict[str, object]:
    bot = db.get(BotSession, session_id)
    if bot is None or bot.ended_at is not None:
        raise ApiError(404, "admin.bot_not_found")
    if bot.command != "emergency":
        bot.command = "stop"
    audit.record(
        db, "admin.trading.bot_stop", "success", actor_user_id=admin.id,
        target_type="bot_session", target_id=str(bot.id), ip_address=client_ip(request),
    )  # fmt: skip
    db.commit()
    return {"bots": _bots(db)}
