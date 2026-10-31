"""
Pilotage du bot par le client. L'API enregistre des demandes ; seul le moteur parle à Deriv.

Toutes les limites sont revalidées ici, quelle que soit la valeur envoyée par le front-end.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import available_timezones

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app import audit
from app.authz import CurrentSession
from app.broker.base import AccountKind
from app.config import Settings
from app.db.models import (
    BotSession,
    PositionStatus,
    TradingDecision,
    TradingPosition,
    TradingSettings,
    User,
)
from app.deps import AppSettings, Db, check_origin, client_ip
from app.deriv import service as deriv_service
from app.errors import ApiError
from app.market.router import Market, asset_views
from app.trading import risk
from app.trading.execution import consecutive_losses, day_net, session_net

router = APIRouter(prefix="/trading", tags=["trading"], dependencies=[Depends(check_origin)])

Command = Literal["pause", "resume", "stop", "emergency"]


class SettingsIn(BaseModel):
    stake: Decimal
    multiplier: int
    capital_pct: Decimal
    max_positions: int
    stop_loss_pct: Decimal
    session_target_pct: Decimal
    session_loss_pct: Decimal
    daily_target_pct: Decimal
    daily_loss_pct: Decimal
    max_consecutive_losses: int
    pause_minutes: int
    activation_r: Decimal
    locked_fraction: Decimal
    allowed_symbols: list[str] = Field(min_length=1, max_length=50)
    timezone: str = Field(max_length=64)


class StartIn(BaseModel):
    symbol: str = Field(max_length=30)


def default_settings(user: User, app: Settings) -> TradingSettings:
    return TradingSettings(
        user_id=user.id, allowed_symbols=list(app.market_symbols), timezone="UTC", **risk.DEFAULTS
    )


def settings_of(db: DbSession, user: User, app: Settings) -> TradingSettings:
    return db.get(TradingSettings, user.id) or default_settings(user, app)


def settings_view(row: TradingSettings) -> dict[str, object]:
    fields = list(risk.RANGES)
    view: dict[str, object] = {f: str(getattr(row, f)) for f in fields}
    view.update(allowed_symbols=row.allowed_symbols, timezone=row.timezone)
    return view


def position_view(p: TradingPosition) -> dict[str, object]:
    money = (
        "stake", "stop_loss", "buy_price", "commission", "current_stop", "current_profit",
        "peak_profit", "sell_price", "net_result",
    )  # fmt: skip
    view: dict[str, object] = {
        f: None if getattr(p, f) is None else str(getattr(p, f)) for f in money
    }
    view.update(
        id=p.id,
        session_id=p.session_id,
        symbol=p.symbol,
        direction=p.direction,
        multiplier=p.multiplier,
        status=p.status,
        contract_id=p.contract_id,
        close_requested=p.close_requested,
        close_reason=p.close_reason,
        opened_at=p.opened_at,
        closed_at=p.closed_at,
    )
    return view


def session_view(db: DbSession, s: BotSession, timezone: str) -> dict[str, object]:
    return {
        "id": s.id,
        "symbol": s.symbol,
        "state": s.state,
        "account_kind": s.account_kind,
        "command": s.command,
        "stop_reason": s.stop_reason,
        "error_code": s.error_code,
        "start_balance": None if s.start_balance is None else str(s.start_balance),
        "paused_until": s.paused_until,
        "started_at": s.started_at,
        "ended_at": s.ended_at,
        "session_net": str(session_net(db, s.id)),
        "consecutive_losses": consecutive_losses(db, s.id, s.paused_until),
    }


def active_session(db: DbSession, user: User) -> BotSession | None:
    return db.scalars(
        select(BotSession).where(BotSession.user_id == user.id, BotSession.ended_at.is_(None))
    ).first()


@router.get("/settings")
def read_settings(db: Db, app: AppSettings, session: CurrentSession) -> dict[str, object]:
    return {"settings": settings_view(settings_of(db, session.user, app))}


@router.put("/settings")
def write_settings(
    body: SettingsIn, request: Request, db: Db, app: AppSettings, session: CurrentSession
) -> dict[str, object]:
    user = session.user
    values = body.model_dump()
    if risk.out_of_range(values) or body.timezone not in available_timezones():
        raise ApiError(422, "trading.invalid_settings")
    if any(symbol not in app.market_symbols for symbol in body.allowed_symbols):
        raise ApiError(422, "trading.invalid_settings")
    row = db.get(TradingSettings, user.id) or TradingSettings(user_id=user.id)
    for field, value in values.items():
        setattr(row, field, value)
    db.add(row)
    audit.record(
        db,
        "trading.settings.update",
        "success",
        actor_user_id=user.id,
        ip_address=client_ip(request),
        details={k: str(v) for k, v in values.items()},
    )
    db.commit()
    return {"settings": settings_view(row)}


@router.get("/bot")
def bot(db: Db, app: AppSettings, session: CurrentSession) -> dict[str, object]:
    user = session.user
    timezone = settings_of(db, user, app).timezone
    current = active_session(db, user)
    positions = db.scalars(
        select(TradingPosition).where(
            TradingPosition.user_id == user.id,
            TradingPosition.status.in_(
                [PositionStatus.OPENING, PositionStatus.UNKNOWN, PositionStatus.OPEN]
            ),
        )
    )
    return {
        "session": session_view(db, current, timezone) if current else None,
        "open_positions": [position_view(p) for p in positions],
    }


def _check_start(db: DbSession, user: User, app: Settings, symbol: str) -> tuple[str, str]:
    if user.risk_accepted_at is None:
        raise ApiError(403, "trading.risk_not_accepted")
    record = deriv_service.find(db, user)
    if record is None or record.account_id is None or record.account_kind is None:
        raise ApiError(409, "deriv.not_connected")
    if record.account_kind != AccountKind.DEMO and not app.real_account_enabled:
        raise ApiError(403, "deriv.real_disabled")
    if symbol not in settings_of(db, user, app).allowed_symbols:
        raise ApiError(422, "trading.symbol_not_allowed")
    return record.account_id, record.account_kind


def _create_session(
    db: DbSession, user: User, app: Settings, symbol: str, ip: str | None
) -> BotSession:
    account_id, kind = _check_start(db, user, app, symbol)
    if db.get(TradingSettings, user.id) is None:
        db.add(default_settings(user, app))
    row = BotSession(user_id=user.id, account_id=account_id, account_kind=kind, symbol=symbol)
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "trading.bot_already_active") from None
    audit.record(
        db,
        "trading.bot.start",
        "success",
        actor_user_id=user.id,
        target_type="bot_session",
        target_id=str(row.id),
        ip_address=ip,
        details={"symbol": symbol, "account_kind": kind},
    )
    db.commit()
    return row


@router.post("/bot/start", status_code=status.HTTP_201_CREATED)
async def start(
    body: StartIn,
    request: Request,
    db: Db,
    app: AppSettings,
    session: CurrentSession,
    store: Market,
) -> dict[str, object]:
    # Marché vérifié au démarrage ; chaque ordre le revérifie ensuite côté moteur.
    views = await asset_views(store, app.market_symbols)
    asset = next((a for a in views if a["symbol"] == body.symbol), None)
    if asset is None or asset["status"] != "live":
        raise ApiError(409, "trading.market_not_live")
    row = await run_in_threadpool(
        _create_session, db, session.user, app, body.symbol, client_ip(request)
    )
    return {"session": {"id": row.id, "state": row.state, "symbol": row.symbol}}


def _send_command(db: DbSession, user: User, command: Command, ip: str | None) -> None:
    current = active_session(db, user)
    if current is None:
        raise ApiError(409, "trading.no_active_bot")
    # L'arrêt d'urgence passe avant toute autre demande en attente.
    if current.command != "emergency":
        current.command = command
    audit.record(
        db,
        f"trading.bot.{command}",
        "success",
        actor_user_id=user.id,
        target_type="bot_session",
        target_id=str(current.id),
        ip_address=ip,
    )
    db.commit()


@router.post("/bot/command/{command}", status_code=status.HTTP_202_ACCEPTED)
def command(
    command: Command, request: Request, db: Db, session: CurrentSession
) -> dict[str, object]:
    _send_command(db, session.user, command, client_ip(request))
    return {"accepted": command}


@router.post("/positions/{position_id}/close", status_code=status.HTTP_202_ACCEPTED)
def close_position(
    position_id: uuid.UUID, request: Request, db: Db, session: CurrentSession
) -> dict[str, object]:
    user = session.user
    position = db.get(TradingPosition, position_id)
    # Même réponse que pour une position inconnue : rien ne révèle celles des autres.
    if position is None or position.user_id != user.id:
        raise ApiError(404, "trading.position_not_found")
    if position.status != PositionStatus.OPEN:
        raise ApiError(409, "trading.position_not_open")
    position.close_requested = True
    audit.record(
        db,
        "trading.position.close",
        "success",
        actor_user_id=user.id,
        target_type="position",
        target_id=str(position_id),
        ip_address=client_ip(request),
    )
    db.commit()
    return {"accepted": True}


@router.get("/positions")
def positions(
    db: Db, session: CurrentSession, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> dict[str, object]:
    rows = db.scalars(
        select(TradingPosition)
        .where(
            TradingPosition.user_id == session.user.id,
            TradingPosition.status != PositionStatus.VOID,
        )
        .order_by(TradingPosition.created_at.desc())
        .limit(limit)
    )
    return {"positions": [position_view(p) for p in rows]}


@router.get("/decisions")
def decisions(
    db: Db, session: CurrentSession, limit: Annotated[int, Query(ge=1, le=200)] = 100
) -> dict[str, object]:
    rows = db.scalars(
        select(TradingDecision)
        .join(BotSession, BotSession.id == TradingDecision.session_id)
        .where(BotSession.user_id == session.user.id)
        .order_by(TradingDecision.id.desc())
        .limit(limit)
    )
    return {
        "decisions": [
            {"at": d.at, "kind": d.kind, "code": d.code, "data": d.data, "position": d.position_id}
            for d in rows
        ]
    }


@router.get("/summary")
def summary(db: Db, app: AppSettings, session: CurrentSession) -> dict[str, object]:
    user = session.user
    timezone = settings_of(db, user, app).timezone
    return {"day_net": str(day_net(db, user.id, timezone, datetime.now(UTC)))}
