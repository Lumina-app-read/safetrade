from typing import Annotated, Literal

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from pydantic import BaseModel, EmailStr, Field

from app.auth import service
from app.auth.mailer import Mailer
from app.auth.rate_limit import FailureCounter
from app.config import Settings
from app.deps import AppSettings, Db, check_origin, client_ip, get_failures, get_mailer

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(check_origin)])

SESSION_COOKIE = "st_session"


class RegisterIn(BaseModel):
    email: EmailStr = Field(max_length=320)
    password: str = Field(max_length=256)
    first_name: str = Field(min_length=1, max_length=100)
    locale: Literal["fr", "en"] = "fr"


class VerifyIn(BaseModel):
    token: str = Field(min_length=20, max_length=100)


class LoginIn(BaseModel):
    email: EmailStr = Field(max_length=320)
    password: str = Field(max_length=256)


def set_session_cookie(response: Response, settings: Settings, token: str, max_age: int) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/register", status_code=status.HTTP_202_ACCEPTED)
def register(
    body: RegisterIn,
    request: Request,
    db: Db,
    settings: AppSettings,
    mailer: Annotated[Mailer, Depends(get_mailer)],
) -> dict[str, str]:
    service.register(
        db,
        mailer,
        settings,
        email=body.email,
        password=body.password,
        first_name=body.first_name,
        locale=body.locale,
        ip=client_ip(request),
    )
    # Réponse identique que l'adresse soit nouvelle ou déjà inscrite.
    return {"status": "verification_sent"}


@router.post("/verify-email")
def verify_email(body: VerifyIn, request: Request, db: Db) -> dict[str, str]:
    service.verify_email(db, token=body.token, ip=client_ip(request))
    return {"status": "verified"}


@router.post("/login")
def login(
    body: LoginIn,
    request: Request,
    response: Response,
    db: Db,
    settings: AppSettings,
    failures: Annotated[FailureCounter, Depends(get_failures)],
) -> dict[str, object]:
    new = service.login(
        db,
        failures,
        settings,
        email=body.email,
        password=body.password,
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    set_session_cookie(response, settings, new.token, settings.session_absolute_hours * 3600)
    return {"user": service.user_view(new.user)}


@router.get("/me")
def me(
    db: Db, settings: AppSettings, token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None
) -> dict[str, object]:
    user, _ = service.authenticate(db, settings, token)
    return {"user": service.user_view(user)}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Db,
    settings: AppSettings,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> None:
    _, session = service.authenticate(db, settings, token)
    service.logout(db, session, client_ip(request))
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )
