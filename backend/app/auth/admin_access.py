"""
Entrée dans l'administration : une seconde connexion, sur une session client déjà ouverte.

Chaque étape est un frein de plus pour qui aurait volé une session ou un mot de passe :

1. session client valide, compte administrateur, double authentification activée ;
2. mot de passe saisi à nouveau, et code de l'application d'authentification (pas de code de
   secours : il se perd plus facilement qu'un téléphone) ;
3. trois échecs ferment la session entière et bloquent l'administration pendant 15 minutes ;
4. accès lié à la session, à l'adresse et au navigateur ; fin après 15 minutes sans activité,
   et au plus tard après une heure ;
5. chaque entrée, chaque échec et chaque blocage est journalisé, et le titulaire est prévenu
   par e-mail.
"""

import ipaddress
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session as DbSession

from app import audit
from app.auth import mfa, security
from app.auth.mailer import Mailer, render
from app.auth.rate_limit import FailureCounter
from app.config import Settings
from app.db.models import Session, User, UserRole
from app.errors import ApiError

ADMIN_ROLES = frozenset({UserRole.SUPER_ADMIN, UserRole.SUPPORT, UserRole.FINANCE})


def _now() -> datetime:
    return datetime.now(UTC)


def _key(user: User) -> str:
    return f"admin:user:{user.id}"


def _same_ip(stored: object, ip: str | None) -> bool:
    if stored is None or ip is None:
        return stored is None and ip is None
    return ipaddress.ip_address(str(stored)) == ipaddress.ip_address(ip)


def _close(session: Session) -> None:
    session.admin_until = None
    session.admin_seen_at = None
    session.admin_ip = None


def is_open(settings: Settings, session: Session, ip: str | None, user_agent: str | None) -> bool:
    now = _now()
    return (
        session.admin_until is not None
        and session.admin_seen_at is not None
        and session.admin_until > now
        and session.admin_seen_at > now - timedelta(minutes=settings.admin_idle_minutes)
        and _same_ip(session.admin_ip, ip)
        and (user_agent or "")[:512] == (session.user_agent or "")
    )


def require_open(
    db: DbSession, settings: Settings, session: Session, ip: str | None, user_agent: str | None
) -> None:
    """Accès en cours, prolongé par l'activité ; sinon nouvelle connexion exigée."""
    if not is_open(settings, session, ip, user_agent):
        if session.admin_until is not None:
            _close(session)
            db.commit()
        raise ApiError(403, "admin.reauth_required")
    session.admin_seen_at = _now()
    db.commit()


def enter(
    db: DbSession,
    failures: FailureCounter,
    mailer: Mailer,
    settings: Settings,
    session: Session,
    *,
    password: str,
    code: str,
    ip: str | None,
    user_agent: str | None,
) -> datetime:
    user = session.user
    if user.role not in ADMIN_ROLES:
        audit.record(
            db,
            "admin.enter",
            "denied",
            actor_user_id=user.id,
            ip_address=ip,
            details={"reason": "not_admin"},
        )
        db.commit()
        raise ApiError(403, "authz.forbidden")
    if user.totp_enabled_at is None:
        raise ApiError(403, "authz.mfa_required")
    key = _key(user)
    if failures.count(key) >= settings.admin_max_failures:
        audit.record(
            db,
            "admin.enter",
            "denied",
            actor_user_id=user.id,
            ip_address=ip,
            details={"reason": "locked"},
        )
        db.commit()
        raise ApiError(
            429,
            "auth.too_many_attempts",
            headers={"Retry-After": str(settings.login_failure_window_seconds)},
        )

    # Les deux facteurs sont exigés ; la réponse ne dit jamais lequel était faux.
    valid = security.verify_password(user.password_hash, password) and mfa.accept_totp(
        settings, user, code
    )
    if not valid:
        count = failures.add(key, settings.login_failure_window_seconds)
        locked = count >= settings.admin_max_failures
        audit.record(
            db,
            "admin.enter",
            "failure",
            actor_user_id=user.id,
            ip_address=ip,
            details={"attempt": count, "locked": locked},
        )
        if locked:
            # Trop d'échecs : la session entière est fermée, il faut se reconnecter.
            session.revoked_at = _now()
            _close(session)
        db.commit()
        if locked:
            mailer.send(render("admin_locked", user.locale, user.email, first_name=user.first_name))
            raise ApiError(401, "admin.locked")
        raise ApiError(401, "admin.reauth_failed")

    failures.reset(key)
    now = _now()
    session.admin_until = now + timedelta(minutes=settings.admin_absolute_minutes)
    session.admin_seen_at = now
    session.admin_ip = ip
    audit.record(
        db,
        "admin.enter",
        "success",
        actor_user_id=user.id,
        ip_address=ip,
        target_type="session",
        target_id=str(session.id),
    )
    db.commit()
    mailer.send(render("admin_access", user.locale, user.email, first_name=user.first_name))
    return session.admin_until


def leave(db: DbSession, session: Session, ip: str | None) -> None:
    if session.admin_until is None:
        return
    _close(session)
    audit.record(
        db,
        "admin.leave",
        "success",
        actor_user_id=session.user_id,
        ip_address=ip,
        target_type="session",
        target_id=str(session.id),
    )
    db.commit()
