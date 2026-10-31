"""Inscription, vérification d'e-mail, connexion et sessions (étape 1.5)."""

import hashlib
import ipaddress
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session as DbSession

from app import audit
from app.affiliate.service import attribute, find_code
from app.auth import security
from app.auth.mailer import Mailer, render
from app.auth.rate_limit import FailureCounter
from app.billing.service import grant_trial
from app.config import Settings
from app.db.models import (
    EmailVerificationToken,
    MfaChallenge,
    PasswordResetToken,
    Session,
    User,
    UserStatus,
)
from app.errors import ApiError


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize(email: str) -> str:
    return email.strip().lower()


def _email_digest(email: str) -> str:
    """Empreinte de l'e-mail pour les clés Redis : aucune donnée personnelle en clair."""
    return hashlib.sha256(_normalize(email).encode()).hexdigest()[:32]


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


def _within_mail_quota(failures: FailureCounter, settings: Settings, kind: str, email: str) -> bool:
    """Plafond d'envois par adresse : le site ne doit pas servir à bombarder une boîte."""
    key = f"{kind}:email:{_email_digest(email)}"
    if failures.count(key) >= settings.verification_max_per_hour:
        return False
    failures.add(key, 3600)
    return True


def _send_verification(db: DbSession, mailer: Mailer, settings: Settings, user: User) -> None:
    token = _issue_verification(db, user, settings)
    db.commit()
    mailer.send(
        render(
            "verify_email",
            user.locale,
            user.email,
            first_name=user.first_name,
            link=f"{settings.public_app_url}/{user.locale}/verify-email?token={token}",
            hours=settings.email_verification_hours,
        )
    )


def register(
    db: DbSession,
    mailer: Mailer,
    failures: FailureCounter,
    settings: Settings,
    *,
    email: str,
    password: str,
    first_name: str,
    locale: str,
    accept_risk: bool,
    ip: str | None,
    referral_code: str | None = None,
    device: bytes | None = None,
) -> None:
    """
    Crée un compte non vérifié et envoie le lien de vérification.
    Même réponse si l'adresse existe déjà (pas d'énumération des comptes) : le titulaire
    reçoit un avertissement, ou un nouveau lien si son compte n'est pas encore confirmé.
    """
    # Reconnaissance du risque exigée ici aussi : le navigateur ne décide jamais seul.
    if not accept_risk:
        raise ApiError(422, "auth.risk_not_accepted")
    problem = security.password_problem(password, email)
    if problem:
        raise ApiError(422, problem)
    # Contrôlé avant de chercher l'adresse : la réponse ne révèle pas si elle existe.
    referrer = find_code(db, referral_code) if referral_code else None

    existing = _find_user(db, email)
    if existing is not None:
        if _within_mail_quota(failures, settings, "verify", email):
            if existing.email_verified_at is None:
                _send_verification(db, mailer, settings, existing)
            else:
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
        risk_accepted_at=_now(),
    )
    db.add(user)
    db.flush()
    audit.record(
        db,
        "auth.register",
        "success",
        actor_user_id=user.id,
        target_type="user",
        target_id=str(user.id),
        ip_address=ip,
    )
    if referrer is not None:
        attribute(db, user, referrer, ip, device)
    _send_verification(db, mailer, settings, user)


def resend_verification(
    db: DbSession,
    mailer: Mailer,
    failures: FailureCounter,
    settings: Settings,
    *,
    email: str,
    ip: str | None,
) -> None:
    """Nouveau lien de confirmation. La réponse ne révèle jamais si l'adresse existe."""
    user = _find_user(db, email)
    if user is None or user.email_verified_at is not None:
        return
    if not _within_mail_quota(failures, settings, "verify", email):
        return
    audit.record(db, "auth.verification_resend", "success", actor_user_id=user.id, ip_address=ip)
    _send_verification(db, mailer, settings, user)


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
    grant_trial(db, user)
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
    remember: bool = False,
    device: bytes | None = None,
) -> "NewSession | MfaPending":
    email_key = f"login:email:{_email_digest(email)}"
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
                remember=remember,
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
    return open_session(db, settings, user, ip, user_agent, remember, device)


def open_session(
    db: DbSession,
    settings: Settings,
    user: User,
    ip: str | None,
    user_agent: str | None,
    remember: bool = False,
    device: bytes | None = None,
) -> NewSession:
    token = security.new_token()
    lifetime = (
        timedelta(days=settings.session_remember_days)
        if remember
        else timedelta(hours=settings.session_absolute_hours)
    )
    expires_at = _now() + lifetime
    db.add(
        Session(
            user_id=user.id,
            token_hash=security.token_hash(token),
            expires_at=expires_at,
            remember=remember,
            ip_address=ip,
            user_agent=(user_agent or "")[:512] or None,
            device_hash=device,
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
    idle = (
        timedelta(hours=settings.session_remember_idle_hours)
        if session is not None and session.remember
        else timedelta(minutes=settings.session_idle_minutes)
    )
    if (
        session is None
        or session.revoked_at is not None
        or session.expires_at <= now
        or session.last_seen_at <= now - idle
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


def forgot_password(
    db: DbSession,
    mailer: Mailer,
    failures: FailureCounter,
    settings: Settings,
    *,
    email: str,
    ip: str | None,
) -> None:
    """
    Envoie un lien de réinitialisation. Aucune réponse ne révèle si l'adresse existe,
    et le nombre d'envois par heure est limité en silence.
    """
    user = _find_user(db, email)
    key = f"reset:email:{_email_digest(email)}"
    if user is None or failures.count(key) >= settings.password_reset_max_per_hour:
        return
    failures.add(key, 3600)
    # Un seul lien valide à la fois : les précédents sont annulés.
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=_now())
    )
    token = security.new_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=security.token_hash(token),
            expires_at=_now() + timedelta(minutes=settings.password_reset_minutes),
        )
    )
    audit.record(db, "auth.password_forgot", "success", actor_user_id=user.id, ip_address=ip)
    db.commit()
    mailer.send(
        render(
            "reset_password",
            user.locale,
            user.email,
            first_name=user.first_name,
            link=f"{settings.public_app_url}/{user.locale}/reset-password?token={token}",
            minutes=settings.password_reset_minutes,
        )
    )


def reset_password(
    db: DbSession,
    mailer: Mailer,
    failures: FailureCounter,
    *,
    token: str,
    password: str,
    ip: str | None,
) -> None:
    """Change le mot de passe et ferme toutes les sessions : un intrus éventuel est expulsé."""
    record = db.scalars(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == security.token_hash(token))
        .with_for_update()
    ).first()
    if record is None or record.used_at is not None or record.expires_at <= _now():
        raise ApiError(400, "auth.reset_invalid")
    user = db.get(User, record.user_id)
    if user is None:  # impossible (clé étrangère en cascade), refus par prudence
        raise ApiError(400, "auth.reset_invalid")
    problem = security.password_problem(password, user.email)
    if problem:
        raise ApiError(422, problem)

    now = _now()
    user.password_hash = security.hash_password(password)
    record.used_at = now
    db.execute(
        update(Session)
        .where(Session.user_id == user.id, Session.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.execute(
        update(MfaChallenge)
        .where(MfaChallenge.user_id == user.id, MfaChallenge.used_at.is_(None))
        .values(used_at=now)
    )
    audit.record(db, "auth.password_reset", "success", actor_user_id=user.id, ip_address=ip)
    db.commit()
    failures.reset(f"login:email:{_email_digest(user.email)}")
    mailer.send(render("password_changed", user.locale, user.email, first_name=user.first_name))
