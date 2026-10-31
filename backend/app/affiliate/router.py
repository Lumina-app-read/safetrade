"""Espace de l'affilié : demande, code, filleuls, commissions et versements."""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.affiliate import service
from app.auth.rate_limit import FailureCounter
from app.authz import CurrentSession
from app.config import Settings
from app.db.models import (
    Affiliate,
    AffiliateCommission,
    AffiliatePayout,
    PaymentOrder,
    Referral,
    User,
)
from app.deps import AppSettings, Db, check_origin, client_ip, get_failures
from app.errors import ApiError

router = APIRouter(prefix="/affiliate", tags=["affiliate"], dependencies=[Depends(check_origin)])

MAX_APPLICATIONS = 5
APPLICATION_WINDOW = 24 * 3600
HISTORY = 50


class ApplyIn(BaseModel):
    message: str = Field(min_length=10, max_length=500)
    payout_details: str = Field(min_length=6, max_length=200)
    accept_terms: bool = False


def program_view(db: DbSession) -> dict[str, object]:
    rules = service.program(db)
    return {
        "rate_pct": str(rules.rate_pct),
        "recurring": rules.recurring,
        "attribution_days": rules.attribution_days,
        "hold_days": rules.hold_days,
    }


def masked(name: str) -> str:
    """Le filleul reste privé : l'affilié voit une initiale, jamais son adresse."""
    return f"{name[:1].upper()}***"


def _referrals(db: DbSession, row: Affiliate) -> list[dict[str, object]]:
    converted = set(
        db.scalars(
            select(AffiliateCommission.referral_id).where(
                AffiliateCommission.affiliate_id == row.id,
                AffiliateCommission.status != service.CANCELLED,
            )
        )
    )
    # Un parrainage bloqué n'apparaît pas : ne pas décrire les contrôles anti-fraude.
    found = db.execute(
        select(Referral, User.first_name)
        .join(User, User.id == Referral.referred_user_id)
        .where(Referral.affiliate_id == row.id, Referral.status != service.BLOCKED)
        .order_by(Referral.attributed_at.desc())
        .limit(HISTORY)
    )
    return [
        {
            "id": referral.id,
            "name": masked(first_name),
            "joined_at": referral.attributed_at,
            "converted": referral.id in converted,
        }
        for referral, first_name in found
    ]


def _commissions(db: DbSession, row: Affiliate, now: datetime) -> list[dict[str, object]]:
    found = db.execute(
        select(AffiliateCommission, PaymentOrder.plan_code)
        .join(PaymentOrder, PaymentOrder.id == AffiliateCommission.order_id)
        .where(AffiliateCommission.affiliate_id == row.id)
        .order_by(AffiliateCommission.created_at.desc())
        .limit(HISTORY)
    )
    views = []
    for commission, plan in found:
        state = service.state_of(commission, now)
        views.append(
            {
                "id": commission.id,
                "plan": plan,
                "amount": str(commission.amount),
                "currency": commission.currency,
                # Une réserve se présente au client comme une attente, sans motif.
                "status": service.HELD if state == service.REVIEW else state,
                "available_at": commission.available_at,
                "created_at": commission.created_at,
            }
        )
    return views


def _payouts(db: DbSession, row: Affiliate) -> list[dict[str, object]]:
    found = db.scalars(
        select(AffiliatePayout)
        .where(AffiliatePayout.affiliate_id == row.id)
        .order_by(AffiliatePayout.paid_at.desc())
        .limit(HISTORY)
    )
    return [
        {
            "id": payout.id,
            "amount": str(payout.amount),
            "currency": payout.currency,
            "method": payout.method,
            "paid_at": payout.paid_at,
        }
        for payout in found
    ]


def overview(db: DbSession, settings: Settings, user: User) -> dict[str, Any]:
    now = datetime.now(UTC)
    row = db.scalars(select(Affiliate).where(Affiliate.user_id == user.id)).first()
    view: dict[str, Any] = {
        "status": row.status if row else "none",
        "program": program_view(db),
        "code": None,
        "link": None,
        "totals": service.Totals().view(),
        "referrals": [],
        "commissions": [],
        "payouts": [],
    }
    if row is None or row.code is None:
        return view
    view["code"] = row.code
    if row.status == service.APPROVED:
        # Sans langue : le site choisit celle du filleul, pas celle de l'affilié.
        view["link"] = f"{settings.public_app_url}/register?ref={row.code}"
    view["totals"] = service.totals_of(db, [row.id], now)[row.id].view()
    view["referrals"] = _referrals(db, row)
    view["commissions"] = _commissions(db, row, now)
    view["payouts"] = _payouts(db, row)
    return view


@router.get("/me")
def me(db: Db, settings: AppSettings, session: CurrentSession) -> dict[str, Any]:
    return overview(db, settings, session.user)


@router.post("/apply", status_code=201)
def apply(
    body: ApplyIn,
    request: Request,
    db: Db,
    settings: AppSettings,
    session: CurrentSession,
    failures: Annotated[FailureCounter, Depends(get_failures)],
) -> dict[str, Any]:
    user = session.user
    key = f"affiliate:apply:{user.id}"
    if failures.count(key) >= MAX_APPLICATIONS:
        raise ApiError(429, "auth.too_many_attempts", {"Retry-After": str(APPLICATION_WINDOW)})
    failures.add(key, APPLICATION_WINDOW)
    service.apply(
        db,
        settings,
        user,
        message=body.message.strip(),
        payout_details=body.payout_details.strip(),
        accept_terms=body.accept_terms,
        ip=client_ip(request),
    )
    db.commit()
    return overview(db, settings, user)
