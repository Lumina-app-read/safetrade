"""Connexion du compte Deriv d'un client : jeton chiffré, compte de travail (étape 2.3)."""

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from app import audit, crypto
from app.broker.base import AccountKind
from app.broker.deriv_rest import DerivAccount
from app.config import Settings
from app.db.models import DerivConnectionRecord, User
from app.errors import ApiError


def _key(settings: Settings) -> bytes:
    if settings.encryption_key is None:
        raise RuntimeError("SAFETRADE_ENCRYPTION_KEY n'est pas défini.")
    return crypto.load_key(settings.encryption_key.get_secret_value())


def _context(user_id: object) -> str:
    return f"deriv:{user_id}"


def find(db: DbSession, user: User) -> DerivConnectionRecord | None:
    return db.scalars(
        select(DerivConnectionRecord).where(DerivConnectionRecord.user_id == user.id)
    ).first()


def read_token(settings: Settings, record: DerivConnectionRecord) -> str:
    """Jeton en clair, uniquement pour un appel à Deriv. Jamais renvoyé ni journalisé."""
    return crypto.decrypt(_key(settings), record.token_encrypted, _context(record.user_id))


def default_account(accounts: list[DerivAccount]) -> DerivAccount | None:
    """Le mode démo est présélectionné ; jamais le compte réel par défaut."""
    return next((a for a in accounts if a.kind is AccountKind.DEMO), None)


def save(
    db: DbSession,
    settings: Settings,
    user: User,
    *,
    token: str,
    auth_method: str,
    accounts: list[DerivAccount],
    expires_at: datetime | None,
    ip: str | None,
) -> DerivConnectionRecord:
    db.execute(delete(DerivConnectionRecord).where(DerivConnectionRecord.user_id == user.id))
    account = default_account(accounts)
    record = DerivConnectionRecord(
        user_id=user.id,
        auth_method=auth_method,
        token_encrypted=crypto.encrypt(_key(settings), token, _context(user.id)),
        token_expires_at=expires_at,
        account_id=account.account_id if account else None,
        account_kind=account.kind.value if account else None,
        currency=account.currency if account else None,
    )
    db.add(record)
    audit.record(
        db,
        "deriv.connect",
        "success",
        actor_user_id=user.id,
        ip_address=ip,
        details={"auth_method": auth_method, "accounts": len(accounts)},
    )
    db.commit()
    return record


def select_account(
    db: DbSession,
    settings: Settings,
    user: User,
    record: DerivConnectionRecord,
    accounts: list[DerivAccount],
    account_id: str,
    ip: str | None,
) -> DerivConnectionRecord:
    account = next((a for a in accounts if a.account_id == account_id), None)
    if account is None:
        raise ApiError(404, "deriv.account_unknown")
    if account.kind is AccountKind.REAL and not settings.real_account_enabled:
        audit.record(
            db,
            "deriv.select_account",
            "denied",
            actor_user_id=user.id,
            ip_address=ip,
            details={"reason": "real_disabled"},
        )
        db.commit()
        raise ApiError(403, "deriv.real_disabled")
    record.account_id = account.account_id
    record.account_kind = account.kind.value
    record.currency = account.currency
    record.updated_at = datetime.now(UTC)
    audit.record(
        db,
        "deriv.select_account",
        "success",
        actor_user_id=user.id,
        ip_address=ip,
        details={"kind": account.kind.value},
    )
    db.commit()
    return record


def disconnect(db: DbSession, user: User, ip: str | None) -> None:
    """Efface le jeton de SafeTrade. La révocation chez Deriv reste à faire par le client."""
    result = db.execute(
        delete(DerivConnectionRecord).where(DerivConnectionRecord.user_id == user.id)
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise ApiError(404, "deriv.not_connected")
    audit.record(db, "deriv.disconnect", "success", actor_user_id=user.id, ip_address=ip)
    db.commit()
