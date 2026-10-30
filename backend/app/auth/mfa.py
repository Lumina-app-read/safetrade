"""Double authentification TOTP, codes de secours et gestion des sessions (étape 1.6)."""

import io
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import segno
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session as DbSession

from app import audit, crypto
from app.auth import security, totp
from app.auth.service import NewSession, open_session
from app.config import Settings
from app.db.models import MfaChallenge, RecoveryCode, Session, User
from app.errors import ApiError


def _now() -> datetime:
    return datetime.now(UTC)


def _key(settings: Settings) -> bytes:
    if settings.encryption_key is None:
        raise RuntimeError("SAFETRADE_ENCRYPTION_KEY n'est pas défini.")
    return crypto.load_key(settings.encryption_key.get_secret_value())


def _context(user: User) -> str:
    return f"totp:{user.id}"


def _secret(settings: Settings, user: User) -> str:
    if user.totp_secret_encrypted is None:
        raise ApiError(409, "mfa.not_configured")
    return crypto.decrypt(_key(settings), user.totp_secret_encrypted, _context(user))


def _accept_totp(settings: Settings, user: User, code: str) -> bool:
    """Code TOTP valide et jamais utilisé (anti-rejeu par pas de temps)."""
    step = totp.match_step(_secret(settings, user), code)
    if step is None or (user.totp_last_step is not None and step <= user.totp_last_step):
        return False
    user.totp_last_step = step
    return True


def _accept_recovery(db: DbSession, user: User, code: str) -> bool:
    record = db.scalars(
        select(RecoveryCode).where(
            RecoveryCode.user_id == user.id,
            RecoveryCode.code_hash == totp.recovery_hash(code),
            RecoveryCode.used_at.is_(None),
        )
    ).first()
    if record is None:
        return False
    record.used_at = _now()
    return True


def _verify_second_factor(db: DbSession, settings: Settings, user: User, code: str) -> str | None:
    """Méthode acceptée (« totp » ou « recovery »), ou None."""
    if _accept_totp(settings, user, code):
        return "totp"
    if _accept_recovery(db, user, code):
        return "recovery"
    return None


@dataclass(frozen=True)
class SetupInfo:
    secret: str
    uri: str
    qr_svg: str


def setup(db: DbSession, settings: Settings, user: User, ip: str | None) -> SetupInfo:
    """Génère un nouveau secret (non actif tant qu'un code n'a pas été confirmé)."""
    if user.totp_enabled_at is not None:
        raise ApiError(409, "mfa.already_enabled")
    secret = totp.new_secret()
    user.totp_secret_encrypted = crypto.encrypt(_key(settings), secret, _context(user))
    user.totp_last_step = None
    audit.record(db, "mfa.setup", "success", actor_user_id=user.id, ip_address=ip)
    db.commit()
    uri = totp.provisioning_uri(secret, user.email)
    buffer = io.BytesIO()
    segno.make(uri, error="m").save(buffer, kind="svg", scale=6, border=2, xmldecl=False)
    return SetupInfo(secret=secret, uri=uri, qr_svg=buffer.getvalue().decode())


def enable(db: DbSession, settings: Settings, user: User, code: str, ip: str | None) -> list[str]:
    """Active la double authentification et renvoie les codes de secours (affichés une fois)."""
    if user.totp_enabled_at is not None:
        raise ApiError(409, "mfa.already_enabled")
    if not _accept_totp(settings, user, code):
        audit.record(db, "mfa.enable", "failure", actor_user_id=user.id, ip_address=ip)
        db.commit()
        raise ApiError(400, "mfa.invalid_code")
    user.totp_enabled_at = _now()
    codes = totp.recovery_codes()
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    db.add_all(RecoveryCode(user_id=user.id, code_hash=totp.recovery_hash(c)) for c in codes)
    audit.record(db, "mfa.enable", "success", actor_user_id=user.id, ip_address=ip)
    db.commit()
    return codes


def disable(
    db: DbSession, settings: Settings, user: User, password: str, code: str, ip: str | None
) -> None:
    """Désactivation : mot de passe et second facteur exigés."""
    if user.totp_enabled_at is None:
        raise ApiError(409, "mfa.not_configured")
    if not security.verify_password(user.password_hash, password):
        audit.record(db, "mfa.disable", "failure", actor_user_id=user.id, ip_address=ip)
        db.commit()
        raise ApiError(400, "auth.invalid_credentials")
    if _verify_second_factor(db, settings, user, code) is None:
        audit.record(db, "mfa.disable", "failure", actor_user_id=user.id, ip_address=ip)
        db.commit()
        raise ApiError(400, "mfa.invalid_code")
    user.totp_enabled_at = None
    user.totp_secret_encrypted = None
    user.totp_last_step = None
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    audit.record(db, "mfa.disable", "success", actor_user_id=user.id, ip_address=ip)
    db.commit()


def complete_login(
    db: DbSession,
    settings: Settings,
    *,
    challenge: str,
    code: str,
    ip: str | None,
    user_agent: str | None,
) -> NewSession:
    """Second temps de la connexion : code TOTP ou code de secours contre une session."""
    record = db.scalars(
        select(MfaChallenge)
        .where(MfaChallenge.token_hash == security.token_hash(challenge))
        .with_for_update()
    ).first()
    if (
        record is None
        or record.used_at is not None
        or record.expires_at <= _now()
        or record.attempts >= settings.mfa_max_attempts
    ):
        raise ApiError(401, "mfa.challenge_invalid")
    user = db.get(User, record.user_id)
    if user is None or user.totp_enabled_at is None:
        raise ApiError(401, "mfa.challenge_invalid")

    method = _verify_second_factor(db, settings, user, code)
    if method is None:
        record.attempts += 1
        audit.record(db, "auth.login_mfa", "failure", actor_user_id=user.id, ip_address=ip)
        db.commit()
        raise ApiError(400, "mfa.invalid_code")
    record.used_at = _now()
    audit.record(
        db,
        "auth.login_mfa",
        "success",
        actor_user_id=user.id,
        ip_address=ip,
        details={"method": method},
    )
    return open_session(db, settings, user, ip, user_agent)


def list_sessions(db: DbSession, user: User, current: Session) -> list[dict[str, object]]:
    rows = db.scalars(
        select(Session)
        .where(
            Session.user_id == user.id, Session.revoked_at.is_(None), Session.expires_at > _now()
        )
        .order_by(Session.last_seen_at.desc())
    ).all()
    return [
        {
            "id": s.id,
            "created_at": s.created_at,
            "last_seen_at": s.last_seen_at,
            "ip_address": s.ip_address,
            "user_agent": s.user_agent,
            "current": s.id == current.id,
        }
        for s in rows
    ]


def revoke_session(db: DbSession, user: User, session_id: uuid.UUID, ip: str | None) -> None:
    """Déconnexion à distance d'une session du même utilisateur (jamais celle d'un autre)."""
    result = db.execute(
        update(Session)
        .where(Session.id == session_id, Session.user_id == user.id, Session.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise ApiError(404, "sessions.not_found")
    audit.record(
        db,
        "auth.session_revoke",
        "success",
        actor_user_id=user.id,
        ip_address=ip,
        target_type="session",
        target_id=str(session_id),
    )
    db.commit()


def revoke_other_sessions(db: DbSession, user: User, current: Session, ip: str | None) -> int:
    result = db.execute(
        update(Session)
        .where(Session.user_id == user.id, Session.id != current.id, Session.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
    count = int(result.rowcount)  # type: ignore[attr-defined]
    audit.record(
        db,
        "auth.session_revoke_others",
        "success",
        actor_user_id=user.id,
        ip_address=ip,
        details={"count": count},
    )
    db.commit()
    return count
