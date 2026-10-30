"""Inscription, vérification d'e-mail, connexion et sessions (étape 1.5)."""

import hashlib
import ipaddress
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app import audit
from app.auth import security
from app.auth.mailer import Mailer, render
from app.auth.rate_limit import FailureCounter
from app.config import Settings
from app.db.models import EmailVerificationToken, MfaChallenge, Session, User, UserStatus
from app.errors import ApiError


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize(email: str) -> str:
    return email.strip().lower()


def _find_user(db: DbSession, email: str) -> User | None:
    return db.scalars(select(User).where(func.lower(User.email) == _normalize(email))).first()


def _issue_verification(db: DbSession, user: User, settings: Settings) -> str:
    token = security.new_token()
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=security.token_hash(token),
            expires_at=_now() + timedelta(hours=settings.email_verification_hours),
        )
    )
    return token


def register(
    db: DbSession,
    mailer: Mailer,
    settings: Settings,
    *,
    email: str,
    password: str,
    first_name: str,
    locale: str,
    ip: str | None,
) -> None:
    """
    Crée un compte non vérifié et envoie le lien de vérification.
    Même réponse si l'adresse existe déjà (pas d'énumération des comptes) :
    le titulaire reçoit alors un e-mail d'avertissement.
    """
    problem = security.password_problem(password, email)
    if problem:
        raise ApiError(422, problem)

    existing = _find_user(db, email)
    if existing is not None:
        mailer.send(
            render(
                "already_registered",
                existing.locale,
                existing.email,
                first_name=existing.first_name,
                link=f"{settings.public_app_url}/{existing.locale}/login",
            )
        )
        audit.record(
            db,
            "auth.register",
            "denied",
            target_type="user",
            target_id=str(existing.id),
            ip_address=ip,
            details={"reason": "email_exists"},
        )
        db.commit()
        return

    user = User(
        email=email.strip(),
        password_hash=security.hash_password(password),
        first_name=first_name.strip(),
        locale=locale,
    )
    db.add(user)
    db.flush()
    token = _issue_verification(db, user, settings)
    audit.record(
        db,
        "auth.register",
        "success",
        actor_user_id=user.id,
        target_type="user",
        target_id=str(user.id),
        ip_address=ip,
    )
    db.commit()
    mailer.send(
        render(
            "verify_email",
            locale,
            user.email,
            first_name=user.first_name,
            link=f"{settings.public_app_url}/{locale}/verify-email?token={token}",
            hours=settings.email_verification_hours,
        )
    )


def verify_email(db: DbSession, *, token: str, ip: str | None) -> None:
    record = db.scalars(
        select(EmailVerificationToken)
        .where(EmailVerificationToken.token_hash == security.token_hash(token))
        .with_for_update()
    ).first()
    if record is None or record.used_at is not None or record.expires_at <= _now():
        raise ApiError(400, "auth.verification_invalid")
    user = db.get(User, record.user_id)
    if user is None:  # impossible (clé étrangère en cascade), refus par prudence
        raise ApiError(400, "auth.verification_invalid")
    record.used_at = _now()
    user.email_verified_at = user.email_verified_at or _now()
    audit.record(
        db,
        "auth.verify_email",
        "success",
        actor_user_id=user.id,
        target_type="user",
        target_id=str(user.id),
        ip_address=ip,
    )
    db.commit()


@dataclass(frozen=True)
class NewSession:
    token: str
    user: User
    expires_at: datetime


@dataclass(frozen=True)
class MfaPending:
    """Mot de passe vérifié ; jeton de défi à présenter avec le code de double authentification."""

    challenge: str


def login(
    db: DbSession,
    failures: FailureCounter,
    settings: Settings,
    *,
    email: str,
    password: str,
    ip: str | None,
    user_agent: str | None,
) -> "NewSession | MfaPending":
    # Empreinte de l'e-mail dans les clés Redis : aucune donnée personnelle en clair.
    email_digest = hashlib.sha256(_normalize(email).encode()).hexdigest()[:32]
    email_key = f"login:email:{email_digest}"
    # Compteur par adresse uniquement pour une adresse publique : une adresse interne
    # (conteneur, proxy) est partagée par tous les visiteurs, la compter permettrait à
    # quiconque de bloquer la connexion de tout le monde (docs/decisions/q16).
    ip_key = f"login:ip:{ip}" if ip and ipaddress.ip_address(ip).is_global else None
    if failures.count(email_key) >= settings.login_max_failures_per_email or (
        ip_key and failures.count(ip_key) >= settings.login_max_failures_per_ip
    ):
        audit.record(db, "auth.login", "denied", ip_address=ip, details={"reason": "rate_limited"})
        db.commit()
        raise ApiError(
            429,
            "auth.too_many_attempts",
            headers={"Retry-After": str(settings.login_failure_window_seconds)},
        )

    user = _find_user(db, email)
    # Vérification toujours effectuée, même sans compte : durée de réponse identique.
    valid = security.verify_password(user.password_hash if user else None, password)
    if user is None or not valid:
        window = settings.login_failure_window_seconds
        failures.add(email_key, window)
        if ip_key:
            failures.add(ip_key, window)
        audit.record(
            db,
            "auth.login",
            "failure",
            actor_user_id=user.id if user else None,
            ip_address=ip,
            details={"reason": "invalid_credentials"},
        )
        db.commit()
        raise ApiError(401, "auth.invalid_credentials")

    if user.status == UserStatus.SUSPENDED:
        audit.record(
            db,
            "auth.login",
            "denied",
            actor_user_id=user.id,
            ip_address=ip,
            details={"reason": "suspended"},
        )
        db.commit()
        raise ApiError(403, "auth.account_suspended")
    if user.email_verified_at is None:
        raise ApiError(403, "auth.email_not_verified")

    failures.reset(email_key)
    if security.needs_rehash(user.password_hash):
        user.password_hash = security.hash_password(password)

    if user.totp_enabled_at is not None:
        # Mot de passe correct, mais la session n'est ouverte qu'après le second facteur.
        challenge = security.new_token()
        db.add(
            MfaChallenge(
                user_id=user.id,
                token_hash=security.token_hash(challenge),
                expires_at=_now() + timedelta(minutes=settings.mfa_challenge_minutes),
            )
        )
        audit.record(
            db,
            "auth.login",
            "success",
            actor_user_id=user.id,
            ip_address=ip,
            details={"step": "password", "mfa": "required"},
        )
        db.commit()
        return MfaPending(challenge=challenge)

    audit.record(db, "auth.login", "success", actor_user_id=user.id, ip_address=ip)
    return open_session(db, settings, user, ip, user_agent)


def open_session(
    db: DbSession, settings: Settings, user: User, ip: str | None, user_agent: str | None
) -> NewSession:
    token = security.new_token()
    expires_at = _now() + timedelta(hours=settings.session_absolute_hours)
    db.add(
        Session(
            user_id=user.id,
            token_hash=security.token_hash(token),
            expires_at=expires_at,
            ip_address=ip,
            user_agent=(user_agent or "")[:512] or None,
        )
    )
    db.commit()
    return NewSession(token=token, user=user, expires_at=expires_at)


def authenticate(db: DbSession, settings: Settings, token: str | None) -> tuple[User, Session]:
    """Session valide pour ce jeton, renouvelée à chaque appel (expiration glissante)."""
    if not token:
        raise ApiError(401, "auth.not_authenticated")
    session = db.scalars(
        select(Session).where(Session.token_hash == security.token_hash(token))
    ).first()
    now = _now()
    if (
        session is None
        or session.revoked_at is not None
        or session.expires_at <= now
        or session.last_seen_at <= now - timedelta(minutes=settings.session_idle_minutes)
    ):
        raise ApiError(401, "auth.not_authenticated")
    user = session.user
    if user.status == UserStatus.SUSPENDED:
        raise ApiError(403, "auth.account_suspended")
    session.last_seen_at = now
    db.commit()
    return user, session


def logout(db: DbSession, session: Session, ip: str | None) -> None:
    session.revoked_at = _now()
    audit.record(
        db,
        "auth.logout",
        "success",
        actor_user_id=session.user_id,
        ip_address=ip,
        target_type="session",
        target_id=str(session.id),
    )
    db.commit()


def user_view(user: User) -> dict[str, str | uuid.UUID | bool]:
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "role": user.role.value,
        "locale": user.locale,
        "theme": user.theme,
        "email_verified": user.email_verified_at is not None,
        "mfa_enabled": user.totp_enabled_at is not None,
    }
