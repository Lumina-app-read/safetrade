"""
Réglages de l'administration (section 10) : messages, textes légaux, e-mails types et clés
des services externes. Réservé à la permission `settings.write` ; motif obligatoire, journal
d'audit à chaque changement, jamais la valeur d'une clé dans une réponse ou dans le journal.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import audit, email_templates, service_keys, site
from app.authz import Permission, require_permission
from app.db.models import LegalDocument, User
from app.deps import AppSettings, Db, client_ip
from app.errors import ApiError

router = APIRouter()

Writer = Annotated[User, Depends(require_permission(Permission.SETTINGS_WRITE))]
Reason = Field(min_length=5, max_length=300)


def _record(db: Db, request: Request, admin: User, action: str, details: dict[str, object]) -> None:
    audit.record(
        db, action, "success", actor_user_id=admin.id, ip_address=client_ip(request),
        details=details,
    )  # fmt: skip


# Messages du site.


class Announcement(BaseModel):
    enabled: bool
    tone: Literal["info", "warning"] = "info"
    fr: str = Field(min_length=1, max_length=280)
    en: str = Field(min_length=1, max_length=280)


class Warning(BaseModel):
    fr: str = Field(min_length=20, max_length=1200)
    en: str = Field(min_length=20, max_length=1200)


class MessagesIn(BaseModel):
    announcement: Announcement | None
    risk_warning: Warning | None
    note: str = Reason


@router.get("/messages")
def read_messages(db: Db, _: Writer) -> dict[str, object]:
    return {
        "announcement": site.read_json(db, site.ANNOUNCEMENT),
        "risk_warning": site.read_json(db, site.RISK_WARNING),
    }


@router.put("/messages")
def write_messages(body: MessagesIn, request: Request, db: Db, admin: Writer) -> dict[str, object]:
    announcement = body.announcement.model_dump() if body.announcement else None
    warning = body.risk_warning.model_dump() if body.risk_warning else None
    site.write_json(db, site.ANNOUNCEMENT, announcement, admin.id)
    # Sans texte propre, l'avertissement par défaut des fichiers de traduction s'affiche.
    site.write_json(db, site.RISK_WARNING, warning, admin.id)
    _record(
        db, request, admin, "admin.site.messages",
        {"announcement": announcement, "risk_warning": warning is not None, "note": body.note},
    )  # fmt: skip
    db.commit()
    return {"announcement": announcement, "risk_warning": warning}


# Textes légaux.


class LegalIn(BaseModel):
    kind: site.LegalKind
    locale: site.Locale
    title: str = Field(min_length=3, max_length=150)
    body: str = Field(min_length=50, max_length=60000)
    note: str = Reason


def _legal_view(db: Db) -> list[dict[str, object]]:
    rows = db.execute(
        select(LegalDocument, User.email)
        .outerjoin(User, User.id == LegalDocument.published_by)
        .order_by(LegalDocument.kind, LegalDocument.locale, LegalDocument.version.desc())
    ).all()
    current: dict[tuple[str, str], dict[str, str]] = {}
    versions: dict[tuple[str, str], list[dict[str, object]]] = {}
    for document, email in rows:
        key = (document.kind, document.locale)
        current.setdefault(key, {"title": document.title, "body": document.body})
        versions.setdefault(key, []).append(
            {"version": document.version, "published_at": document.published_at, "by": email}
        )
    return [
        {
            "kind": kind,
            "locale": locale,
            "current": current.get((kind, locale)),
            "versions": versions.get((kind, locale), []),
        }
        for kind in site.LEGAL_KINDS
        for locale in ("fr", "en")
    ]


@router.get("/legal")
def read_legal(db: Db, _: Writer) -> dict[str, object]:
    return {"documents": _legal_view(db)}


@router.post("/legal", status_code=201)
def publish_legal(body: LegalIn, request: Request, db: Db, admin: Writer) -> dict[str, object]:
    """Toujours une nouvelle version : ce qui a été affiché reste prouvable."""
    current = db.scalar(
        select(func.max(LegalDocument.version)).where(
            LegalDocument.kind == body.kind, LegalDocument.locale == body.locale
        )
    )
    version = (current or 0) + 1
    db.add(
        LegalDocument(
            kind=body.kind,
            locale=body.locale,
            version=version,
            title=body.title.strip(),
            body=body.body.strip(),
            published_by=admin.id,
        )
    )
    _record(
        db, request, admin, "admin.legal.publish",
        {"kind": body.kind, "locale": body.locale, "version": version, "note": body.note},
    )  # fmt: skip
    try:
        db.commit()
    except IntegrityError as exc:
        # Deux publications au même instant : l'une est refusée, rien n'est écrasé.
        db.rollback()
        raise ApiError(409, "settings.legal_conflict") from exc
    return {"documents": _legal_view(db)}


# E-mails types.


class EmailIn(BaseModel):
    subject: str = Field(max_length=150)
    title: str = Field(max_length=150)
    lines: list[str] = Field(max_length=email_templates.MAX_LINES)
    note: str = Field(max_length=400)
    action: str | None = Field(default=None, max_length=60)
    reason: str = Reason


class ResetIn(BaseModel):
    reason: str = Reason


@router.get("/emails")
def read_emails(db: Db, _: Writer) -> dict[str, object]:
    return {"templates": email_templates.view(db)}


@router.post("/emails/{template}/{lang}/preview")
def preview_email(template: str, lang: str, body: EmailIn, _: Writer) -> dict[str, str]:
    values = email_templates.validate(template, lang, body.model_dump(exclude={"reason"}))
    return email_templates.preview(template, lang, values)


@router.put("/emails/{template}/{lang}")
def write_email(
    template: str, lang: str, body: EmailIn, request: Request, db: Db, admin: Writer
) -> dict[str, object]:
    values = email_templates.validate(template, lang, body.model_dump(exclude={"reason"}))
    email_templates.write(db, template, lang, values, admin.id)
    _record(
        db, request, admin, "admin.email.update",
        {"template": template, "lang": lang, "note": body.reason},
    )  # fmt: skip
    db.commit()
    return {"templates": email_templates.view(db)}


@router.post("/emails/{template}/{lang}/reset")
def reset_email(
    template: str, lang: str, body: ResetIn, request: Request, db: Db, admin: Writer
) -> dict[str, object]:
    email_templates.validate_name(template, lang)
    email_templates.write(db, template, lang, None, admin.id)
    _record(
        db, request, admin, "admin.email.reset",
        {"template": template, "lang": lang, "note": body.reason},
    )  # fmt: skip
    db.commit()
    return {"templates": email_templates.view(db)}


# Clés des services externes.


class KeyIn(BaseModel):
    value: str = Field(min_length=1, max_length=300)
    note: str = Reason


class KeyRemoveIn(BaseModel):
    note: str = Reason


@router.get("/keys")
def read_keys(db: Db, settings: AppSettings, _: Writer) -> dict[str, object]:
    return service_keys.status(db, settings)


@router.put("/keys/{name}")
def write_key(
    name: str, body: KeyIn, request: Request, db: Db, settings: AppSettings, admin: Writer
) -> dict[str, object]:
    service_keys.write(db, settings, name, body.value, admin.id)
    # Le nom seul : jamais la valeur, même partielle.
    _record(db, request, admin, "admin.key.update", {"key": name, "note": body.note})
    db.commit()
    return service_keys.status(db, settings)


@router.post("/keys/{name}/remove")
def remove_key(
    name: str, body: KeyRemoveIn, request: Request, db: Db, settings: AppSettings, admin: Writer
) -> dict[str, object]:
    service_keys.write(db, settings, name, None, admin.id)
    _record(db, request, admin, "admin.key.remove", {"key": name, "note": body.note})
    db.commit()
    return service_keys.status(db, settings)
