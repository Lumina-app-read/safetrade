"""
Données de marché partagées : le flux les écrit, l'API les lit.

Une seule connexion à Deriv alimente tout le serveur ; l'API ne parle jamais à Deriv pour
les prix. Redis garde le dernier état et diffuse les événements.
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator, Awaitable
from typing import Any, Protocol, cast

from redis.asyncio import Redis

from app.market.lease import LEASE_KEY, LeadershipLostError

Data = dict[str, Any]

CHANNEL = "market:events"
LISTEN_SECONDS = 1.0

# Sans tick récent, un prix n'est plus considéré comme direct, même marché ouvert.
STALE_SECONDS = 30.0
# Liste des actifs non rafraîchie : le flux lui-même est tombé.
FEED_DOWN_SECONDS = 180.0
MAX_ALERTS = 200


class MarketStore(Protocol):
    async def put_assets(self, assets: list[Data]) -> None: ...
    async def get_assets(self) -> Data | None: ...
    async def put_tick(self, tick: Data) -> None: ...
    async def get_ticks(self, symbols: list[str]) -> dict[str, Data]: ...
    async def put_candles(self, symbol: str, granularity: int, candles: list[Data]) -> None: ...
    async def get_candles(self, symbol: str, granularity: int) -> Data | None: ...
    async def demand(self, symbol: str) -> None: ...
    async def get_demand(self, since: float) -> list[str]: ...
    async def publish(self, event: Data) -> None: ...
    async def put_health(self, health: Data) -> None: ...
    async def get_health(self) -> Data | None: ...
    async def push_alert(self, alert: Data) -> None: ...
    async def get_alerts(self) -> list[Data]: ...
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
    # Date de Deriv comprise : un vieux tick rejoué par une reprise ne paraît pas frais.
    if tick is None or now - min(tick["epoch"], tick["received_at"]) > STALE_SECONDS:
        return "stale"
    return "live"


class MemoryMarketStore:
    """Tests et développement sans Redis."""

    def __init__(self) -> None:
        self._assets: Data | None = None
        self._ticks: dict[str, Data] = {}
        self._candles: dict[tuple[str, int], Data] = {}
        self._demand: dict[str, float] = {}
        self._listeners: list[asyncio.Queue[Data]] = []
        self._health: Data | None = None
        self._alerts: list[Data] = []

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

    async def demand(self, symbol: str) -> None:
        self._demand[symbol] = time.time()

    async def get_demand(self, since: float) -> list[str]:
        return [symbol for symbol, at in self._demand.items() if at >= since]

    async def publish(self, event: Data) -> None:
        for queue in self._listeners:
            queue.put_nowait(event)

    async def put_health(self, health: Data) -> None:
        self._health = health

    async def get_health(self) -> Data | None:
        return self._health

    async def push_alert(self, alert: Data) -> None:
        self._alerts = [alert, *self._alerts][:MAX_ALERTS]

    async def get_alerts(self) -> list[Data]:
        return self._alerts

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


# Écriture et bail vérifiés d'un seul geste : aucun tick d'un ancien responsable ne passe.
_GUARDED_WRITE = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
if ARGV[2] ~= '' then redis.call('SET', KEYS[2], ARGV[2]) end
if ARGV[3] ~= '' then redis.call('PUBLISH', ARGV[4], ARGV[3]) end
return 1
"""

_GUARDED_ALERT = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
redis.call('LPUSH', KEYS[2], ARGV[2])
redis.call('LTRIM', KEYS[2], 0, ARGV[3])
return 1
"""


class RedisMarketStore:
    """
    Lecture seule sans `owner` ; avec `owner`, écrit tant que ce worker tient le bail.
    `demand` fait exception : c'est une requête vers le flux, pas une donnée de marché.
    """

    def __init__(self, client: Redis, owner: str | None = None) -> None:
        self._client = client
        self._owner = owner
        self._write_script = client.register_script(_GUARDED_WRITE)
        self._alert_script = client.register_script(_GUARDED_ALERT)

    async def _write(self, key: str, value: str, event: str = "") -> None:
        if self._owner is None:
            raise LeadershipLostError
        written = await self._write_script(
            keys=[LEASE_KEY, key], args=[self._owner, value, event, CHANNEL]
        )
        if not written:
            raise LeadershipLostError

    async def _read(self, key: str) -> Data | None:
        raw = await self._client.get(key)
        return cast("Data", json.loads(raw)) if raw else None

    async def put_assets(self, assets: list[Data]) -> None:
        await self._write(
            "market:assets", json.dumps({"updated_at": time.time(), "assets": assets})
        )

    async def get_assets(self) -> Data | None:
        return await self._read("market:assets")

    async def put_tick(self, tick: Data) -> None:
        await self._write(
            f"market:tick:{tick['symbol']}",
            json.dumps(tick),
            json.dumps({"type": "tick", **tick}),
        )

    async def get_ticks(self, symbols: list[str]) -> dict[str, Data]:
        if not symbols:
            return {}
        rows = await self._client.mget([f"market:tick:{s}" for s in symbols])
        return {s: json.loads(raw) for s, raw in zip(symbols, rows, strict=True) if raw}

    async def put_candles(self, symbol: str, granularity: int, candles: list[Data]) -> None:
        value = json.dumps({"updated_at": time.time(), "candles": candles})
        await self._write(f"market:candles:{symbol}:{granularity}", value)

    async def get_candles(self, symbol: str, granularity: int) -> Data | None:
        return await self._read(f"market:candles:{symbol}:{granularity}")

    async def demand(self, symbol: str) -> None:
        await self._client.zadd("market:demand", {symbol: time.time()})

    async def get_demand(self, since: float) -> list[str]:
        rows = await self._client.zrangebyscore("market:demand", since, "+inf")
        return [raw.decode() for raw in rows]

    async def publish(self, event: Data) -> None:
        await self._write(LEASE_KEY, "", json.dumps(event))

    async def put_health(self, health: Data) -> None:
        await self._write("monitor:feed", json.dumps(health))

    async def get_health(self) -> Data | None:
        return await self._read("monitor:feed")

    async def push_alert(self, alert: Data) -> None:
        written = await self._alert_script(
            keys=[LEASE_KEY, "monitor:alerts"],
            args=[self._owner or "", json.dumps(alert), MAX_ALERTS - 1],
        )
        if not written:
            raise LeadershipLostError

    async def get_alerts(self) -> list[Data]:
        rows = await cast("Awaitable[list[bytes]]", self._client.lrange("monitor:alerts", 0, -1))
        return [json.loads(raw) for raw in rows]

    async def listen(self) -> AsyncIterator[Data | None]:
        async with self._client.pubsub() as pubsub:
            await pubsub.subscribe(CHANNEL)
            yield None
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=LISTEN_SECONDS
                )
                yield json.loads(message["data"]) if message else None
