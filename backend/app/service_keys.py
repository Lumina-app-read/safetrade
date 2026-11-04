"""
Clés des services externes réglées dans l'administration (section 10).

Chiffrées au repos en AES-256-GCM avec la clé du serveur, jamais renvoyées, jamais journalisées :
l'administration ne voit que « configurée » et la date. Une clé enregistrée ici passe avant la
variable d'environnement du même nom ; la retirer fait revenir la variable.

Seules les clés relues à chaque usage sont réglables ici. La connexion à Deriv et l'envoi
d'e-mails ouvrent leurs connexions au démarrage : leurs clés restent dans l'environnement.
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime

from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app import crypto
from app.config import Settings
from app.db.models import SiteSetting, User
from app.errors import ApiError

PREFIX = "service_key:"


@dataclass(frozen=True)
class KeySpec:
    name: str
    secret: bool
    max_length: int


EDITABLE: dict[str, KeySpec] = {
    spec.name: spec
    for spec in (
        KeySpec("chariow_api_key", True, 300),
        KeySpec("chariow_webhook_secret", True, 300),
        KeySpec("chariow_product_weekly", False, 80),
        KeySpec("chariow_product_monthly", False, 80),
        KeySpec("chariow_product_annual", False, 80),
    )
}
# Lues au démarrage : affichées, jamais modifiables ici.
FROM_ENVIRONMENT = ("deriv_app_id", "smtp_password", "encryption_key")


def _key(settings: Settings) -> bytes:
    if settings.encryption_key is None:
        raise ApiError(503, "settings.encryption_unavailable")
    return crypto.load_key(settings.encryption_key.get_secret_value())


def _context(name: str) -> str:
    return f"{PREFIX}{name}"


def _stored(db: DbSession) -> dict[str, SiteSetting]:
    rows = db.scalars(select(SiteSetting).where(SiteSetting.key.startswith(PREFIX)))
    return {row.key.removeprefix(PREFIX): row for row in rows}


def effective(db: DbSession, settings: Settings) -> Settings:
    """Réglages du serveur, avec les clés de l'administration à la place des variables."""
    rows = _stored(db)
    if not rows:
        return settings
    key = _key(settings)
    update: dict[str, object] = {}
    for name, row in rows.items():
        spec = EDITABLE.get(name)
        if spec is None:
            continue
        value = crypto.decrypt(key, row.value, _context(name))
        update[name] = SecretStr(value) if spec.secret else value
    return settings.model_copy(update=update)


def fingerprint(db: DbSession) -> str | None:
    """Empreinte des valeurs enregistrées : change à chaque modification, ne révèle rien."""
    rows = _stored(db)
    if not rows:
        return None
    digest = hashlib.sha256()
    for name in sorted(rows):
        digest.update(f"{name}={rows[name].value};".encode())
    return digest.hexdigest()


def status(db: DbSession, settings: Settings) -> dict[str, object]:
    rows = _stored(db)
    emails = {
        row.updated_by: db.get_one(User, row.updated_by).email
        for row in rows.values()
        if row.updated_by is not None
    }
    editable = []
    for name, spec in EDITABLE.items():
        row = rows.get(name)
        env = getattr(settings, name)
        value = None
        if row is not None and not spec.secret:
            value = crypto.decrypt(_key(settings), row.value, _context(name))
        elif row is None and env and not spec.secret:
            value = str(env)
        editable.append(
            {
                "name": name,
                "secret": spec.secret,
                "source": "admin" if row else ("environment" if env else None),
                # Jamais la valeur d'un secret ; un identifiant de produit n'en est pas un.
                "value": value,
                "updated_at": row.updated_at if row else None,
                "updated_by": emails.get(row.updated_by) if row and row.updated_by else None,
            }
        )
    return {
        "editable": editable,
        "environment": [
            {"name": name, "configured": bool(getattr(settings, name, None))}
            for name in FROM_ENVIRONMENT
        ],
        "encryption": settings.encryption_key is not None,
    }


def write(
    db: DbSession, settings: Settings, name: str, value: str | None, by: uuid.UUID
) -> datetime | None:
    spec = EDITABLE.get(name)
    if spec is None:
        raise ApiError(404, "settings.key_not_found")
    row = db.get(SiteSetting, _context(name))
    if value is None:
        if row is not None:
            db.delete(row)
        return None
    clean = value.strip()
    if not clean or len(clean) > spec.max_length or any(c.isspace() for c in clean):
        raise ApiError(422, "settings.key_invalid", fields=["value"])
    sealed = crypto.encrypt(_key(settings), clean, _context(name))
    if row is None:
        db.add(SiteSetting(key=_context(name), value=sealed, updated_by=by))
    else:
        row.value, row.updated_by = sealed, by
    return None
