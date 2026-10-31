"""
Flux de marché : une connexion publique, sans jeton, pour tout le serveur.

Marché fermé : Deriv refuse l'abonnement (`MarketIsClosed`). L'état vient donc de
`active_symbols`, relu régulièrement, et les actifs sont abonnés à leur ouverture.
Après une coupure, `DerivConnection` rétablit les flux ; ici, les ticks reçus deux fois sont
écartés, un trou est signalé et ses bougies relues. Un flux muet sur un marché ouvert, ou
dont la reprise a été refusée, est rouvert.
"""

import asyncio
import contextlib
import itertools
import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from app.broker.base import Broker, BrokerError, Message, Subscription
from app.market.store import STALE_SECONDS, Data, MarketStore

logger = logging.getLogger("safetrade.market")

GRANULARITIES = (60, 300, 900, 3600)
CANDLE_COUNT = 500
ASSETS_SECONDS = 60.0
SYNC_SECONDS = 5.0
# Une bougie toutes les 1,5 s au plus : 40 appels par minute, loin du quota de ce groupe.
CANDLE_PAUSE_SECONDS = 1.5
# Au-delà, deux ticks consécutifs ne sont pas continus (actifs mesurés : 1 à 2 s).
GAP_SECONDS = 15


def parse_tick(message: Message, symbol: str, now: float) -> Data | None:
    tick = message.get("tick")
    if not isinstance(tick, dict) or tick.get("symbol") != symbol:
        return None
    try:
        quote, epoch = float(tick["quote"]), int(tick["epoch"])
    except (KeyError, TypeError, ValueError):
        return None
    if quote <= 0 or epoch <= 0:
        return None
    return {
        "symbol": symbol,
        "quote": quote,
        "bid": tick.get("bid"),
        "ask": tick.get("ask"),
        "epoch": epoch,
        "received_at": now,
    }


def valid_candles(candles: Any) -> bool:
    """Bougies strictement ordonnées, plus-haut et plus-bas cohérents."""
    if not isinstance(candles, list) or not candles:
        return False
    try:
        epochs = [c["epoch"] for c in candles]
        coherent = all(
            0 < c["low"] <= min(c["open"], c["close"]) and max(c["open"], c["close"]) <= c["high"]
            for c in candles
        )
    except (KeyError, TypeError):
        return False
    return coherent and all(a < b for a, b in itertools.pairwise(epochs))


class MarketFeed:
    def __init__(
        self,
        broker: Broker,
        store: MarketStore,
        symbols: Sequence[str],
        *,
        clock: Callable[[], float] = time.time,
        candle_pause: float = CANDLE_PAUSE_SECONDS,
    ) -> None:
        self._broker = broker
        self._store = store
        self._symbols = list(symbols)
        self._clock = clock
        self._candle_pause = candle_pause
        self._streams: dict[str, Subscription] = {}
        self._subscribed_at: dict[str, float] = {}
        self._last_epoch: dict[str, int] = {}
        self._last_received: dict[str, float] = {}
        self._open: set[str] = set()
        self._assets_read_at: float | None = None
        self._urgent: deque[tuple[str, int]] = deque()
        self.ticks_dropped = 0

    async def run(self) -> None:
        await self._broker.start()
        try:
            await asyncio.gather(
                self._forever(self.sync, SYNC_SECONDS),
                self._forever(self.refresh_next_candles, self._candle_pause),
            )
        finally:
            await self._broker.stop()

    @staticmethod
    async def _forever(step: Callable[[], Awaitable[None]], pause: float) -> None:
        while True:
            try:
                await step()
            except BrokerError as exc:
                # Coupure ou refus passager : le cycle suivant recommence.
                logger.warning("flux de marché : %s", type(exc).__name__)
            await asyncio.sleep(pause)

    async def sync(self) -> None:
        now = self._clock()
        if self._assets_read_at is None or now - self._assets_read_at >= ASSETS_SECONDS:
            await self.refresh_assets()
        for symbol in self._symbols:
            await self._align(symbol, now)

    async def refresh_assets(self) -> None:
        response = await self._broker.request("active_symbols", {"active_symbols": "brief"})
        known = {row["underlying_symbol"]: row for row in response["active_symbols"]}
        assets = [
            {
                "symbol": symbol,
                "name": row["underlying_symbol_name"],
                "market": row["market"],
                "pip_size": row["pip_size"],
                "exchange_is_open": bool(row["exchange_is_open"]),
                "is_trading_suspended": bool(row["is_trading_suspended"]),
            }
            for symbol in self._symbols
            if (row := known.get(symbol)) is not None
        ]
        for symbol in set(self._symbols) - known.keys():
            logger.warning("actif absent chez Deriv : %s", symbol)
        self._open = {
            a["symbol"] for a in assets if a["exchange_is_open"] and not a["is_trading_suspended"]
        }
        await self._store.put_assets(assets)
        self._assets_read_at = self._clock()

    async def _align(self, symbol: str, now: float) -> None:
        stream = self._streams.get(symbol)
        if symbol not in self._open:
            if stream is not None:
                await self._close(symbol)
            return
        if stream is None:
            await self._open_stream(symbol, now)
            return
        seen = self._last_received.get(symbol, self._subscribed_at[symbol])
        if now - seen > STALE_SECONDS:
            logger.warning("flux muet, réouverture : %s", symbol)
            await self._close(symbol)
            await self._open_stream(symbol, now)

    async def _open_stream(self, symbol: str, now: float) -> None:
        async def on_tick(message: Message) -> None:
            await self.handle_tick(symbol, message)

        self._subscribed_at[symbol] = now
        self._last_received.pop(symbol, None)
        self._streams[symbol] = await self._broker.subscribe("ticks", {"ticks": symbol}, on_tick)

    async def _close(self, symbol: str) -> None:
        stream = self._streams.pop(symbol)
        with contextlib.suppress(BrokerError):
            await stream.cancel()

    async def handle_tick(self, symbol: str, message: Message) -> None:
        now = self._clock()
        tick = parse_tick(message, symbol, now)
        if tick is None:
            self.ticks_dropped += 1
            logger.warning("tick incohérent écarté : %s", symbol)
            return
        previous = self._last_epoch.get(symbol)
        if previous is not None and tick["epoch"] <= previous:
            self.ticks_dropped += 1
            return
        self._last_epoch[symbol] = tick["epoch"]
        self._last_received[symbol] = now
        await self._store.put_tick(tick)
        if previous is not None and tick["epoch"] - previous > GAP_SECONDS:
            logger.warning("trou de %d s : %s", tick["epoch"] - previous, symbol)
            await self._store.publish(
                {"type": "gap", "symbol": symbol, "from": previous, "to": tick["epoch"]}
            )
            self._urgent.extend((symbol, g) for g in GRANULARITIES)

    async def refresh_next_candles(self) -> None:
        if not self._urgent:
            self._urgent.extend((s, g) for s in self._symbols for g in GRANULARITIES)
        symbol, granularity = self._urgent.popleft()
        response = await self._broker.request(
            "ticks_history",
            {
                "ticks_history": symbol,
                "style": "candles",
                "granularity": granularity,
                "count": CANDLE_COUNT,
                "end": "latest",
            },
        )
        candles = response.get("candles")
        if not isinstance(candles, list) or not valid_candles(candles):
            logger.warning("bougies incohérentes écartées : %s %d", symbol, granularity)
            return
        await self._store.put_candles(symbol, granularity, candles)
