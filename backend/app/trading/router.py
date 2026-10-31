"""
Pilotage du bot par le client. L'API enregistre des demandes ; seul le moteur parle à Deriv.

Toutes les limites sont revalidées ici, quelle que soit la valeur envoyée par le front-end.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import available_timezones

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
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
from app.trading import exits, risk
from app.trading.execution import consecutive_losses, day_net, session_net

router = APIRouter(prefix="/trading", tags=["trading"], dependencies=[Depends(check_origin)])

Command = Literal["pause", "resume", "stop", "emergency"]

# Au-delà, le moteur est considéré comme absent : son signal de vie part toutes les 5 s.
ENGINE_ALIVE = 20
CURVE_POINTS = 200
IDLE_SIGNALS = ("strategy.no_cross", "strategy.flat_market")


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
        user_id=user.id,
        allowed_symbols=list(app.market_symbols),
        timezone=user.time_zone,
        **risk.DEFAULTS,
    )


def settings_of(db: DbSession, user: User, app: Settings) -> TradingSettings:
    return db.get(TradingSettings, user.id) or default_settings(user, app)


def settings_view(row: TradingSettings) -> dict[str, object]:
    fields = list(risk.RANGES)
    view: dict[str, object] = {f: str(getattr(row, f)) for f in fields}
    view.update(allowed_symbols=row.allowed_symbols, timezone=row.timezone)
    return view


def text_or_none(value: object) -> str | None:
    return None if value is None else str(value)


def protection_view(p: TradingPosition, row: TradingSettings) -> dict[str, object] | None:
    """Protections calculées ici : le front-end affiche, il ne décide jamais."""
    if p.status != PositionStatus.OPEN or p.commission is None:
        return None
    view = exits.PositionView(
        p.current_profit or Decimal(0), p.peak_profit, p.commission, p.stop_loss, p.current_stop
    )
    activation = exits.activation_level(
        view, exits.ExitParams(row.activation_r, row.locked_fraction)
    )
    active = p.peak_profit >= activation
    stop = p.current_stop if p.current_stop is not None else p.stop_loss
    return {
        "activation_level": str(activation.quantize(Decimal("0.01"))),
        "ratchet_active": active,
        "locked_level": str((p.peak_profit * row.locked_fraction).quantize(Decimal("0.01")))
        if active
        else None,
        "floor_active": p.current_stop is not None and p.current_stop < p.stop_loss,
        "worst_case_loss": str(risk.worst_case_loss(stop)),
    }


def position_view(p: TradingPosition, row: TradingSettings | None = None) -> dict[str, object]:
    money = (
        "stake", "stop_loss", "buy_price", "commission", "current_stop", "current_profit",
        "peak_profit", "sell_price", "net_result", "entry_spot", "stop_spot",
    )  # fmt: skip
    view: dict[str, object] = {f: text_or_none(getattr(p, f)) for f in money}
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
        protection=protection_view(p, row) if row else None,
    )
    return view


def session_view(s: BotSession, db: DbSession, now: datetime) -> dict[str, object]:
    alive = s.heartbeat_at is not None and (now - s.heartbeat_at).total_seconds() < ENGINE_ALIVE
    return {
        "id": s.id,
        "symbol": s.symbol,
        "state": s.state,
        "account_kind": s.account_kind,
        "command": s.command,
        "stop_reason": s.stop_reason,
        "error_code": s.error_code,
        "start_balance": text_or_none(s.start_balance),
        "paused_until": s.paused_until,
        "started_at": s.started_at,
        "ended_at": s.ended_at,
        "session_net": str(session_net(db, s.id)),
        "consecutive_losses": consecutive_losses(db, s.id, s.paused_until),
        "engine_online": alive,
        "deriv_connected": alive and s.deriv_connected,
    }


def risk_view(
    db: DbSession,
    s: BotSession,
    row: TradingSettings,
    positions: Sequence[TradingPosition],
    now: datetime,
) -> dict[str, object] | None:
    """Mêmes bases de calcul que le moteur, en montants, pour la session en cours."""
    if s.start_balance is None:
        return None
    base = s.start_balance

    def share(pct: Decimal) -> str:
        return str((base * pct / 100).quantize(Decimal("0.01")))

    stop = risk.stop_amount(row)
    return {
        "session_net": str(session_net(db, s.id)),
        "session_loss_limit": share(row.session_loss_pct),
        "session_target": share(row.session_target_pct),
        "day_net": str(day_net(db, s.user_id, row.timezone, now)),
        "day_loss_limit": share(row.daily_loss_pct),
        "day_target": share(row.daily_target_pct),
        "exposure": str(sum((p.stake for p in positions), Decimal(0))),
        "exposure_limit": share(row.capital_pct),
        "open_positions": len(positions),
        "max_positions": row.max_positions,
        "consecutive_losses": consecutive_losses(db, s.id, s.paused_until),
        "max_consecutive_losses": row.max_consecutive_losses,
        "stop_loss": str(stop),
        "worst_case_loss": str(risk.worst_case_loss(stop)),
        "slippage_margin": str(risk.SLIPPAGE_MARGIN),
    }


def active_session(db: DbSession, user: User) -> BotSession | None:
    return db.scalars(
        select(BotSession).where(BotSession.user_id == user.id, BotSession.ended_at.is_(None))
    ).first()


def last_session(db: DbSession, user: User) -> BotSession | None:
    return db.scalars(
        select(BotSession)
        .where(BotSession.user_id == user.id, BotSession.ended_at.is_not(None))
        .order_by(BotSession.ended_at.desc())
    ).first()


@router.get("/settings")
def read_settings(db: Db, app: AppSettings, session: CurrentSession) -> dict[str, object]:
    return {
        "settings": settings_view(settings_of(db, session.user, app)),
        "ranges": {k: {"min": str(a), "max": str(b)} for k, (a, b) in risk.RANGES.items()},
        "provisional": ["multiplier", "activation_r", "locked_fraction"],
    }


@router.put("/settings")
def write_settings(
    body: SettingsIn, request: Request, db: Db, app: AppSettings, session: CurrentSession
) -> dict[str, object]:
    user = session.user
    values = body.model_dump()
    bad = risk.out_of_range(values)
    if body.timezone not in available_timezones():
        bad.append("timezone")
    if any(symbol not in app.market_symbols for symbol in body.allowed_symbols):
        bad.append("allowed_symbols")
    if bad:
        raise ApiError(422, "trading.invalid_settings", fields=bad)
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
    now = datetime.now(UTC)
    row = settings_of(db, user, app)
    current = active_session(db, user)
    positions = list(
        db.scalars(
            select(TradingPosition)
            .where(
                TradingPosition.user_id == user.id,
                TradingPosition.status.in_(
                    [PositionStatus.OPENING, PositionStatus.UNKNOWN, PositionStatus.OPEN]
                ),
            )
            .order_by(TradingPosition.created_at)
        )
    )
    finished = None if current else last_session(db, user)
    return {
        "session": session_view(current, db, now) if current else None,
        "last_session": session_view(finished, db, now) if finished else None,
        "open_positions": [position_view(p, row) for p in positions],
        "risk": risk_view(db, current, row, positions, now) if current else None,
        "server_time": now,
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
    db: Db,
    session: CurrentSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    closed: bool = False,
) -> dict[str, object]:
    query = (
        select(TradingPosition, BotSession.account_kind)
        .join(BotSession, BotSession.id == TradingPosition.session_id)
        .where(
            TradingPosition.user_id == session.user.id,
            TradingPosition.status != PositionStatus.VOID,
        )
        .order_by(TradingPosition.created_at.desc())
        .limit(limit)
    )
    if closed:
        query = query.where(TradingPosition.status == PositionStatus.CLOSED)
    rows = db.execute(query)
    return {"positions": [{**position_view(p), "account_kind": kind} for p, kind in rows]}


@router.get("/decisions")
def decisions(
    db: Db,
    session: CurrentSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    hide_idle: bool = False,
) -> dict[str, object]:
    query = (
        select(TradingDecision)
        .join(BotSession, BotSession.id == TradingDecision.session_id)
        .where(BotSession.user_id == session.user.id)
        .order_by(TradingDecision.id.desc())
        .limit(limit)
    )
    if hide_idle:
        # Sans signal, sans décision : une ligne par minute noierait le reste du journal.
        query = query.where(
            or_(
                TradingDecision.kind != "signal",
                TradingDecision.code.not_in(IDLE_SIGNALS),
            )
        )
    return {
        "decisions": [
            {
                "id": d.id,
                "at": d.at,
                "kind": d.kind,
                "code": d.code,
                "data": d.data,
                "position": d.position_id,
            }
            for d in db.scalars(query)
        ]
    }


@router.get("/summary")
def summary(db: Db, app: AppSettings, session: CurrentSession) -> dict[str, object]:
    """Statistiques calculées sur les positions réellement clôturées, sans extrapolation."""
    user = session.user
    timezone = settings_of(db, user, app).timezone
    results = list(
        db.execute(
            select(TradingPosition.closed_at, TradingPosition.net_result)
            .where(
                TradingPosition.user_id == user.id,
                TradingPosition.status == PositionStatus.CLOSED,
                TradingPosition.net_result.is_not(None),
            )
            .order_by(TradingPosition.closed_at)
        )
    )
    closed = [(at, net) for at, net in results if net is not None]
    nets: list[Decimal] = [net for _, net in closed]
    gains = [n for n in nets if n > 0]
    losses = [n for n in nets if n < 0]
    running = Decimal(0)
    curve = []
    for closed_at, net in closed:
        running += net
        curve.append({"at": closed_at, "net": str(running)})

    def mean(values: list[Decimal]) -> str | None:
        if not values:
            return None
        return str((sum(values, Decimal(0)) / len(values)).quantize(Decimal("0.01")))

    return {
        "day_net": str(day_net(db, user.id, timezone, datetime.now(UTC))),
        "total_net": str(running),
        "trades": len(nets),
        "wins": len(gains),
        "losses": len(losses),
        "win_rate": round(len(gains) / len(nets), 4) if nets else None,
        "average_gain": mean(gains),
        "average_loss": mean(losses),
        "best": str(max(nets)) if nets else None,
        "worst": str(min(nets)) if nets else None,
        "curve": curve[-CURVE_POINTS:],
    }
