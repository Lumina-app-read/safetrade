"""Réglages publics du site : ici, le lien partenaire Deriv, modifiable dans l'administration."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.db.models import SiteSetting
from app.deps import Db, check_origin

DERIV_SIGNUP_URL = "deriv_signup_url"

router = APIRouter(prefix="/site", tags=["site"], dependencies=[Depends(check_origin)])


def deriv_signup_url(db: DbSession) -> str | None:
    row = db.get(SiteSetting, DERIV_SIGNUP_URL)
    return row.value if row else None


@router.get("/config")
def config(db: Db) -> dict[str, str | None]:
    """Public : la page d'accueil et l'inscription affichent ce lien sans session."""
    return {"deriv_signup_url": deriv_signup_url(db)}
