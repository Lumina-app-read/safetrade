"""
Affiliation (section 13) : demande, attribution, commissions et versements.

Le rattachement se décide une seule fois, à l'inscription. Une commission ne naît que dans la
transaction qui valide un paiement (`billing.service.settle`), et son solde est calculé ici :
le navigateur ne fournit jamais un montant.
"""

import hashlib
import hmac
import ipaddress
import re
import secrets
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_DOWN, Decimal

from sqlalchemy import exists, select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import aliased

from app import audit
from app.config import Settings
from app.db.models import (
    Affiliate,
    AffiliateCommission,
    AffiliatePayout,
    AffiliateProgram,
    PaymentOrder,
    Referral,
    Session,
    User,
    UserRole,
    UserStatus,
)
from app.errors import ApiError

PENDING = "pending"
APPROVED = "approved"
REFUSED = "refused"
SUSPENDED = "suspended"

ACTIVE = "active"
REVIEW = "review"
BLOCKED = "blocked"

HELD = "held"
PAID = "paid"
CANCELLED = "cancelled"

# Devise de référence de tous les prix : les commissions et les soldes y sont tenus.
CURRENCY = "USD"
CENT = Decimal("0.01")
# Sans 0, O, 1 ni I : un code se dicte et se recopie sans erreur.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8
PHONE = re.compile(r"\d{6,15}")


def program(db: DbSession) -> AffiliateProgram:
    return db.get_one(AffiliateProgram, 1)


def fingerprint(settings: Settings, phone: str) -> bytes:
    """Empreinte d'un numéro : comparable, sans conserver le numéro."""
    secret = settings.encryption_key.get_secret_value() if settings.encryption_key else "dev"
    return hmac.new(secret.encode(), f"payer:{phone}".encode(), hashlib.sha256).digest()


def identity(email: str) -> str:
    """Même boîte aux lettres : alias « +tag », et points ignorés par Gmail."""
    local, _, domain = email.strip().lower().partition("@")
    local = local.split("+", 1)[0]
    if domain in ("gmail.com", "googlemail.com"):
        return f"{local.replace('.', '')}@gmail.com"
    return f"{local}@{domain}"


def find_code(db: DbSession, raw: str) -> Affiliate | None:
    """Affilié approuvé pour ce code. Champ vide : aucun. Code inconnu : refus explicite."""
    code = raw.strip().upper()
    if not code:
        return None
    row = db.scalars(
        select(Affiliate).where(Affiliate.code == code, Affiliate.status == APPROVED)
    ).first()
    if row is None:
        raise ApiError(422, "affiliate.unknown_code")
    return row


def _device_used(db: DbSession, user_id: uuid.UUID, device: bytes) -> bool:
    return (
        db.scalars(
            select(Session.id).where(Session.user_id == user_id, Session.device_hash == device)
        ).first()
        is not None
    )


def _address_used(db: DbSession, user_id: uuid.UUID, ip: str | None) -> bool:
    """Adresse publique uniquement : une adresse interne est commune à tous les visiteurs."""
    if ip is None or not ipaddress.ip_address(ip).is_global:
        return False
    return (
        db.scalars(
            select(Session.id).where(Session.user_id == user_id, Session.ip_address == ip)
        ).first()
        is not None
    )


def _devices_shared(db: DbSession, first: uuid.UUID, second: uuid.UUID) -> bool:
    other = aliased(Session)
    return bool(
        db.scalar(
            select(
                exists().where(
                    Session.user_id == first,
                    other.user_id == second,
                    Session.device_hash == other.device_hash,
                    Session.device_hash.is_not(None),
                )
            )
        )
    )


def attribute(
    db: DbSession,
    user: User,
    affiliate: Affiliate,
    ip: str | None,
    device: bytes | None,
    now: datetime | None = None,
) -> Referral:
    """
    Rattache un nouveau compte. Une même identité ou un même appareil bloque le parrainage ;
    une même adresse réseau ne prouve rien (réseau partagé) : l'administrateur tranche.
    """
    owner = db.get_one(User, affiliate.user_id)
    status, reason = ACTIVE, None
    if identity(user.email) == identity(owner.email):
        status, reason = BLOCKED, "same_identity"
    elif device is not None and _device_used(db, owner.id, device):
        status, reason = BLOCKED, "same_device"
    elif _address_used(db, owner.id, ip):
        status, reason = REVIEW, "same_address"
    row = Referral(
        affiliate_id=affiliate.id,
        referred_user_id=user.id,
        status=status,
        reason=reason,
        attributed_at=now or datetime.now(UTC),
    )
    db.add(row)
    audit.record(
        db,
        "affiliate.attribution",
        "denied" if status == BLOCKED else "success",
        actor_user_id=user.id,
        target_type="affiliate",
        target_id=str(affiliate.id),
        ip_address=ip,
        details={"status": status, "reason": reason},
    )
    return row


def _paid_before(db: DbSession, order: PaymentOrder) -> bool:
    return (
        db.scalars(
            select(PaymentOrder.id).where(
                PaymentOrder.user_id == order.user_id,
                PaymentOrder.status == PAID,
                PaymentOrder.id != order.id,
            )
        ).first()
        is not None
    )


def _commissioned(db: DbSession, referral: Referral) -> bool:
    return (
        db.scalars(
            select(AffiliateCommission.id).where(
                AffiliateCommission.referral_id == referral.id,
                AffiliateCommission.status != CANCELLED,
            )
        ).first()
        is not None
    )


def _same_payer(db: DbSession, order: PaymentOrder, affiliate: Affiliate) -> bool:
    if order.payer_hash is None:
        return False
    if order.payer_hash == affiliate.payout_hash:
        return True
    return (
        db.scalars(
            select(PaymentOrder.id).where(
                PaymentOrder.user_id == affiliate.user_id,
                PaymentOrder.payer_hash == order.payer_hash,
            )
        ).first()
        is not None
    )


def credit(
    db: DbSession, order: PaymentOrder, now: datetime | None = None
) -> AffiliateCommission | None:
    """
    Appelée quand un paiement vient d'être validé. Le filleul est verrouillé : deux paiements
    simultanés ne créent pas deux commissions de « premier paiement ».
    """
    referral = db.scalars(
        select(Referral).where(Referral.referred_user_id == order.user_id).with_for_update()
    ).first()
    if referral is None or referral.status == BLOCKED:
        return None
    affiliate = db.get_one(Affiliate, referral.affiliate_id)
    if affiliate.status != APPROVED:
        return None
    moment = now or datetime.now(UTC)
    rules = program(db)
    if _paid_before(db, order):
        if not rules.recurring or not _commissioned(db, referral):
            return None
    elif moment > referral.attributed_at + timedelta(days=rules.attribution_days):
        return None
    amount = (order.amount * rules.rate_pct / 100).quantize(CENT, rounding=ROUND_DOWN)
    if amount <= 0:
        return None

    fraud = None
    if _same_payer(db, order, affiliate):
        fraud = "same_payer"
    elif _devices_shared(db, affiliate.user_id, order.user_id):
        fraud = "same_device"
    if fraud:
        referral.status, referral.reason = BLOCKED, fraud
    row = AffiliateCommission(
        affiliate_id=affiliate.id,
        referral_id=referral.id,
        order_id=order.id,
        base_amount=order.amount,
        rate_pct=rules.rate_pct,
        amount=amount,
        currency=order.currency,
        status=CANCELLED if fraud else HELD,
        reason=fraud or (referral.reason if referral.status == REVIEW else None),
        available_at=moment + timedelta(days=rules.hold_days),
    )
    db.add(row)
    db.flush()
    audit.record(
        db,
        "affiliate.commission",
        "denied" if fraud else "success",
        actor_user_id=order.user_id,
        target_type="commission",
        target_id=str(row.id),
        details={
            "affiliate": str(affiliate.id),
            "order": str(order.id),
            "amount": str(amount),
            "rate_pct": str(rules.rate_pct),
            "reason": row.reason,
        },
    )
    return row


def state_of(row: AffiliateCommission, now: datetime) -> str:
    """held, review, available, paid ou cancelled : `review` n'est jamais montré au client."""
    if row.status != HELD:
        return row.status
    if row.reason:
        return REVIEW
    return "available" if row.available_at <= now else HELD


@dataclass
class Totals:
    referrals: int = 0
    converted: int = 0
    held: Decimal = Decimal(0)
    available: Decimal = Decimal(0)
    paid: Decimal = Decimal(0)

    def view(self) -> dict[str, object]:
        return {
            "referrals": self.referrals,
            "converted": self.converted,
            "held": str(self.held),
            "available": str(self.available),
            "paid": str(self.paid),
            "currency": CURRENCY,
        }


def totals_of(
    db: DbSession, ids: Iterable[uuid.UUID], now: datetime | None = None
) -> dict[uuid.UUID, Totals]:
    moment = now or datetime.now(UTC)
    found = {affiliate_id: Totals() for affiliate_id in ids}
    if not found:
        return found
    for affiliate_id in db.scalars(
        select(Referral.affiliate_id).where(
            Referral.affiliate_id.in_(found), Referral.status != BLOCKED
        )
    ):
        found[affiliate_id].referrals += 1
    referrals: dict[uuid.UUID, set[uuid.UUID]] = {key: set() for key in found}
    for row in db.scalars(
        select(AffiliateCommission).where(AffiliateCommission.affiliate_id.in_(found))
    ):
        state = state_of(row, moment)
        total = found[row.affiliate_id]
        if state == CANCELLED:
            continue
        referrals[row.affiliate_id].add(row.referral_id)
        if state == "available":
            total.available += row.amount
        elif state == PAID:
            total.paid += row.amount
        else:
            total.held += row.amount
    for key, converted in referrals.items():
        found[key].converted = len(converted)
    return found


def apply(
    db: DbSession,
    settings: Settings,
    user: User,
    *,
    message: str,
    payout_details: str,
    accept_terms: bool,
    ip: str | None,
) -> Affiliate:
    if not accept_terms:
        raise ApiError(422, "affiliate.terms_required")
    if user.role not in (UserRole.CLIENT, UserRole.AFFILIATE):
        raise ApiError(403, "affiliate.not_eligible")
    row = db.scalars(select(Affiliate).where(Affiliate.user_id == user.id)).first()
    if row is not None and row.status != REFUSED:
        raise ApiError(409, "affiliate.already_applied")
    digits = re.sub(r"\D", "", payout_details)
    payout_hash = fingerprint(settings, digits) if PHONE.fullmatch(digits) else None
    moment = datetime.now(UTC)
    if row is None:
        row = Affiliate(
            user_id=user.id,
            message=message,
            payout_details=payout_details,
            payout_hash=payout_hash,
            terms_accepted_at=moment,
        )
        db.add(row)
    else:
        row.status = PENDING
        row.message = message
        row.payout_details = payout_details
        row.payout_hash = payout_hash
        row.terms_accepted_at = moment
    db.flush()
    _trace(db, "apply", row, user.id, ip)
    return row


def _trace(
    db: DbSession,
    action: str,
    row: Affiliate,
    actor: uuid.UUID,
    ip: str | None,
    note: str | None = None,
) -> None:
    audit.record(
        db,
        f"affiliate.{action}",
        "success",
        actor_user_id=actor,
        target_type="affiliate",
        target_id=str(row.id),
        ip_address=ip,
        details={"note": note} if note else None,
    )


def _locked(db: DbSession, affiliate_id: uuid.UUID) -> Affiliate:
    row = db.scalars(
        select(Affiliate).where(Affiliate.id == affiliate_id).with_for_update()
    ).first()
    if row is None:
        raise ApiError(404, "affiliate.not_found")
    return row


def _new_code(db: DbSession) -> str:
    while True:
        code = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
        if db.scalars(select(Affiliate.id).where(Affiliate.code == code)).first() is None:
            return code


def _review(row: Affiliate, status: str, admin: User, note: str | None, moment: datetime) -> None:
    row.status = status
    row.reviewed_by = admin.id
    row.reviewed_at = moment
    row.review_note = note


def approve(
    db: DbSession, affiliate_id: uuid.UUID, admin: User, note: str | None, ip: str | None
) -> Affiliate:
    """Approbation d'une demande, ou reprise d'un affilié suspendu : le code ne change pas."""
    row = _locked(db, affiliate_id)
    if row.status not in (PENDING, SUSPENDED):
        raise ApiError(409, "affiliate.invalid_state")
    user = db.get_one(User, row.user_id)
    if user.status != UserStatus.ACTIVE:
        raise ApiError(409, "affiliate.invalid_state")
    row.code = row.code or _new_code(db)
    _review(row, APPROVED, admin, note, datetime.now(UTC))
    if user.role == UserRole.CLIENT:
        user.role = UserRole.AFFILIATE
    _trace(db, "approve", row, admin.id, ip, note)
    return row


def refuse(
    db: DbSession, affiliate_id: uuid.UUID, admin: User, note: str | None, ip: str | None
) -> Affiliate:
    row = _locked(db, affiliate_id)
    if row.status != PENDING:
        raise ApiError(409, "affiliate.invalid_state")
    _review(row, REFUSED, admin, note, datetime.now(UTC))
    _trace(db, "refuse", row, admin.id, ip, note)
    return row


def suspend(
    db: DbSession, affiliate_id: uuid.UUID, admin: User, note: str | None, ip: str | None
) -> Affiliate:
    """Le code cesse de fonctionner ; plus de commission ni de versement jusqu'à la reprise."""
    row = _locked(db, affiliate_id)
    if row.status != APPROVED:
        raise ApiError(409, "affiliate.invalid_state")
    _review(row, SUSPENDED, admin, note, datetime.now(UTC))
    user = db.get_one(User, row.user_id)
    if user.role == UserRole.AFFILIATE:
        user.role = UserRole.CLIENT
    _trace(db, "suspend", row, admin.id, ip, note)
    return row


def _commission(db: DbSession, commission_id: uuid.UUID) -> AffiliateCommission:
    row = db.scalars(
        select(AffiliateCommission).where(AffiliateCommission.id == commission_id).with_for_update()
    ).first()
    if row is None:
        raise ApiError(404, "affiliate.not_found")
    return row


def _trace_commission(
    db: DbSession, action: str, row: AffiliateCommission, admin: User, ip: str | None
) -> None:
    audit.record(
        db,
        f"affiliate.commission_{action}",
        "success",
        actor_user_id=admin.id,
        target_type="commission",
        target_id=str(row.id),
        ip_address=ip,
        details={"amount": str(row.amount), "reason": row.reason},
    )


def release(
    db: DbSession, commission_id: uuid.UUID, admin: User, ip: str | None
) -> AffiliateCommission:
    """Lève une réserve. Le délai de rétractation, lui, reste dû."""
    row = _commission(db, commission_id)
    if row.status != HELD or not row.reason:
        raise ApiError(409, "affiliate.invalid_state")
    _trace_commission(db, "release", row, admin, ip)
    row.reason = None
    return row


def cancel(
    db: DbSession, commission_id: uuid.UUID, admin: User, ip: str | None
) -> AffiliateCommission:
    """Remboursement, fraude : une commission déjà versée ne se change plus."""
    row = _commission(db, commission_id)
    if row.status != HELD:
        raise ApiError(409, "affiliate.invalid_state")
    row.status = CANCELLED
    row.reason = row.reason or "admin"
    _trace_commission(db, "cancel", row, admin, ip)
    return row


def record_payout(
    db: DbSession,
    affiliate_id: uuid.UUID,
    admin: User,
    *,
    method: str,
    reference: str,
    ip: str | None,
) -> AffiliatePayout:
    """
    Verse tout le disponible, d'un seul geste. Affilié et commissions verrouillés : un second
    clic ne trouve plus rien à verser. Le montant ne vient jamais de la requête.
    """
    moment = datetime.now(UTC)
    affiliate = _locked(db, affiliate_id)
    if affiliate.status != APPROVED:
        raise ApiError(409, "affiliate.invalid_state")
    due = list(
        db.scalars(
            select(AffiliateCommission)
            .where(
                AffiliateCommission.affiliate_id == affiliate.id,
                AffiliateCommission.status == HELD,
                AffiliateCommission.reason.is_(None),
                AffiliateCommission.available_at <= moment,
            )
            .with_for_update()
        )
    )
    if not due:
        raise ApiError(409, "affiliate.nothing_to_pay")
    payout = AffiliatePayout(
        affiliate_id=affiliate.id,
        amount=sum((row.amount for row in due), Decimal(0)),
        currency=CURRENCY,
        method=method,
        reference=reference,
        paid_by=admin.id,
        paid_at=moment,
    )
    db.add(payout)
    db.flush()
    for row in due:
        row.status = PAID
        row.payout_id = payout.id
    audit.record(
        db,
        "affiliate.payout",
        "success",
        actor_user_id=admin.id,
        target_type="affiliate",
        target_id=str(affiliate.id),
        ip_address=ip,
        details={
            "payout": str(payout.id),
            "amount": str(payout.amount),
            "method": method,
            "commissions": len(due),
        },
    )
    return payout
