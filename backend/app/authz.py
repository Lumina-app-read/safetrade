"""
Contrôle d'accès (étape 1.7) : session obligatoire, rôles et permissions.

Les rôles administrateur sont différenciés (section 3) : chacun n'a que les
permissions nécessaires. Tout compte administrateur doit avoir activé la double
authentification (section 14) pour utiliser une route d'administration.
"""

import enum
from collections.abc import Callable
from typing import Annotated

from fastapi import Cookie, Depends, Request

from app import audit
from app.auth import service
from app.db.models import Session, User, UserRole
from app.deps import AppSettings, Db, client_ip
from app.errors import ApiError

SESSION_COOKIE = "st_session"


class Permission(enum.StrEnum):
    USERS_READ = "users.read"
    USERS_WRITE = "users.write"
    AUDIT_READ = "audit.read"
    PAYMENTS_READ = "payments.read"
    RISK_WRITE = "risk.write"
    SETTINGS_WRITE = "settings.write"
    TEAM_WRITE = "team.write"
    MONITORING_READ = "monitoring.read"
    AFFILIATES_READ = "affiliates.read"
    AFFILIATES_WRITE = "affiliates.write"
    PAYOUTS_WRITE = "payouts.write"


ADMIN_ROLES = frozenset({UserRole.SUPER_ADMIN, UserRole.SUPPORT, UserRole.FINANCE})

ROLE_PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    UserRole.SUPER_ADMIN: frozenset(Permission),
    # Support : consulter et aider les comptes, jamais les paiements ni les réglages.
    UserRole.SUPPORT: frozenset({Permission.USERS_READ}),
    # Finance : paiements, consultation des comptes et versements aux affiliés.
    UserRole.FINANCE: frozenset(
        {
            Permission.PAYMENTS_READ,
            Permission.USERS_READ,
            Permission.AFFILIATES_READ,
            Permission.PAYOUTS_WRITE,
        }
    ),
    UserRole.CLIENT: frozenset(),
    UserRole.AFFILIATE: frozenset(),
}


def permissions_of(user: User) -> frozenset[Permission]:
    return ROLE_PERMISSIONS.get(user.role, frozenset())


def current_session(
    db: Db,
    settings: AppSettings,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> Session:
    """Session valide (sinon 401) ; la session est renouvelée à chaque appel."""
    _, session = service.authenticate(db, settings, token)
    return session


CurrentSession = Annotated[Session, Depends(current_session)]


def _deny(db: Db, request: Request, user: User, reason: str, code: str) -> ApiError:
    audit.record(
        db,
        "authz.denied",
        "denied",
        actor_user_id=user.id,
        ip_address=client_ip(request),
        details={"path": request.url.path, "reason": reason},
    )
    db.commit()
    return ApiError(403, code)


def require_admin(request: Request, db: Db, session: CurrentSession) -> User:
    """Compte administrateur avec double authentification activée."""
    user = session.user
    if user.role not in ADMIN_ROLES:
        raise _deny(db, request, user, "not_admin", "authz.forbidden")
    if user.totp_enabled_at is None:
        raise _deny(db, request, user, "admin_without_mfa", "authz.mfa_required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def require_permission(permission: Permission) -> Callable[..., User]:
    """Dépendance : administrateur disposant de la permission demandée."""

    def check(request: Request, db: Db, user: AdminUser) -> User:
        if permission not in permissions_of(user):
            raise _deny(db, request, user, f"missing:{permission}", "authz.forbidden")
        return user

    return check
