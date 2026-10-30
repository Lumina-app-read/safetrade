"""Routes de connexion Deriv. Le jeton entre une fois et ne ressort jamais."""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app import audit
from app.auth.rate_limit import FailureCounter
from app.authz import CurrentSession
from app.broker.base import AccountKind
from app.broker.deriv_rest import DerivAccount, DerivAuthError, DerivRest, DerivUnavailableError
from app.db.models import DerivConnectionRecord, User
from app.deps import AppSettings, Db, check_origin, client_ip, get_failures
from app.deriv import service
from app.errors import ApiError

router = APIRouter(prefix="/deriv", tags=["deriv"], dependencies=[Depends(check_origin)])

MAX_INVALID_TOKENS = 5
INVALID_TOKEN_WINDOW = 15 * 60


class ConnectIn(BaseModel):
    token: str = Field(min_length=20, max_length=512, pattern=r"^\S+$")


class SelectIn(BaseModel):
    account_id: str = Field(min_length=1, max_length=50)


def get_deriv(request: Request) -> DerivRest:
    rest: DerivRest | None = request.app.state.deriv
    if rest is None:
        raise ApiError(503, "deriv.unavailable")
    return rest


Deriv = Annotated[DerivRest, Depends(get_deriv)]


def account_view(account: DerivAccount, settings_real_enabled: bool) -> dict[str, object]:
    view = {**asdict(account), "kind": account.kind.value}
    view["selectable"] = account.kind is AccountKind.DEMO or settings_real_enabled
    return view


def connection_view(
    record: DerivConnectionRecord, accounts: list[DerivAccount] | None, real_enabled: bool
) -> dict[str, object]:
    # Liste blanche de champs : le jeton chiffré lui-même ne sort jamais.
    return {
        "connected": True,
        "auth_method": record.auth_method,
        "token_valid": accounts is not None,
        "token_expires_at": record.token_expires_at,
        "selected": {
            "account_id": record.account_id,
            "kind": record.account_kind,
            "currency": record.currency,
        },
        "accounts": [account_view(a, real_enabled) for a in accounts or []],
    }


async def fetch_accounts(rest: DerivRest, token: str, user: User) -> list[DerivAccount]:
    try:
        return await rest.list_accounts(token, str(user.id))
    except DerivUnavailableError:
        raise ApiError(503, "deriv.unavailable") from None


@router.post("/connect")
async def connect(
    body: ConnectIn,
    request: Request,
    db: Db,
    settings: AppSettings,
    session: CurrentSession,
    rest: Deriv,
    failures: Annotated[FailureCounter, Depends(get_failures)],
) -> dict[str, object]:
    user = session.user
    ip = client_ip(request)
    key = f"deriv:connect:{user.id}"
    if failures.count(key) >= MAX_INVALID_TOKENS:
        raise ApiError(
            429, "auth.too_many_attempts", headers={"Retry-After": str(INVALID_TOKEN_WINDOW)}
        )
    try:
        accounts = await fetch_accounts(rest, body.token, user)
    except DerivAuthError:
        failures.add(key, INVALID_TOKEN_WINDOW)
        await run_in_threadpool(_record_failure, db, user, ip)
        raise ApiError(400, "deriv.token_invalid") from None
    record = await run_in_threadpool(
        service.save,
        db,
        settings,
        user,
        token=body.token,
        auth_method="pat",
        accounts=accounts,
        expires_at=None,
        ip=ip,
    )
    return connection_view(record, accounts, settings.real_account_enabled)


def _record_failure(db: Db, user: User, ip: str | None) -> None:
    audit.record(db, "deriv.connect", "failure", actor_user_id=user.id, ip_address=ip)
    db.commit()


@router.get("/connection")
async def connection(
    db: Db, settings: AppSettings, session: CurrentSession, rest: Deriv
) -> dict[str, object]:
    record = await run_in_threadpool(service.find, db, session.user)
    if record is None:
        return {"connected": False}
    token = await run_in_threadpool(service.read_token, settings, record)
    try:
        accounts = await fetch_accounts(rest, token, session.user)
    except DerivAuthError:
        # Jeton expiré ou révoqué chez Deriv : l'interface demandera une nouvelle autorisation.
        return connection_view(record, None, settings.real_account_enabled)
    return connection_view(record, accounts, settings.real_account_enabled)


@router.post("/account")
async def select_account(
    body: SelectIn,
    request: Request,
    db: Db,
    settings: AppSettings,
    session: CurrentSession,
    rest: Deriv,
) -> dict[str, object]:
    user = session.user
    record = await run_in_threadpool(service.find, db, user)
    if record is None:
        raise ApiError(404, "deriv.not_connected")
    token = await run_in_threadpool(service.read_token, settings, record)
    try:
        accounts = await fetch_accounts(rest, token, user)
    except DerivAuthError:
        raise ApiError(400, "deriv.token_invalid") from None
    updated = await run_in_threadpool(
        service.select_account,
        db,
        settings,
        user,
        record,
        accounts,
        body.account_id,
        client_ip(request),
    )
    return connection_view(updated, accounts, settings.real_account_enabled)


@router.delete("/connection", status_code=status.HTTP_204_NO_CONTENT)
def disconnect(request: Request, db: Db, session: CurrentSession) -> None:
    service.disconnect(db, session.user, client_ip(request))
