"""
Machine d'états du bot. Une boucle par session, seule à agir sur le compte.

Le client écrit une commande en base, le moteur l'applique. Après un démarrage ou une coupure,
aucune décision avant réconciliation. Les positions ouvertes restent protégées par le stop
loss chez Deriv, y compris si cette boucle s'arrête.
"""

import asyncio
import logging
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.billing.service import has_access
from app.broker.base import ApiRejectedError, BrokerError, Message, Subscription
from app.broker.deriv_trading import DerivTrading
from app.db.models import (
    BotSession,
    BotState,
    PositionStatus,
    TradingPosition,
    TradingSettings,
)
from app.market.quality import closed_candles, entry_refusal, read_snapshot
from app.market.store import MarketStore
from app.trading import exits, risk, strategy
from app.trading.execution import (
    Executor,
    Journal,
    as_decimal,
    consecutive_losses,
    day_net,
    session_net,
)

logger = logging.getLogger("safetrade.trading")

STEP_SECONDS = 1.0
CONNECTION_ERROR_SECONDS = 60.0
# Sans mise à jour du flux de la position au-delà, elle est relue directement.
CONTRACT_STALE_SECONDS = 5.0
# Deriv refuse plus d'un `contract_update` par seconde.
UPDATE_SPACING_SECONDS = 1.1
SELL_RETRY_SECONDS = 2.0
HEARTBEAT_SECONDS = 5.0
# Refus mesuré : « Enter an amount equal to or higher than 0.21. »
STOP_MINIMUM = re.compile(r"higher than (\d+(?:\.\d+)?)")


@dataclass
class Tracked:
    stream: Subscription | None = None
    state: Message | None = None
    seen_at: float = 0.0
    updated_at: float = 0.0
    sell_at: float = 0.0
    floor_refused: bool = False
    stop_minimum: Decimal | None = None


def contract_of(position: TradingPosition) -> int:
    if position.contract_id is None:
        raise ValueError("position sans contrat")
    return position.contract_id


def stop_of(contract: Message) -> Decimal | None:
    order = (contract.get("limit_order") or {}).get("stop_loss") or {}
    amount = order.get("order_amount")
    return abs(as_decimal(amount)) if amount is not None else None


class BotRunner:
    def __init__(
        self,
        session_id: uuid.UUID,
        journal: Journal,
        trading: DerivTrading,
        executor: Executor,
        market: MarketStore,
        *,
        real_enabled: bool = False,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.session_id = session_id
        self._journal = journal
        self._trading = trading
        self._executor = executor
        self._market = market
        self._real_enabled = real_enabled
        self._clock = clock
        self._monotonic = monotonic
        self._tracked: dict[int, Tracked] = {}
        self._reconcile_needed = True
        self._reconnections = 0
        self._disconnected_at: float | None = None
        self._last_candle: int | None = None
        self._last_refusal: str | None = None
        self._beat_at: float | None = None
        self.finished = False

    async def run(self) -> None:
        try:
            while not self.finished:
                try:
                    await self.step()
                except BrokerError as exc:
                    # Coupure ou refus passager : réconciliation, puis reprise.
                    self._reconcile_needed = True
                    await self._journal.note(self.session_id, "broker_error", type(exc).__name__)
                await asyncio.sleep(STEP_SECONDS)
        finally:
            await self._close_streams()

    async def _close_streams(self) -> None:
        for tracked in self._tracked.values():
            if tracked.stream is not None:
                await asyncio.gather(tracked.stream.cancel(), return_exceptions=True)
        self._tracked.clear()

    async def _load(self) -> tuple[BotSession, TradingSettings, list[TradingPosition]]:
        def read(db: DbSession) -> tuple[BotSession, TradingSettings, list[TradingPosition]]:
            session = db.get_one(BotSession, self.session_id)
            settings = db.get_one(TradingSettings, session.user_id)
            positions = list(
                db.scalars(
                    select(TradingPosition).where(
                        TradingPosition.account_id == session.account_id,
                        TradingPosition.status.in_(
                            [
                                PositionStatus.OPENING,
                                PositionStatus.UNKNOWN,
                                PositionStatus.OPEN,
                            ]
                        ),
                    )
                )
            )
            return session, settings, positions

        return await self._journal.run(read)

    async def _set(self, **changes: Any) -> None:
        def write(db: DbSession) -> None:
            session = db.get_one(BotSession, self.session_id)
            for field, value in changes.items():
                setattr(session, field, value)

        await self._journal.run(write)

    async def step(self) -> None:
        session, settings, positions = await self._load()
        if session.ended_at is not None:
            self.finished = True
            return
        await self._beat(session)
        if not self._trading.connected:
            await self._on_disconnected()
            return
        self._disconnected_at = None
        if self._trading.reconnections != self._reconnections:
            self._reconnections = self._trading.reconnections
            self._reconcile_needed = True
        if self._reconcile_needed:
            await self._reconcile(session)
            session, settings, positions = await self._load()
        if session.command:
            await self._apply_command(session, positions)
            session, settings, positions = await self._load()
        if any(p.status != PositionStatus.OPEN for p in positions):
            await self._executor.resolve_pending(session)
        for position in positions:
            if position.status == PositionStatus.OPEN:
                await self._manage(session, settings, position)
        session, settings, positions = await self._load()
        await self._advance(session, settings, positions)
        if session.state == BotState.ANALYZING and not positions:
            await self._consider_entry(session, settings, positions)

    async def _beat(self, session: BotSession) -> None:
        """Signal de vie, écrit aussi sans connexion à Deriv : c'est là qu'il compte."""
        now = self._monotonic()
        connected = self._trading.connected
        changed = connected != session.deriv_connected
        if not changed and self._beat_at is not None and now - self._beat_at < HEARTBEAT_SECONDS:
            return
        self._beat_at = now
        await self._set(heartbeat_at=self._clock(), deriv_connected=connected)

    async def _on_disconnected(self) -> None:
        now = self._monotonic()
        self._reconcile_needed = True
        if self._disconnected_at is None:
            self._disconnected_at = now
        elif now - self._disconnected_at >= CONNECTION_ERROR_SECONDS:
            session, _, _ = await self._load()
            if session.state != BotState.ERROR:
                await self._set(state=BotState.ERROR, error_code="deriv.connection_lost")
                await self._journal.note(self.session_id, "error", "deriv.connection_lost")

    async def _reconcile(self, session: BotSession) -> None:
        if session.start_balance is None:
            await self._set(start_balance=await self._trading.balance())
        await self._executor.reconcile(session)
        self._reconcile_needed = False
        self._reconnections = self._trading.reconnections
        if session.state in (BotState.STARTING, BotState.ERROR):
            await self._set(state=BotState.ANALYZING, error_code=None)

    async def _apply_command(self, session: BotSession, positions: list[TradingPosition]) -> None:
        command = session.command
        changes: dict[str, Any] = {"command": None}
        if command == "pause":
            changes.update(state=BotState.PAUSED)
        elif command == "resume" and session.state == BotState.PAUSED:
            changes.update(state=BotState.ANALYZING)
        elif command == "stop":
            changes.update(state=BotState.STOPPING, stop_reason="client")
        elif command == "emergency":
            changes.update(state=BotState.STOPPING, stop_reason="emergency")

            def request_close(db: DbSession) -> None:
                for position in positions:
                    if position.status == PositionStatus.OPEN:
                        db.get_one(TradingPosition, position.id).close_requested = True

            await self._journal.run(request_close)
        await self._set(**changes)
        await self._journal.note(self.session_id, "command", command)

    async def _follow(self, position: TradingPosition) -> Message:
        contract_id = contract_of(position)
        tracked = self._tracked.setdefault(contract_id, Tracked())
        if tracked.stream is None:

            async def on_update(message: Message) -> None:
                state = message.get("proposal_open_contract")
                if state:
                    tracked.state = state
                    tracked.seen_at = self._monotonic()

            tracked.stream = await self._trading.watch(contract_id, on_update)
        if tracked.state is None or self._monotonic() - tracked.seen_at > CONTRACT_STALE_SECONDS:
            tracked.state = await self._trading.contract(contract_id)
            tracked.seen_at = self._monotonic()
        return tracked.state

    async def _forget(self, contract_id: int) -> None:
        tracked = self._tracked.pop(contract_id, None)
        if tracked is not None and tracked.stream is not None:
            await asyncio.gather(tracked.stream.cancel(), return_exceptions=True)

    async def _manage(
        self, session: BotSession, settings: TradingSettings, position: TradingPosition
    ) -> None:
        contract = await self._follow(position)
        contract_id = contract_of(position)
        if contract.get("is_sold"):
            await self._executor.finalize(position.id, contract)
            await self._forget(contract_id)
            return
        profit = as_decimal(contract.get("profit", 0))
        commission = as_decimal(contract.get("commission") or position.commission or 0)
        stop = stop_of(contract)
        peak = max(position.peak_profit, profit)

        def save(db: DbSession) -> None:
            row = db.get_one(TradingPosition, position.id)
            row.current_profit = profit
            row.peak_profit = peak
            row.commission = commission
            row.current_stop = stop
            if contract.get("entry_spot") is not None:
                row.entry_spot = as_decimal(contract["entry_spot"])
            stop_order = (contract.get("limit_order") or {}).get("stop_loss") or {}
            row.stop_spot = as_decimal(stop_order["value"]) if stop_order.get("value") else None

        await self._journal.run(save)
        if stop is None:
            await self._restore_stop(position, contract)
            return
        if position.close_requested:
            reason = session.stop_reason if session.stop_reason == "emergency" else "client"
            await self._sell(position, contract, reason)
            return
        action = exits.decide(
            exits.PositionView(
                profit,
                peak,
                commission,
                position.stop_loss,
                stop,
                self._tracked[contract_id].stop_minimum,
            ),
            exits.ExitParams(settings.activation_r, settings.locked_fraction),
        )
        if action.kind == "sell":
            await self._sell(position, contract, action.reason or "exit")
        elif action.kind == "tighten" and action.stop_loss is not None:
            await self._tighten(position, action.stop_loss)

    async def _restore_stop(self, position: TradingPosition, contract: Message) -> None:
        """Position sans stop loss : le remettre, sinon la clôturer."""
        contract_id = contract_of(position)
        await self._journal.note(
            self.session_id, "stop_missing", "position.no_stop", position_id=position.id
        )
        try:
            await self._trading.update_stop(contract_id, position.stop_loss)
        except BrokerError:
            await self._sell(position, contract, "no_stop")

    async def _tighten(self, position: TradingPosition, stop_loss: Decimal) -> None:
        contract_id = contract_of(position)
        tracked = self._tracked[contract_id]
        now = self._monotonic()
        if tracked.floor_refused or now - tracked.updated_at < UPDATE_SPACING_SECONDS:
            return
        tracked.updated_at = now
        try:
            await self._trading.update_stop(contract_id, stop_loss)
        except ApiRejectedError as exc:
            # Le stop initial reste en place : la protection ne recule pas.
            minimum = STOP_MINIMUM.search(exc.message)
            if minimum:
                # Minimum arrondi à l'affichage : refusé même à sa valeur exacte (mesuré).
                stated = Decimal(minimum.group(1))
                tracked.stop_minimum = max(stated, stop_loss + exits.STOP_MARGIN)
            elif exc.code != "ContractUpdateTooFrequent":
                tracked.floor_refused = True
            await self._journal.note(
                self.session_id,
                "floor_refused",
                exc.code,
                {"message": exc.message, "asked": str(stop_loss)},
                position.id,
            )
            return
        await self._journal.note(
            self.session_id,
            "floor_set",
            data={"stop_loss": str(stop_loss)},
            position_id=position.id,
        )

    async def _sell(self, position: TradingPosition, contract: Message, reason: str) -> None:
        contract_id = contract_of(position)
        tracked = self._tracked[contract_id]
        now = self._monotonic()
        if not contract.get("is_valid_to_sell") or now - tracked.sell_at < SELL_RETRY_SECONDS:
            return  # par exemple, prix d'entrée pas encore fixé
        tracked.sell_at = now
        try:
            await self._trading.sell(contract_id)
        except ApiRejectedError as exc:
            await self._journal.note(
                self.session_id, "sell_refused", exc.code, position_id=position.id
            )
            return

        def mark(db: DbSession) -> None:
            db.get_one(TradingPosition, position.id).close_reason = reason

        await self._journal.run(mark)
        await self._journal.note(self.session_id, "sell_sent", reason, position_id=position.id)
        final = await self._trading.contract(contract_id)
        if final.get("is_sold"):
            await self._executor.finalize(position.id, final)
            await self._forget(contract_id)

    async def _figures(
        self, session: BotSession, settings: TradingSettings
    ) -> tuple[Decimal, Decimal, int]:
        now = self._clock()

        def read(db: DbSession) -> tuple[Decimal, Decimal, int]:
            return (
                session_net(db, session.id),
                day_net(db, session.user_id, settings.timezone, now),
                consecutive_losses(db, session.id, session.paused_until),
            )

        return await self._journal.run(read)

    async def _advance(
        self,
        session: BotSession,
        settings: TradingSettings,
        positions: list[TradingPosition],
    ) -> None:
        now = self._clock()
        state = session.state
        if state == BotState.STOPPING:
            if not positions:
                await self._set(state=BotState.STOPPED, ended_at=now)
                await self._journal.note(self.session_id, "stopped", session.stop_reason)
                self.finished = True
            return
        if state == BotState.PAUSED:
            if session.paused_until is not None and now >= session.paused_until:
                await self._set(state=BotState.ANALYZING)
                session.state = BotState.ANALYZING
            return
        if not await self._journal.run(lambda db: has_access(db, session.user_id, now)):
            # Plus de nouvelle position ; les ouvertes finissent sous leur stop loss (q06).
            await self._set(state=BotState.STOPPING, stop_reason="billing.expired")
            session.state = BotState.STOPPING
            await self._journal.note(self.session_id, "limit", "billing.expired")
            return
        if state not in (BotState.ANALYZING, BotState.POSITION_OPEN):
            return
        start = session.start_balance or Decimal(0)
        net, day, losses = await self._figures(session, settings)
        outcome = risk.session_outcome(
            risk.OrderCheck(
                params=settings, stake=settings.stake, stop_loss=None, balance=start,
                start_balance=start, open_exposure=Decimal(0), open_positions=0,
                pending_orders=0, session_net=net, day_net=day, day_start_balance=start,
                consecutive_losses=losses, paused_until=None, now=now, market_refusal=None,
                account_kind=session.account_kind, real_enabled=self._real_enabled,
                symbol_allowed=True, connected=True,
            )
        )  # fmt: skip
        if outcome:
            limit = outcome.endswith("_limit")
            await self._set(
                state=BotState.LIMIT_REACHED if limit else BotState.TARGET_REACHED,
                stop_reason=outcome,
            )
            session.state = BotState.LIMIT_REACHED if limit else BotState.TARGET_REACHED
            await self._journal.note(self.session_id, "limit", outcome, {"net": str(net)})
            return
        if losses >= settings.max_consecutive_losses:
            until = now + timedelta(minutes=settings.pause_minutes)
            await self._set(state=BotState.PAUSED, paused_until=until)
            session.state = BotState.PAUSED
            await self._journal.note(self.session_id, "cooldown", "risk.consecutive_losses")
            return
        wanted = BotState.POSITION_OPEN if positions else BotState.ANALYZING
        if wanted != state:
            await self._set(state=wanted)
            session.state = wanted

    async def _refuse(self, code: str, data: dict[str, Any] | None = None) -> None:
        """Un refus répété n'est écrit qu'une fois."""
        if code != self._last_refusal:
            self._last_refusal = code
            await self._journal.note(self.session_id, "order_refused", code, data)

    async def _consider_entry(
        self,
        session: BotSession,
        settings: TradingSettings,
        positions: list[TradingPosition],
    ) -> None:
        now = self._clock()
        now_ts = now.timestamp()
        # Garde les bougies de cet actif à jour, même sans graphique ouvert.
        await self._market.demand(session.symbol)
        snapshot = await read_snapshot(self._market, session.symbol, strategy.GRANULARITY, now_ts)
        refusal = entry_refusal(snapshot, now_ts, strategy.NEEDED_CANDLES)
        if refusal:
            await self._refuse(refusal)
            return
        closed = closed_candles(snapshot.candles, snapshot.granularity, now_ts)
        candle = closed[-1]["epoch"]
        if candle == self._last_candle:
            return  # une décision par bougie close
        self._last_candle = candle
        signal = strategy.evaluate(closed[-strategy.NEEDED_CANDLES :])
        await self._journal.note(self.session_id, "signal", signal.reason, signal.data)
        if signal.direction is None:
            return
        net, day, losses = await self._figures(session, settings)
        balance = await self._trading.balance()
        check = risk.OrderCheck(
            params=settings,
            stake=settings.stake,
            stop_loss=risk.stop_amount(settings),
            balance=balance,
            start_balance=session.start_balance or balance,
            open_exposure=sum((p.stake for p in positions), Decimal(0)),
            open_positions=len(positions),
            pending_orders=0,
            session_net=net,
            day_net=day,
            day_start_balance=session.start_balance or balance,
            consecutive_losses=losses,
            paused_until=session.paused_until,
            now=now,
            market_refusal=None,
            account_kind=session.account_kind,
            real_enabled=self._real_enabled,
            symbol_allowed=settings.allows(session.symbol),
            connected=self._trading.connected,
        )
        refusal = risk.order_refusal(check)
        if refusal:
            await self._refuse(refusal, {"balance": str(balance)})
            return
        self._last_refusal = None
        multiplier = risk.multiplier_for(settings.multiplier, snapshot.multiplier_range)
        await self._executor.open_position(session, settings, signal.direction, multiplier)
