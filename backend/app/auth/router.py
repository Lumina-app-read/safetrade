import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from pydantic import BaseModel, EmailStr, Field

from app.auth import mfa, service
from app.auth.mailer import Mailer
from app.auth.rate_limit import FailureCounter
from app.authz import SESSION_COOKIE, CurrentSession
from app.config import Settings
from app.deps import AppSettings, Db, check_origin, client_ip, get_failures, get_mailer
from app.errors import ApiError

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(check_origin)])


class RegisterIn(BaseModel):
    email: EmailStr = Field(max_length=320)
    password: str = Field(max_length=256)
    first_name: str = Field(min_length=1, max_length=100)
    locale: Literal["fr", "en"] = "fr"
    accept_risk: bool = False


class VerifyIn(BaseModel):
    token: str = Field(min_length=20, max_length=100)


class LoginIn(BaseModel):
    email: EmailStr = Field(max_length=320)
    password: str = Field(max_length=256)
    remember: bool = False


class ForgotIn(BaseModel):
    email: EmailStr = Field(max_length=320)


class ResetIn(BaseModel):
    token: str = Field(min_length=20, max_length=100)
    password: str = Field(max_length=256)


class MfaLoginIn(BaseModel):
    challenge: str = Field(min_length=20, max_length=100)
    # Code TOTP à 6 chiffres ou code de secours « ABCD-EFGH ».
    code: str = Field(min_length=6, max_length=20)


class CodeIn(BaseModel):
    code: str = Field(min_length=6, max_length=20)


class MfaDisableIn(BaseModel):
    password: str = Field(max_length=256)
    code: str = Field(min_length=6, max_length=20)


def set_session_cookie(response: Response, settings: Settings, new: service.NewSession) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        new.token,
        max_age=int((new.expires_at - datetime.now(UTC)).total_seconds()),
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
        accept_risk=body.accept_risk,
        ip=client_ip(request),
    )
    # Réponse identique que l'adresse soit nouvelle ou déjà inscrite.
    return {"status": "verification_sent"}


@router.post("/verify-email")
def verify_email(body: VerifyIn, request: Request, db: Db) -> dict[str, str]:
    service.verify_email(db, token=body.token, ip=client_ip(request))
    return {"status": "verified"}


@router.post("/password/forgot", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(
    body: ForgotIn,
    request: Request,
    db: Db,
    settings: AppSettings,
    mailer: Annotated[Mailer, Depends(get_mailer)],
    failures: Annotated[FailureCounter, Depends(get_failures)],
) -> dict[str, str]:
    service.forgot_password(db, mailer, failures, settings, email=body.email, ip=client_ip(request))
    # Réponse identique que l'adresse existe ou non.
    return {"status": "reset_sent"}


@router.post("/password/reset")
def reset_password(
    body: ResetIn,
    request: Request,
    db: Db,
    mailer: Annotated[Mailer, Depends(get_mailer)],
    failures: Annotated[FailureCounter, Depends(get_failures)],
) -> dict[str, str]:
    service.reset_password(
        db, mailer, failures, token=body.token, password=body.password, ip=client_ip(request)
    )
    return {"status": "password_changed"}


@router.post("/login")
def login(
    body: LoginIn,
    request: Request,
    response: Response,
    db: Db,
    settings: AppSettings,
    failures: Annotated[FailureCounter, Depends(get_failures)],
) -> dict[str, object]:
    result = service.login(
        db,
        failures,
        settings,
        email=body.email,
        password=body.password,
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
        remember=body.remember,
    )
    if isinstance(result, service.MfaPending):
        # Aucune session tant que le second facteur n'est pas fourni (POST /auth/login/mfa).
        return {"mfa_required": True, "challenge": result.challenge}
    set_session_cookie(response, settings, result)
    return {"user": service.user_view(result.user)}


@router.post("/login/mfa")
def login_mfa(
    body: MfaLoginIn, request: Request, response: Response, db: Db, settings: AppSettings
) -> dict[str, object]:
    new = mfa.complete_login(
        db,
        settings,
        challenge=body.challenge,
        code=body.code,
        ip=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    set_session_cookie(response, settings, new)
    return {"user": service.user_view(new.user)}


@router.post("/mfa/setup")
def mfa_setup(
    request: Request, db: Db, settings: AppSettings, session: CurrentSession
) -> dict[str, str]:
    info = mfa.setup(db, settings, session.user, client_ip(request))
    # Le secret n'est montré que pendant la configuration ; il n'est plus jamais renvoyé ensuite.
    return {"secret": info.secret, "otpauth_uri": info.uri, "qr_svg": info.qr_svg}


@router.post("/mfa/enable")
def mfa_enable(
    body: CodeIn, request: Request, db: Db, settings: AppSettings, session: CurrentSession
) -> dict[str, list[str]]:
    return {"recovery_codes": mfa.enable(db, settings, session.user, body.code, client_ip(request))}


@router.post("/mfa/disable", status_code=status.HTTP_204_NO_CONTENT)
def mfa_disable(
    body: MfaDisableIn, request: Request, db: Db, settings: AppSettings, session: CurrentSession
) -> None:
    mfa.disable(db, settings, session.user, body.password, body.code, client_ip(request))


@router.get("/sessions")
def sessions(db: Db, session: CurrentSession) -> dict[str, object]:
    return {"sessions": mfa.list_sessions(db, session.user, session)}


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(
    session_id: uuid.UUID, request: Request, db: Db, session: CurrentSession
) -> None:
    if session_id == session.id:
        raise ApiError(400, "sessions.use_logout")
    mfa.revoke_session(db, session.user, session_id, client_ip(request))


@router.post("/sessions/revoke-others")
def revoke_others(request: Request, db: Db, session: CurrentSession) -> dict[str, int]:
    return {"revoked": mfa.revoke_other_sessions(db, session.user, session, client_ip(request))}


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
