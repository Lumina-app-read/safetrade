"""
API d'administration. Le contrôle d'accès est posé sur le routeur lui-même : toute
route ajoutée ici exige un compte administrateur avec double authentification.
Les modules complets de la section 10 arrivent en phase 5.
"""

import uuid
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from app import audit, site
from app.admin.common import access_view, target_user
from app.authz import (
    AdminUser,
    CurrentSession,
    Permission,
    permissions_of,
    require_admin,
    require_permission,
)
from app.billing import service as billing
from app.db.models import AuditLog, Plan, SiteSetting, User, UserRole, UserStatus
from app.deps import AppSettings, Db, check_origin, client_ip
from app.errors import ApiError
from app.market.router import asset_views
from app.market.store import MarketStore

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(check_origin), Depends(require_admin)],
)


class SiteIn(BaseModel):
    deriv_signup_url: str | None = Field(default=None, max_length=500)


class GrantIn(BaseModel):
    plan: str = Field(min_length=1, max_length=20)
    days: int | None = Field(default=None, ge=1, le=billing.MAX_GRANT_DAYS)
    # Motif obligatoire : il reste dans le journal d'audit.
    note: str = Field(min_length=5, max_length=300)


class RevokeIn(BaseModel):
    note: str = Field(min_length=5, max_length=300)


def clean_url(raw: str | None) -> str | None:
    """Vide : le lien disparaît du site. Sinon, une adresse https sans identifiants."""
    url = (raw or "").strip()
    if not url:
        return None
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or " " in url:
        raise ApiError(422, "admin.invalid_url")
    return url


@router.get("/me")
def admin_me(user: AdminUser, session: CurrentSession) -> dict[str, object]:
    return {
        "admin_until": session.admin_until,
        "user": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "role": user.role,
        },
        "permissions": sorted(permissions_of(user)),
    }


@router.get("/users")
def list_users(
    db: Db,
    _: Annotated[User, Depends(require_permission(Permission.USERS_READ))],
    q: Annotated[str | None, Query(max_length=100)] = None,
    status: Annotated[UserStatus | None, Query()] = None,
    role: Annotated[UserRole | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, object]:
    stmt = select(User).order_by(User.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(User.status == status)
    if role:
        stmt = stmt.where(User.role == role)
    if q:
        # Les jokers SQL saisis (%, _) sont recherchés littéralement.
        term = q.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{term}%"
        stmt = stmt.where(
            or_(
                func.lower(User.email).like(pattern, escape="\\"),
                func.lower(User.first_name).like(pattern, escape="\\"),
            )
        )
    # Jamais de secret : ni empreinte de mot de passe, ni secret TOTP, ni token Deriv.
    return {
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "first_name": u.first_name,
                "role": u.role,
                "status": u.status,
                "email_verified": u.email_verified_at is not None,
                "mfa_enabled": u.totp_enabled_at is not None,
                "created_at": u.created_at,
                "access": access_view(db, u),
            }
            for u in db.scalars(stmt)
        ]
    }


@router.get("/users/{user_id}/subscriptions")
def user_subscriptions(
    user_id: uuid.UUID,
    db: Db,
    _: Annotated[User, Depends(require_permission(Permission.USERS_READ))],
) -> dict[str, object]:
    user = target_user(db, user_id)
    plans = db.scalars(
        select(Plan)
        .where(Plan.active.is_(True), Plan.code != billing.TRIAL)
        .order_by(Plan.duration_days)
    )
    return {
        "user": {"id": user.id, "email": user.email, "first_name": user.first_name},
        "access": access_view(db, user),
        "history": billing.history_view(db, user),
        "plans": [{"code": p.code, "days": p.duration_days} for p in plans],
    }


@router.post("/users/{user_id}/subscriptions", status_code=201)
def grant_subscription(
    user_id: uuid.UUID,
    body: GrantIn,
    request: Request,
    db: Db,
    admin: Annotated[User, Depends(require_permission(Permission.SUBSCRIPTIONS_WRITE))],
) -> dict[str, object]:
    user = target_user(db, user_id)
    billing.grant(
        db,
        admin,
        user,
        plan_code=body.plan,
        days=body.days,
        note=body.note.strip(),
        ip=client_ip(request),
    )
    db.commit()
    return {"access": access_view(db, user), "history": billing.history_view(db, user)}


@router.post("/users/{user_id}/subscriptions/{subscription_id}/revoke")
def revoke_subscription(
    user_id: uuid.UUID,
    subscription_id: uuid.UUID,
    body: RevokeIn,
    request: Request,
    db: Db,
    admin: Annotated[User, Depends(require_permission(Permission.SUBSCRIPTIONS_WRITE))],
) -> dict[str, object]:
    user = target_user(db, user_id)
    billing.revoke(db, admin, user, subscription_id, note=body.note.strip(), ip=client_ip(request))
    db.commit()
    return {"access": access_view(db, user), "history": billing.history_view(db, user)}


@router.get("/audit")
def read_audit(
    request: Request,
    db: Db,
    user: Annotated[User, Depends(require_permission(Permission.AUDIT_READ))],
    action: Annotated[str | None, Query(max_length=100)] = None,
    actor: Annotated[str | None, Query(max_length=320)] = None,
    before: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict[str, object]:
    stmt = (
        select(AuditLog, User.email)
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .order_by(AuditLog.id.desc())
        .limit(limit)
    )
    if action:
        # Préfixe accepté : « admin. » montre toutes les actions d'administration.
        stmt = stmt.where(
            AuditLog.action.startswith(action, autoescape=True)
            if action.endswith(".")
            else AuditLog.action == action
        )
    if actor:
        stmt = stmt.where(func.lower(User.email) == actor.strip().lower())
    if before:
        stmt = stmt.where(AuditLog.id < before)
    entries = [
        {
            "id": e.id,
            "occurred_at": e.occurred_at,
            "actor_user_id": e.actor_user_id,
            "actor_email": email,
            "action": e.action,
            "target_type": e.target_type,
            "target_id": e.target_id,
            "result": e.result,
            "ip_address": e.ip_address,
            "details": e.details,
        }
        for e, email in db.execute(stmt).all()
    ]
    # La consultation du journal est elle-même une action tracée.
    audit.record(
        db,
        "admin.audit.view",
        "success",
        actor_user_id=user.id,
        ip_address=client_ip(request),
        details={"action_filter": action, "count": len(entries)},
    )
    db.commit()
    return {"entries": entries}


@router.get("/site")
def read_site(
    db: Db, _: Annotated[User, Depends(require_permission(Permission.SETTINGS_WRITE))]
) -> dict[str, str | None]:
    return {"deriv_signup_url": site.deriv_signup_url(db)}


@router.put("/site")
def write_site(
    body: SiteIn,
    request: Request,
    db: Db,
    user: Annotated[User, Depends(require_permission(Permission.SETTINGS_WRITE))],
) -> dict[str, str | None]:
    url = clean_url(body.deriv_signup_url)
    row = db.get(SiteSetting, site.DERIV_SIGNUP_URL)
    if url is None and row is not None:
        db.delete(row)
    elif url is not None and row is None:
        db.add(SiteSetting(key=site.DERIV_SIGNUP_URL, value=url, updated_by=user.id))
    elif url is not None and row is not None:
        row.value, row.updated_by = url, user.id
    audit.record(
        db,
        "admin.site_settings",
        "success",
        actor_user_id=user.id,
        ip_address=client_ip(request),
        details={"deriv_signup_url": url},
    )
    db.commit()
    return {"deriv_signup_url": url}


@router.get("/monitoring/market")
async def market_monitoring(
    request: Request,
    settings: AppSettings,
    _: Annotated[User, Depends(require_permission(Permission.MONITORING_READ))],
) -> dict[str, object]:
    """Connexion, latence, erreurs Deriv, alertes et statut de chaque actif."""
    store: MarketStore | None = request.app.state.market
    if store is None:
        raise ApiError(503, "market.unavailable")
    alerts = await store.get_alerts()
    return {
        "feed": await store.get_health(),
        "assets": await asset_views(store),
        "alerts": alerts[:50],
    }


# Modules complets de la section 10, protégés par les dépendances de ce routeur.
from app.admin import accounts, operations, site_admin  # noqa: E402

router.include_router(accounts.router)
router.include_router(operations.router)
router.include_router(site_admin.router)
