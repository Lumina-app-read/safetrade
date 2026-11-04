"""Outils partagés par les routes d'administration."""

import uuid

from sqlalchemy.orm import Session as DbSession

from app.billing import service as billing
from app.db.models import User
from app.errors import ApiError


def access_view(db: DbSession, user: User) -> dict[str, object]:
    access = billing.access_of(db, user)
    return {"status": access.status, "plan": access.plan, "ends_at": access.ends_at}


def target_user(db: DbSession, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(404, "admin.user_not_found")
    return user
