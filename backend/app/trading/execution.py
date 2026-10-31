"""
Exécution et réconciliation : tout ordre laisse une trace avant de partir.

Ordre des écritures à l'ouverture : position `opening`, proposition, date d'envoi enregistrée,
achat. Une panne à n'importe quel point laisse donc un état que `reconcile` sait résoudre, et
l'index unique bloque tout autre achat sur le compte en attendant. Un achat n'est jamais
renvoyé : une issue inconnue se lit dans `statement`.
"""

import asyncio
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, TypeVar
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from app.broker.base import BrokerError, Message, OrderOutcomeUnknownError
from app.broker.deriv_trading import DerivTrading, Guard, matches
from app.db.models import (
    BotSession,
    PositionStatus,
    TradingDecision,
    TradingPosition,
    TradingSettings,
)
from app.trading import risk

logger = logging.getLogger("safetrade.trading")

T = TypeVar("T")

# Délai d'apparition d'un achat dans `statement` avant de le déclarer non exécuté.
STATEMENT_DELAY_SECONDS = 20
STATEMENT_MARGIN_SECONDS = 5


def as_decimal(value: Any) -> Decimal:
    return Decimal(str(value))


class Journal:
    """Accès à la base depuis la boucle asynchrone, sans la bloquer."""

    def __init__(self, factory: sessionmaker[DbSession]) -> None:
        self._factory = factory

    async def run(self, work: Callable[[DbSession], T]) -> T:
        def job() -> T:
            with self._factory() as db:
                result = work(db)
                db.commit()
                return result

        return await asyncio.to_thread(job)

    async def note(
        self,
        session_id: uuid.UUID,
        kind: str,
        code: str | None = None,
        data: dict[str, Any] | None = None,
        position_id: uuid.UUID | None = None,
    ) -> None:
        def write(db: DbSession) -> None:
            db.add(
                TradingDecision(
                    session_id=session_id,
                    position_id=position_id,
                    kind=kind,
                    code=code,
                    data=data or {},
                )
            )

        await self.run(write)
        logger.info(
            "décision",
            extra={"event": f"trading.{kind}", "code": code, "session": str(session_id)},
        )


def session_net(db: DbSession, session_id: uuid.UUID) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(TradingPosition.net_result), 0)).where(
            TradingPosition.session_id == session_id
        )
    )
    return as_decimal(total)


def day_start(timezone: str, now: datetime) -> datetime:
    """Section 7 : la journée se calcule dans le fuseau du client."""
    local = now.astimezone(ZoneInfo(timezone))
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)


def day_net(db: DbSession, user_id: uuid.UUID, timezone: str, now: datetime) -> Decimal:
    total = db.scalar(
        select(func.coalesce(func.sum(TradingPosition.net_result), 0)).where(
            TradingPosition.user_id == user_id,
            TradingPosition.closed_at >= day_start(timezone, now),
        )
    )
    return as_decimal(total)


def consecutive_losses(db: DbSession, session_id: uuid.UUID, since: datetime | None = None) -> int:
    """Depuis la dernière pause : une pause de refroidissement remet le compte à zéro."""
    query = (
        select(TradingPosition.net_result)
        .where(
            TradingPosition.session_id == session_id,
            TradingPosition.status == PositionStatus.CLOSED,
        )
        .order_by(TradingPosition.closed_at.desc())
    )
    if since is not None:
        query = query.where(TradingPosition.closed_at >= since)
    results = db.scalars(query)
    count = 0
    for result in results:
        if result is None or result >= 0:
            break
        count += 1
    return count


class Executor:
    def __init__(self, journal: Journal, trading: DerivTrading, guard: Guard) -> None:
        self._journal = journal
        self._trading = trading
        self._guard = guard

    async def _void(self, position_id: uuid.UUID, session_id: uuid.UUID, code: str) -> None:
        def write(db: DbSession) -> None:
            row = db.get_one(TradingPosition, position_id)
            row.status = PositionStatus.VOID
            row.close_reason = code

        await self._journal.run(write)
        await self._journal.note(session_id, "order_void", code, position_id=position_id)

    async def open_position(
        self,
        session: BotSession,
        settings: TradingSettings,
        direction: str,
        multiplier: int | None = None,
    ) -> uuid.UUID | None:
        """Renvoie la position ouverte, ou None : aucune nouvelle tentative ici."""
        stop_loss = risk.stop_amount(settings)
        used = multiplier or settings.multiplier
        position = TradingPosition(
            session_id=session.id,
            user_id=session.user_id,
            account_id=session.account_id,
            symbol=session.symbol,
            direction=direction,
            stake=settings.stake,
            multiplier=used,
            stop_loss=stop_loss,
            current_stop=stop_loss,
            status=PositionStatus.OPENING,
            peak_profit=Decimal(0),
        )

        def insert(db: DbSession) -> uuid.UUID:
            db.add(position)
            db.flush()
            return position.id

        try:
            position_id = await self._journal.run(insert)
        except IntegrityError:
            await self._journal.note(session.id, "order_refused", "risk.order_pending")
            return None
        return await self._send(session, settings, direction, stop_loss, position_id, used)

    async def _send(
        self,
        session: BotSession,
        settings: TradingSettings,
        direction: str,
        stop_loss: Decimal,
        position_id: uuid.UUID,
        multiplier: int,
    ) -> uuid.UUID | None:
        try:
            proposal = await self._trading.proposal(
                session.symbol, direction, settings.stake, multiplier, stop_loss
            )
        except BrokerError as exc:
            await self._void(position_id, session.id, f"order.proposal_{type(exc).__name__}")
            return None
        refusal = risk.proposal_refusal(proposal, settings.stake, stop_loss)
        if refusal:
            await self._void(position_id, session.id, refusal)
            return None
        # Le bail est relu au dernier moment : un moteur remplacé n'achète plus.
        if not await self._guard():
            await self._void(position_id, session.id, "order.lease_lost")
            return None

        def mark_sent(db: DbSession) -> None:
            db.get_one(TradingPosition, position_id).sent_at = datetime.now(UTC)

        await self._journal.run(mark_sent)
        try:
            purchase = await self._trading.buy(proposal["id"], float(proposal["ask_price"]))
        except OrderOutcomeUnknownError:

            def mark_unknown(db: DbSession) -> None:
                db.get_one(TradingPosition, position_id).status = PositionStatus.UNKNOWN

            await self._journal.run(mark_unknown)
            await self._journal.note(
                session.id, "order_unknown", "order.outcome_unknown", position_id=position_id
            )
            return None
        except BrokerError as exc:
            code = getattr(exc, "code", type(exc).__name__)
            await self._void(position_id, session.id, f"order.refused_{code}")
            return None

        def mark_open(db: DbSession) -> None:
            row = db.get_one(TradingPosition, position_id)
            row.status = PositionStatus.OPEN
            row.contract_id = purchase.contract_id
            row.buy_price = as_decimal(purchase.buy_price)
            row.commission = as_decimal(proposal["commission"])
            row.opened_at = datetime.now(UTC)

        await self._journal.run(mark_open)
        await self._journal.note(
            session.id,
            "position_open",
            data={
                "contract_id": purchase.contract_id,
                "direction": direction,
                "buy_price": purchase.buy_price,
                "stop_loss": str(stop_loss),
                "commission": proposal["commission"],
            },
            position_id=position_id,
        )
        return position_id

    async def finalize(self, position_id: uuid.UUID, contract: Message) -> None:
        """Résultat de référence : celui de Deriv (q18)."""
        sell_price = as_decimal(contract["sell_price"])

        def write(db: DbSession) -> tuple[uuid.UUID, Decimal]:
            row = db.get_one(TradingPosition, position_id)
            buy_price = row.buy_price or as_decimal(contract["buy_price"])
            row.buy_price = buy_price
            row.status = PositionStatus.CLOSED
            row.sell_price = sell_price
            row.net_result = sell_price - buy_price
            row.current_profit = row.net_result
            row.close_reason = row.close_reason or "deriv"
            sold_at = contract.get("sell_time")
            row.closed_at = (
                datetime.fromtimestamp(int(sold_at), UTC) if sold_at else datetime.now(UTC)
            )
            return row.session_id, row.net_result

        session_id, net = await self._journal.run(write)
        await self._journal.note(
            session_id,
            "position_closed",
            data={"net_result": str(net), "sell_price": str(sell_price)},
            position_id=position_id,
        )

    async def resolve_pending(self, session: BotSession) -> None:
        """Ordres en attente, après une issue inconnue ou un redémarrage."""
        pending = await self._journal.run(
            lambda db: list(
                db.scalars(
                    select(TradingPosition).where(
                        TradingPosition.account_id == session.account_id,
                        TradingPosition.status.in_(
                            [PositionStatus.OPENING, PositionStatus.UNKNOWN]
                        ),
                    )
                )
            )
        )
        for position in pending:
            if position.sent_at is None:
                # Panne avant l'envoi : l'ordre n'a jamais quitté SafeTrade.
                await self._void(position.id, session.id, "reconcile.never_sent")
                continue
            await self._resolve_sent(session, position)

    async def _resolve_sent(self, session: BotSession, position: TradingPosition) -> None:
        sent_at = position.sent_at
        if sent_at is None:
            return
        since = int(sent_at.timestamp()) - STATEMENT_MARGIN_SECONDS
        buys = await self._trading.buys_since(since)
        known = await self._journal.run(
            lambda db: set(
                db.scalars(
                    select(TradingPosition.contract_id).where(
                        TradingPosition.account_id == position.account_id,
                        TradingPosition.contract_id.is_not(None),
                    )
                )
            )
        )
        found = [
            b
            for b in buys
            if b.contract_id not in known
            and matches(b, position.symbol, position.direction, position.stake, position.multiplier)
            and b.amount == position.stake
        ]
        if found:
            buy = min(found, key=lambda b: b.transaction_time)
            await self._adopt(session, position, buy.contract_id, buy.amount)
            return
        age = datetime.now(UTC) - sent_at
        if age >= timedelta(seconds=STATEMENT_DELAY_SECONDS):
            await self._void(position.id, session.id, "reconcile.not_executed")

    async def _adopt(
        self, session: BotSession, position: TradingPosition, contract_id: int, amount: Decimal
    ) -> None:
        def write(db: DbSession) -> None:
            row = db.get_one(TradingPosition, position.id)
            row.status = PositionStatus.OPEN
            row.contract_id = contract_id
            row.buy_price = amount
            row.opened_at = datetime.now(UTC)

        await self._journal.run(write)
        await self._journal.note(
            session.id,
            "reconcile_adopted",
            data={"contract_id": contract_id},
            position_id=position.id,
        )

    async def reconcile(self, session: BotSession) -> None:
        """
        Au démarrage et après une coupure, avant toute nouvelle position. Une position clôturée
        pendant l'absence est enregistrée ; un contrat inconnu appartient au client et n'est
        jamais touché, mais il est tracé.
        """
        await self.resolve_pending(session)
        open_rows = await self._journal.run(
            lambda db: list(
                db.scalars(
                    select(TradingPosition).where(
                        TradingPosition.account_id == session.account_id,
                        TradingPosition.status == PositionStatus.OPEN,
                    )
                )
            )
        )
        for row in open_rows:
            if row.contract_id is None:
                continue
            contract = await self._trading.contract(row.contract_id)
            if contract.get("is_sold"):
                await self.finalize(row.id, contract)
        ours = {r.contract_id for r in open_rows}
        for contract in await self._trading.portfolio():
            contract_id = int(contract["contract_id"])
            if contract_id not in ours:
                await self._journal.note(
                    session.id, "reconcile_foreign", data={"contract_id": contract_id}
                )
        await self._journal.note(session.id, "reconciled", data={"open": len(open_rows)})
