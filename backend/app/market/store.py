"""
Données de marché partagées : le flux les écrit, l'API les lit.

Une seule connexion à Deriv alimente tout le serveur ; l'API ne parle jamais à Deriv pour
les prix. Redis garde le dernier état et diffuse les événements.
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any, Protocol, cast

from redis.asyncio import Redis

Data = dict[str, Any]

CHANNEL = "market:events"
LISTEN_SECONDS = 1.0

# Sans tick récent, un prix n'est plus considéré comme direct, même marché ouvert.
STALE_SECONDS = 30.0
# Liste des actifs non rafraîchie : le flux lui-même est tombé.
FEED_DOWN_SECONDS = 180.0


class MarketStore(Protocol):
    async def put_assets(self, assets: list[Data]) -> None: ...
    async def get_assets(self) -> Data | None: ...
    async def put_tick(self, tick: Data) -> None: ...
    async def get_ticks(self, symbols: list[str]) -> dict[str, Data]: ...
    async def put_candles(self, symbol: str, granularity: int, candles: list[Data]) -> None: ...
    async def get_candles(self, symbol: str, granularity: int) -> Data | None: ...
    async def publish(self, event: Data) -> None: ...
    def listen(self) -> AsyncIterator[Data | None]:
        """Événements diffusés, ou None à vide. Le premier None confirme l'écoute."""
        ...


def asset_status(asset: Data, tick: Data | None, updated_at: float, now: float) -> str:
    """Seul le statut `live` autorise à trader cet actif."""
    if now - updated_at > FEED_DOWN_SECONDS:
        return "unavailable"
    if asset["is_trading_suspended"]:
        return "suspended"
    if not asset["exchange_is_open"]:
        return "closed"
    if tick is None or now - tick["received_at"] > STALE_SECONDS:
        return "stale"
    return "live"


class MemoryMarketStore:
    """Tests et développement sans Redis."""

    def __init__(self) -> None:
        self._assets: Data | None = None
        self._ticks: dict[str, Data] = {}
        self._candles: dict[tuple[str, int], Data] = {}
        self._listeners: list[asyncio.Queue[Data]] = []

    async def put_assets(self, assets: list[Data]) -> None:
        self._assets = {"updated_at": time.time(), "assets": assets}

    async def get_assets(self) -> Data | None:
        return self._assets

    async def put_tick(self, tick: Data) -> None:
        self._ticks[tick["symbol"]] = tick
        await self.publish({"type": "tick", **tick})

    async def get_ticks(self, symbols: list[str]) -> dict[str, Data]:
        return {s: self._ticks[s] for s in symbols if s in self._ticks}

    async def put_candles(self, symbol: str, granularity: int, candles: list[Data]) -> None:
        self._candles[symbol, granularity] = {"updated_at": time.time(), "candles": candles}

    async def get_candles(self, symbol: str, granularity: int) -> Data | None:
        return self._candles.get((symbol, granularity))

    async def publish(self, event: Data) -> None:
        for queue in self._listeners:
            queue.put_nowait(event)

    async def listen(self) -> AsyncIterator[Data | None]:
        queue: asyncio.Queue[Data] = asyncio.Queue()
        self._listeners.append(queue)
        try:
            yield None
            while True:
                try:
                    yield await asyncio.wait_for(queue.get(), LISTEN_SECONDS)
                except TimeoutError:
                    yield None
        finally:
            self._listeners.remove(queue)


class RedisMarketStore:
    def __init__(self, client: Redis) -> None:
        self._client = client

    async def _read(self, key: str) -> Data | None:
        raw = await self._client.get(key)
        return cast("Data", json.loads(raw)) if raw else None

    async def put_assets(self, assets: list[Data]) -> None:
        value = json.dumps({"updated_at": time.time(), "assets": assets})
        await self._client.set("market:assets", value)

    async def get_assets(self) -> Data | None:
        return await self._read("market:assets")

    async def put_tick(self, tick: Data) -> None:
        await self._client.set(f"market:tick:{tick['symbol']}", json.dumps(tick))
        await self.publish({"type": "tick", **tick})

    async def get_ticks(self, symbols: list[str]) -> dict[str, Data]:
        if not symbols:
            return {}
        rows = await self._client.mget([f"market:tick:{s}" for s in symbols])
        return {s: json.loads(raw) for s, raw in zip(symbols, rows, strict=True) if raw}

    async def put_candles(self, symbol: str, granularity: int, candles: list[Data]) -> None:
        value = json.dumps({"updated_at": time.time(), "candles": candles})
        await self._client.set(f"market:candles:{symbol}:{granularity}", value)

    async def get_candles(self, symbol: str, granularity: int) -> Data | None:
        return await self._read(f"market:candles:{symbol}:{granularity}")

    async def publish(self, event: Data) -> None:
        await self._client.publish(CHANNEL, json.dumps(event))

    async def listen(self) -> AsyncIterator[Data | None]:
        async with self._client.pubsub() as pubsub:
            await pubsub.subscribe(CHANNEL)
            yield None
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=LISTEN_SECONDS
                )
                yield json.loads(message["data"]) if message else None
