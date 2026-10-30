"""Écriture dans le journal d'audit (table en ajout seul)."""

import uuid
from typing import Any, Literal

from sqlalchemy.orm import Session as DbSession

from app.db.models import AuditLog


def record(
    db: DbSession,
    action: str,
    result: Literal["success", "failure", "denied"],
    *,
    actor_user_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    ip_address: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Ajoute une entrée. Ne jamais y mettre de mot de passe, jeton ou token Deriv."""
    db.add(
        AuditLog(
            action=action,
            result=result,
            actor_user_id=actor_user_id,
            target_type=target_type,
            target_id=target_id,
            ip_address=ip_address,
            details=details or {},
        )
    )
