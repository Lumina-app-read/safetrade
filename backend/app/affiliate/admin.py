"""
Administration de l'affiliation. Protégée au niveau du routeur, comme `/admin` : chaque route
exige en plus sa permission. Support n'y a pas accès (paiements et coordonnées de versement).
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app import audit
from app.affiliate import service
from app.affiliate.router import program_view
from app.auth.mailer import Mailer, render
from app.authz import Permission, require_admin, require_permission
from app.config import Settings
from app.db.models import (
    Affiliate,
    AffiliateCommission,
    AffiliatePayout,
    PaymentOrder,
    Referral,
    User,
)
from app.deps import AppSettings, Db, check_origin, client_ip, get_mailer
from app.errors import ApiError

router = APIRouter(
    prefix="/admin/affiliates",
    tags=["admin"],
    dependencies=[Depends(check_origin), Depends(require_admin)],
)

Reader = Annotated[User, Depends(require_permission(Permission.AFFILIATES_READ))]
Writer = Annotated[User, Depends(require_permission(Permission.AFFILIATES_WRITE))]
Payer = Annotated[User, Depends(require_permission(Permission.PAYOUTS_WRITE))]
Owner = Annotated[User, Depends(require_permission(Permission.SETTINGS_WRITE))]
AppMailer = Annotated[Mailer, Depends(get_mailer)]


class ReviewIn(BaseModel):
    note: str | None = Field(default=None, max_length=300)


class PayoutIn(BaseModel):
    method: Literal["mobile_money", "crypto", "bank", "other"]
    reference: str = Field(min_length=3, max_length=120)


class ProgramIn(BaseModel):
    rate_pct: Decimal = Field(gt=0, le=100, max_digits=5, decimal_places=2)
    recurring: bool
    attribution_days: int = Field(ge=1, le=365)
    hold_days: int = Field(ge=0, le=365)


def _row(affiliate: Affiliate, user: User, totals: service.Totals) -> dict[str, object]:
    return {
        "id": affiliate.id,
        "email": user.email,
        "first_name": user.first_name,
        "status": affiliate.status,
        "code": affiliate.code,
        "message": affiliate.message,
        "payout_details": affiliate.payout_details,
        "review_note": affiliate.review_note,
        "reviewed_at": affiliate.reviewed_at,
        "created_at": affiliate.created_at,
        "totals": totals.view(),
    }


@router.get("/program")
def read_program(db: Db, _: Reader) -> dict[str, object]:
    return program_view(db)


@router.put("/program")
def update_program(body: ProgramIn, request: Request, db: Db, user: Owner) -> dict[str, object]:
    """Vaut pour les paiements à venir : chaque commission garde le taux de sa création."""
    rules = service.program(db)
    rules.rate_pct = body.rate_pct
    rules.recurring = body.recurring
    rules.attribution_days = body.attribution_days
    rules.hold_days = body.hold_days
    audit.record(
        db,
        "affiliate.program",
        "success",
        actor_user_id=user.id,
        ip_address=client_ip(request),
        details=body.model_dump(mode="json"),
    )
    db.commit()
    return program_view(db)


@router.get("")
def list_affiliates(
    db: Db,
    _: Reader,
    status: Annotated[
        Literal["pending", "approved", "refused", "suspended"] | None, Query()
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> dict[str, object]:
    stmt = (
        select(Affiliate, User)
        .join(User, User.id == Affiliate.user_id)
        .order_by(Affiliate.created_at.desc())
        .limit(limit)
    )
    if status:
        stmt = stmt.where(Affiliate.status == status)
    rows = db.execute(stmt).all()
    totals = service.totals_of(db, [affiliate.id for affiliate, _user in rows])
    return {"affiliates": [_row(affiliate, user, totals[affiliate.id]) for affiliate, user in rows]}


def _detail(db: Db, affiliate_id: uuid.UUID) -> dict[str, Any]:
    found = db.execute(
        select(Affiliate, User)
        .join(User, User.id == Affiliate.user_id)
        .where(Affiliate.id == affiliate_id)
    ).first()
    if found is None:
        raise ApiError(404, "affiliate.not_found")
    affiliate, user = found
    now = datetime.now(UTC)
    view: dict[str, Any] = _row(
        affiliate, user, service.totals_of(db, [affiliate.id], now)[affiliate.id]
    )
    view["referrals"] = [
        {
            "id": referral.id,
            "email": email,
            "status": referral.status,
            "reason": referral.reason,
            "attributed_at": referral.attributed_at,
        }
        for referral, email in db.execute(
            select(Referral, User.email)
            .join(User, User.id == Referral.referred_user_id)
            .where(Referral.affiliate_id == affiliate.id)
            .order_by(Referral.attributed_at.desc())
            .limit(200)
        )
    ]
    view["commissions"] = [
        {
            "id": commission.id,
            "plan": plan,
            "base_amount": str(commission.base_amount),
            "rate_pct": str(commission.rate_pct),
            "amount": str(commission.amount),
            "currency": commission.currency,
            "status": service.state_of(commission, now),
            "reason": commission.reason,
            "available_at": commission.available_at,
            "created_at": commission.created_at,
        }
        for commission, plan in db.execute(
            select(AffiliateCommission, PaymentOrder.plan_code)
            .join(PaymentOrder, PaymentOrder.id == AffiliateCommission.order_id)
            .where(AffiliateCommission.affiliate_id == affiliate.id)
            .order_by(AffiliateCommission.created_at.desc())
            .limit(200)
        )
    ]
    view["payouts"] = [
        {
            "id": payout.id,
            "amount": str(payout.amount),
            "currency": payout.currency,
            "method": payout.method,
            "reference": payout.reference,
            "paid_at": payout.paid_at,
        }
        for payout in db.scalars(
            select(AffiliatePayout)
            .where(AffiliatePayout.affiliate_id == affiliate.id)
            .order_by(AffiliatePayout.paid_at.desc())
            .limit(200)
        )
    ]
    return view


@router.get("/{affiliate_id}")
def read_affiliate(affiliate_id: uuid.UUID, db: Db, _: Reader) -> dict[str, Any]:
    return _detail(db, affiliate_id)


def _notify(
    db: Db, mailer: Mailer, settings: Settings, row: Affiliate, template: str, **values: object
) -> None:
    user = db.get_one(User, row.user_id)
    mailer.send(
        render(
            template,
            user.locale,
            user.email,
            first_name=user.first_name,
            link=f"{settings.public_app_url}/{user.locale}/affiliate",
            **values,
        )
    )


@router.post("/{affiliate_id}/approve")
def approve(
    affiliate_id: uuid.UUID,
    body: ReviewIn,
    request: Request,
    db: Db,
    settings: AppSettings,
    mailer: AppMailer,
    user: Writer,
) -> dict[str, Any]:
    row = service.approve(db, affiliate_id, user, body.note, client_ip(request))
    db.commit()
    _notify(db, mailer, settings, row, "affiliate_approved", code=row.code)
    return _detail(db, affiliate_id)


@router.post("/{affiliate_id}/refuse")
def refuse(
    affiliate_id: uuid.UUID,
    body: ReviewIn,
    request: Request,
    db: Db,
    settings: AppSettings,
    mailer: AppMailer,
    user: Writer,
) -> dict[str, Any]:
    row = service.refuse(db, affiliate_id, user, body.note, client_ip(request))
    db.commit()
    _notify(db, mailer, settings, row, "affiliate_refused")
    return _detail(db, affiliate_id)


@router.post("/{affiliate_id}/suspend")
def suspend(
    affiliate_id: uuid.UUID, body: ReviewIn, request: Request, db: Db, user: Writer
) -> dict[str, Any]:
    service.suspend(db, affiliate_id, user, body.note, client_ip(request))
    db.commit()
    return _detail(db, affiliate_id)


@router.post("/{affiliate_id}/payouts", status_code=201)
def record_payout(
    affiliate_id: uuid.UUID,
    body: PayoutIn,
    request: Request,
    db: Db,
    settings: AppSettings,
    mailer: AppMailer,
    user: Payer,
) -> dict[str, Any]:
    """Enregistre un versement déjà effectué : SafeTrade n'envoie aucun fonds lui-même."""
    payout = service.record_payout(
        db,
        affiliate_id,
        user,
        method=body.method,
        reference=body.reference.strip(),
        ip=client_ip(request),
    )
    db.commit()
    row = db.get_one(Affiliate, affiliate_id)
    amount = f"{payout.amount} {payout.currency}"
    _notify(db, mailer, settings, row, "affiliate_payout", amount=amount)
    return _detail(db, affiliate_id)


@router.post("/commissions/{commission_id}/release")
def release_commission(
    commission_id: uuid.UUID, request: Request, db: Db, user: Writer
) -> dict[str, Any]:
    row = service.release(db, commission_id, user, client_ip(request))
    db.commit()
    return _detail(db, row.affiliate_id)


@router.post("/commissions/{commission_id}/cancel")
def cancel_commission(
    commission_id: uuid.UUID, request: Request, db: Db, user: Writer
) -> dict[str, Any]:
    row = service.cancel(db, commission_id, user, client_ip(request))
    db.commit()
    return _detail(db, row.affiliate_id)
