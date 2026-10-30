"""Dépendances partagées : base de données, services et contrôles de requête."""

import ipaddress
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from app.auth.mailer import Mailer
from app.auth.rate_limit import FailureCounter
from app.config import Settings
from app.errors import ApiError


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_db(request: Request) -> Iterator[DbSession]:
    factory: sessionmaker[DbSession] = request.app.state.session_factory
    with factory() as db:
        yield db


def get_mailer(request: Request) -> Mailer:
    mailer: Mailer = request.app.state.mailer
    return mailer


def get_failures(request: Request) -> FailureCounter:
    failures: FailureCounter = request.app.state.failures
    return failures


def client_ip(request: Request) -> str | None:
    """Adresse IP du client, ou None si elle n'est pas une adresse valide."""
    # Derrière le reverse proxy, uvicorn est lancé avec --proxy-headers (adresse réelle).
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


def check_origin(
    request: Request, settings: Annotated[Settings, Depends(get_settings_dep)]
) -> None:
    """
    Anti-CSRF pour les requêtes qui modifient l'état : le navigateur envoie toujours
    l'en-tête Origin, qui doit être une origine de l'application. En plus du cookie SameSite.
    """
    origin = request.headers.get("origin")
    if origin is not None and origin not in settings.allowed_origins:
        raise ApiError(403, "auth.origin_forbidden")


Db = Annotated[DbSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings_dep)]
