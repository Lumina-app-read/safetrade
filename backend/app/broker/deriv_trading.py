"""
Opérations de trading sur un compte Deriv. Contrats multiplicateurs uniquement.

Les règles mesurées en démo vivent ici (docs/decisions/essais-demo-2026-10-31.md) : le stop
loss n'est jamais retiré, `BetExpired` à la vente veut dire « déjà clôturé », un refus
`RateLimit` sur une lecture s'attend, sur un ordre il remonte sans nouvel essai.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.broker.base import (
    ApiRejectedError,
    Broker,
    Message,
    MessageHandler,
    Purchase,
    RateLimitedError,
    Subscription,
)

CONTRACT_TYPES = {"up": "MULTUP", "down": "MULTDOWN"}
READ_ATTEMPTS = 3
READ_PAUSE_SECONDS = 2.0
ALREADY_CLOSED = frozenset({"BetExpired"})


@dataclass(frozen=True)
class Buy:
    contract_id: int
    amount: Decimal
    transaction_time: int
    shortcode: str


class DerivTrading:
    def __init__(self, broker: Broker, *, read_pause: float = READ_PAUSE_SECONDS) -> None:
        self._broker = broker
        self._read_pause = read_pause

    @property
    def connected(self) -> bool:
        return self._broker.connected

    @property
    def reconnections(self) -> int:
        return self._broker.reconnections

    async def _read(self, call: str, payload: Message) -> Message:
        for attempt in range(READ_ATTEMPTS):
            try:
                return await self._broker.request(call, payload)
            except RateLimitedError:
                if attempt == READ_ATTEMPTS - 1:
                    raise
                await asyncio.sleep(self._read_pause * (attempt + 1))
        raise AssertionError("inatteignable")

    async def proposal(
        self, symbol: str, direction: str, stake: Decimal, multiplier: int, stop_loss: Decimal
    ) -> Message:
        response = await self._broker.request(
            "proposal",
            {
                "proposal": 1,
                "amount": float(stake),
                "basis": "stake",
                "contract_type": CONTRACT_TYPES[direction],
                "currency": "USD",
                "multiplier": multiplier,
                "underlying_symbol": symbol,
                "limit_order": {"stop_loss": float(stop_loss)},
            },
        )
        proposal: Message = response["proposal"]
        return proposal

    async def buy(self, proposal_id: str, max_price: float) -> Purchase:
        return await self._broker.buy(proposal_id, max_price)

    async def sell(self, contract_id: int) -> Message | None:
        """Vente au marché. None : Deriv venait de clôturer la position."""
        try:
            response = await self._broker.request("sell", {"sell": contract_id, "price": 0})
        except ApiRejectedError as exc:
            if exc.code in ALREADY_CLOSED:
                return None
            raise
        sold: Message = response["sell"]
        return sold

    async def update_stop(self, contract_id: int, stop_loss: Decimal) -> Message:
        """Déplace le stop. `None` chez Deriv le retirerait : refusé ici, sans exception."""
        if stop_loss is None or stop_loss <= 0:
            raise ValueError("stop loss obligatoire")
        response = await self._broker.request(
            "contract_update",
            {
                "contract_update": 1,
                "contract_id": contract_id,
                "limit_order": {"stop_loss": float(stop_loss)},
            },
        )
        updated: Message = response["contract_update"]
        return updated

    async def contract(self, contract_id: int) -> Message:
        response = await self._read(
            "proposal_open_contract", {"proposal_open_contract": 1, "contract_id": contract_id}
        )
        state: Message = response["proposal_open_contract"]
        return state

    async def watch(self, contract_id: int, handler: MessageHandler) -> Subscription:
        return await self._broker.subscribe(
            "proposal_open_contract",
            {"proposal_open_contract": 1, "contract_id": contract_id},
            handler,
        )

    async def balance(self) -> Decimal:
        response = await self._read("balance", {"balance": 1})
        return Decimal(str(response["balance"]["balance"]))

    async def portfolio(self) -> list[Message]:
        response = await self._read("portfolio", {"portfolio": 1})
        contracts: list[Message] = response["portfolio"].get("contracts", [])
        return contracts

    async def buys_since(self, date_from: int) -> list[Buy]:
        response = await self._read(
            "statement",
            {
                "statement": 1,
                "description": 1,
                "action_type": "buy",
                "date_from": date_from,
                "limit": 50,
            },
        )
        rows: list[dict[str, Any]] = response["statement"].get("transactions", [])
        return [
            Buy(
                contract_id=int(row["contract_id"]),
                amount=abs(Decimal(str(row["amount"]))),
                transaction_time=int(row["transaction_time"]),
                shortcode=str(row.get("shortcode", "")),
            )
            for row in rows
        ]


Guard = Callable[[], Awaitable[bool]]


def matches(buy: Buy, symbol: str, direction: str, stake: Decimal, multiplier: int) -> bool:
    """Shortcode mesuré : MULTUP_1HZ100V_1.00_400_1793435127_..."""
    prefix = f"{CONTRACT_TYPES[direction]}_{symbol}_{stake:.2f}_{multiplier}_"
    return buy.shortcode.startswith(prefix)
