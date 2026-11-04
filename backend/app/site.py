"""
Réglages publics du site, modifiables dans l'administration : lien partenaire Deriv, bandeau
d'annonce, avertissement de risque et textes légaux.
"""

import json
import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.db.models import LegalDocument, SiteSetting
from app.deps import Db, check_origin
from app.errors import ApiError

DERIV_SIGNUP_URL = "deriv_signup_url"
ANNOUNCEMENT = "announcement"
RISK_WARNING = "risk_warning"
LEGAL_KINDS = ("legal_notice", "terms", "privacy", "risk")

LegalKind = Literal["legal_notice", "terms", "privacy", "risk"]
Locale = Literal["fr", "en"]

router = APIRouter(prefix="/site", tags=["site"], dependencies=[Depends(check_origin)])


def deriv_signup_url(db: DbSession) -> str | None:
    row = db.get(SiteSetting, DERIV_SIGNUP_URL)
    return row.value if row else None


def read_json(db: DbSession, key: str) -> dict[str, Any] | None:
    row = db.get(SiteSetting, key)
    value: dict[str, Any] | None = json.loads(row.value) if row else None
    return value


def write_json(db: DbSession, key: str, value: dict[str, Any] | None, by: uuid.UUID) -> None:
    row = db.get(SiteSetting, key)
    if value is None:
        if row is not None:
            db.delete(row)
        return
    encoded = json.dumps(value, ensure_ascii=False)
    if row is None:
        db.add(SiteSetting(key=key, value=encoded, updated_by=by))
    else:
        row.value, row.updated_by = encoded, by


def latest_legal(db: DbSession, kind: str, locale: str) -> LegalDocument | None:
    return db.scalars(
        select(LegalDocument)
        .where(LegalDocument.kind == kind, LegalDocument.locale == locale)
        .order_by(LegalDocument.version.desc())
    ).first()


def published_kinds(db: DbSession) -> list[str]:
    return sorted(set(db.scalars(select(LegalDocument.kind).distinct())))


@router.get("/config")
def config(db: Db) -> dict[str, object]:
    """Public : la page d'accueil, l'inscription et l'espace client lisent ces réglages."""
    announcement = read_json(db, ANNOUNCEMENT)
    return {
        "deriv_signup_url": deriv_signup_url(db),
        "announcement": announcement if announcement and announcement.get("enabled") else None,
        "risk_warning": read_json(db, RISK_WARNING),
        "legal": published_kinds(db),
    }


@router.get("/legal")
def legal(
    db: Db,
    kind: Annotated[LegalKind, Query()],
    locale: Annotated[Locale, Query()] = "fr",
) -> dict[str, object]:
    """Version en vigueur ; sans version dans cette langue, l'autre langue, sinon un refus."""
    document = latest_legal(db, kind, locale) or latest_legal(
        db, kind, "en" if locale == "fr" else "fr"
    )
    if document is None:
        raise ApiError(404, "legal.not_published")
    return {
        "kind": document.kind,
        "locale": document.locale,
        "version": document.version,
        "title": document.title,
        "body": document.body,
        "published_at": document.published_at,
    }
