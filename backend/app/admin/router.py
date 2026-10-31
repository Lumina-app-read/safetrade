"""
API d'administration. Le contrôle d'accès est posé sur le routeur lui-même : toute
route ajoutée ici exige un compte administrateur avec double authentification.
Les modules complets de la section 10 arrivent en phase 5.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select

from app import audit
from app.authz import AdminUser, Permission, permissions_of, require_admin, require_permission
from app.db.models import AuditLog, User
from app.deps import AppSettings, Db, check_origin, client_ip
from app.errors import ApiError
from app.market.router import asset_views
from app.market.store import MarketStore

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(check_origin), Depends(require_admin)],
)


@router.get("/me")
def admin_me(user: AdminUser) -> dict[str, object]:
    return {
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
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, object]:
    stmt = select(User).order_by(User.created_at.desc()).limit(limit)
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
            }
            for u in db.scalars(stmt)
        ]
    }


@router.get("/audit")
def read_audit(
    request: Request,
    db: Db,
    user: Annotated[User, Depends(require_permission(Permission.AUDIT_READ))],
    action: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict[str, object]:
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    entries = [
        {
            "id": e.id,
            "occurred_at": e.occurred_at,
            "actor_user_id": e.actor_user_id,
            "action": e.action,
            "target_type": e.target_type,
            "target_id": e.target_id,
            "result": e.result,
            "ip_address": e.ip_address,
            "details": e.details,
        }
        for e in db.scalars(stmt)
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
        "assets": await asset_views(store, settings.market_symbols),
        "alerts": alerts[:50],
    }
