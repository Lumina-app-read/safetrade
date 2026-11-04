"""
Fiche utilisateur, actions sur un compte et équipe d'administration (section 10).

Jamais de secret dans une réponse : ni empreinte de mot de passe, ni secret TOTP, ni token
Deriv. Chaque action est inscrite au journal d'audit avec son motif.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update

from app import audit
from app.admin.common import access_view, target_user
from app.auth.admin_access import ADMIN_ROLES
from app.authz import Permission, permissions_of, require_permission
from app.billing import service as billing
from app.db.models import (
    Affiliate,
    BotSession,
    DerivConnectionRecord,
    PaymentOrder,
    Referral,
    Session,
    TradingPosition,
    User,
    UserRole,
    UserStatus,
)
from app.deps import Db, client_ip
from app.errors import ApiError

router = APIRouter()


class NoteIn(BaseModel):
    note: str = Field(min_length=5, max_length=300)


class RoleIn(BaseModel):
    role: UserRole
    note: str = Field(min_length=5, max_length=300)


def _now() -> datetime:
    return datetime.now(UTC)


def _close_sessions(db: Db, user: User) -> int:
    result = db.execute(
        update(Session)
        .where(Session.user_id == user.id, Session.revoked_at.is_(None))
        .values(revoked_at=_now(), admin_until=None, admin_seen_at=None)
    )
    return int(getattr(result, "rowcount", 0) or 0)


def _profile(db: Db, user: User) -> dict[str, object]:
    last_seen = db.scalar(select(func.max(Session.last_seen_at)).where(Session.user_id == user.id))
    open_sessions = db.scalar(
        select(func.count())
        .select_from(Session)
        .where(
            Session.user_id == user.id,
            Session.revoked_at.is_(None),
            Session.expires_at > _now(),
        )
    )
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "role": user.role,
        "status": user.status,
        "locale": user.locale,
        "email_verified": user.email_verified_at is not None,
        "mfa_enabled": user.totp_enabled_at is not None,
        "created_at": user.created_at,
        "last_seen_at": last_seen,
        "open_sessions": open_sessions or 0,
    }


def _trading(db: Db, user: User) -> dict[str, object]:
    connection = db.scalars(
        select(DerivConnectionRecord).where(DerivConnectionRecord.user_id == user.id)
    ).first()
    bots = db.scalars(
        select(BotSession)
        .where(BotSession.user_id == user.id)
        .order_by(BotSession.started_at.desc())
        .limit(10)
    ).all()
    closed = db.execute(
        select(func.count(), func.coalesce(func.sum(TradingPosition.net_result), 0)).where(
            TradingPosition.user_id == user.id, TradingPosition.closed_at.is_not(None)
        )
    ).one()
    return {
        # Compte relié seulement : le token reste chiffré en base et ne sort jamais.
        "deriv": None
        if connection is None
        else {
            "account_id": connection.account_id,
            "account_kind": connection.account_kind,
            "currency": connection.currency,
            "method": connection.auth_method,
            "connected_at": connection.created_at,
        },
        "bots": [
            {
                "id": bot.id,
                "symbol": bot.symbol,
                "account_kind": bot.account_kind,
                "state": bot.state,
                "stop_reason": bot.stop_reason,
                "started_at": bot.started_at,
                "ended_at": bot.ended_at,
            }
            for bot in bots
        ],
        "closed_positions": closed[0],
        "net_result": str(Decimal(closed[1] or 0)),
    }


def _payments(db: Db, user: User) -> list[dict[str, object]]:
    orders = db.scalars(
        select(PaymentOrder)
        .where(PaymentOrder.user_id == user.id)
        .order_by(PaymentOrder.created_at.desc())
        .limit(20)
    )
    return [billing.order_view(order) for order in orders]


def _affiliation(db: Db, user: User) -> dict[str, object]:
    own = db.scalars(select(Affiliate).where(Affiliate.user_id == user.id)).first()
    referral = db.scalars(select(Referral).where(Referral.referred_user_id == user.id)).first()
    sponsor = None
    if referral is not None:
        parent = db.get(Affiliate, referral.affiliate_id)
        sponsor = None if parent is None else db.get_one(User, parent.user_id).email
    return {
        "affiliate_status": own.status if own else None,
        "affiliate_code": own.code if own else None,
        "referred_by": sponsor,
    }


@router.get("/users/{user_id}")
def user_detail(
    user_id: uuid.UUID,
    db: Db,
    admin: Annotated[User, Depends(require_permission(Permission.USERS_READ))],
) -> dict[str, object]:
    user = target_user(db, user_id)
    allowed = permissions_of(admin)
    return {
        "profile": _profile(db, user),
        "access": access_view(db, user),
        "history": billing.history_view(db, user),
        "trading": _trading(db, user),
        "payments": _payments(db, user) if Permission.PAYMENTS_READ in allowed else None,
        "affiliation": _affiliation(db, user),
    }


def _guard(admin: User, user: User) -> None:
    if admin.id == user.id:
        raise ApiError(403, "admin.self_action")
    if user.role == UserRole.SUPER_ADMIN:
        raise ApiError(403, "admin.protected_account")


@router.post("/users/{user_id}/suspend")
def suspend(
    user_id: uuid.UUID,
    body: NoteIn,
    request: Request,
    db: Db,
    admin: Annotated[User, Depends(require_permission(Permission.USERS_WRITE))],
) -> dict[str, object]:
    """Plus de connexion ni de bot ; les positions ouvertes finissent sous leur stop loss."""
    user = target_user(db, user_id)
    _guard(admin, user)
    if user.status == UserStatus.SUSPENDED:
        raise ApiError(409, "admin.already_suspended")
    user.status = UserStatus.SUSPENDED
    closed = _close_sessions(db, user)
    audit.record(
        db, "admin.user.suspend", "success", actor_user_id=admin.id, target_type="user",
        target_id=str(user.id), ip_address=client_ip(request),
        details={"note": body.note.strip(), "sessions_closed": closed},
    )  # fmt: skip
    db.commit()
    return {"profile": _profile(db, user), "access": access_view(db, user)}


@router.post("/users/{user_id}/reactivate")
def reactivate(
    user_id: uuid.UUID,
    body: NoteIn,
    request: Request,
    db: Db,
    admin: Annotated[User, Depends(require_permission(Permission.USERS_WRITE))],
) -> dict[str, object]:
    user = target_user(db, user_id)
    if user.status != UserStatus.SUSPENDED:
        raise ApiError(409, "admin.not_suspended")
    user.status = UserStatus.ACTIVE
    audit.record(
        db, "admin.user.reactivate", "success", actor_user_id=admin.id, target_type="user",
        target_id=str(user.id), ip_address=client_ip(request), details={"note": body.note.strip()},
    )  # fmt: skip
    db.commit()
    return {"profile": _profile(db, user), "access": access_view(db, user)}


@router.post("/users/{user_id}/sessions/revoke")
def revoke_sessions(
    user_id: uuid.UUID,
    body: NoteIn,
    request: Request,
    db: Db,
    admin: Annotated[User, Depends(require_permission(Permission.USERS_WRITE))],
) -> dict[str, object]:
    user = target_user(db, user_id)
    _guard(admin, user)
    closed = _close_sessions(db, user)
    audit.record(
        db, "admin.user.sessions_revoke", "success", actor_user_id=admin.id, target_type="user",
        target_id=str(user.id), ip_address=client_ip(request),
        details={"note": body.note.strip(), "sessions_closed": closed},
    )  # fmt: skip
    db.commit()
    return {"profile": _profile(db, user)}


# Équipe et rôles.


@router.get("/team")
def team(
    db: Db, _: Annotated[User, Depends(require_permission(Permission.TEAM_WRITE))]
) -> dict[str, object]:
    members = db.scalars(
        select(User).where(User.role.in_(list(ADMIN_ROLES))).order_by(User.created_at)
    )
    return {
        "members": [
            {
                "id": m.id,
                "email": m.email,
                "first_name": m.first_name,
                "role": m.role,
                "status": m.status,
                "mfa_enabled": m.totp_enabled_at is not None,
                "permissions": sorted(permissions_of(m)),
            }
            for m in members
        ],
        "roles": [
            role.value for role in (UserRole.SUPER_ADMIN, UserRole.SUPPORT, UserRole.FINANCE)
        ],
    }


@router.put("/team/{user_id}")
def set_role(
    user_id: uuid.UUID,
    body: RoleIn,
    request: Request,
    db: Db,
    admin: Annotated[User, Depends(require_permission(Permission.TEAM_WRITE))],
) -> dict[str, object]:
    """Promotion ou retrait d'un rôle. Le compte doit déjà exister et avoir vérifié son e-mail."""
    user = target_user(db, user_id)
    if admin.id == user.id:
        raise ApiError(403, "admin.self_action")
    if body.role == UserRole.AFFILIATE:
        raise ApiError(422, "admin.invalid_role")
    if user.email_verified_at is None:
        raise ApiError(409, "admin.email_not_verified")
    if user.role == UserRole.SUPER_ADMIN and body.role != UserRole.SUPER_ADMIN:
        others = db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == UserRole.SUPER_ADMIN, User.id != user.id)
        )
        if not others:
            raise ApiError(409, "admin.last_super_admin")
    before = user.role
    user.role = body.role
    if body.role not in ADMIN_ROLES:
        # Un rôle retiré ferme aussitôt l'administration ouverte sur ses sessions.
        db.execute(
            update(Session)
            .where(Session.user_id == user.id)
            .values(admin_until=None, admin_seen_at=None)
        )
    audit.record(
        db, "admin.team.role", "success", actor_user_id=admin.id, target_type="user",
        target_id=str(user.id), ip_address=client_ip(request),
        details={"from": before, "to": body.role, "note": body.note.strip()},
    )  # fmt: skip
    db.commit()
    return {"id": user.id, "role": user.role}
