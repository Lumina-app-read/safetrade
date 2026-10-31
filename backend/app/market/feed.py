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
from collections import Counter, deque
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from app.broker.base import ApiRejectedError, Broker, BrokerError, Message, Subscription
from app.market.quality import MAX_FUTURE_SECONDS
from app.market.store import STALE_SECONDS, Data, MarketStore

logger = logging.getLogger("safetrade.market")

GRANULARITIES = (60, 300, 900, 3600)
CANDLE_COUNT = 500
ASSETS_SECONDS = 60.0
# Cycle peu coûteux : les appels à Deriv restent espacés par ASSETS_SECONDS.
SYNC_SECONDS = 1.0
# Une bougie toutes les 1,5 s au plus : 40 appels par minute, loin du quota de ce groupe.
CANDLE_PAUSE_SECONDS = 1.5
# Au-delà, deux ticks consécutifs ne sont pas continus (actifs mesurés : 1 à 2 s).
GAP_SECONDS = 15
REPORT_SECONDS = 5.0
# Interruption prolongée : alerte, puis arrêt des bots via le statut des actifs.
ALERT_DISCONNECTED_SECONDS = 60.0
ALERT_ERRORS_PER_REPORT = 5


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


def active_alerts(health: Data, now: float) -> set[str]:
    """Alertes en cours : fonction pure, évaluée à chaque rapport."""
    alerts: set[str] = set()
    down_since = health["disconnected_since"]
    if down_since is not None and now - down_since >= ALERT_DISCONNECTED_SECONDS:
        alerts.add("market.feed_disconnected")
    if health["silent_symbols"]:
        alerts.add("market.symbols_silent")
    if health["errors_since_last_report"] >= ALERT_ERRORS_PER_REPORT:
        alerts.add("market.deriv_errors")
    return alerts


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
        self._last_gap: dict[str, int] = {}
        self.started_at = clock()
        self.ticks_received = 0
        self.ticks_dropped = 0
        self.gaps = 0
        self.errors: Counter[str] = Counter()
        self._errors_reported = 0
        self.round_trip_ms: float | None = None
        self.clock_offset_seconds: float | None = None
        self._disconnected_since: float | None = None
        self._raised: set[str] = set()

    async def run(self) -> None:
        await self._broker.start()
        loops = [
            asyncio.ensure_future(self._forever(step, pause))
            for step, pause in (
                (self.sync, SYNC_SECONDS),
                (self.refresh_next_candles, self._candle_pause),
                (self.report, REPORT_SECONDS),
            )
        ]
        try:
            # Une boucle tombée, par exemple sur la perte du bail, arrête tout le flux.
            done, _ = await asyncio.wait(loops, return_when=asyncio.FIRST_EXCEPTION)
            for loop in done:
                loop.result()
        finally:
            for loop in loops:
                loop.cancel()
            await asyncio.gather(*loops, return_exceptions=True)
            await self._broker.stop()

    async def _forever(self, step: Callable[[], Awaitable[None]], pause: float) -> None:
        while True:
            try:
                await step()
            except BrokerError as exc:
                # Coupure ou refus passager : le cycle suivant recommence.
                code = exc.code if isinstance(exc, ApiRejectedError) else type(exc).__name__
                self.errors[code] += 1
                logger.warning("erreur Deriv", extra={"event": "market.deriv_error", "code": code})
            await asyncio.sleep(pause)

    async def sync(self) -> None:
        # Connexion en cours d'ouverture ou tombée : rien à tenter, ce n'est pas une erreur.
        if not self._broker.connected:
            return
        now = self._clock()
        if self._assets_read_at is None or now - self._assets_read_at >= ASSETS_SECONDS:
            await self.probe()
            await self.refresh_assets()
        for symbol in self._symbols:
            await self._align(symbol, now)

    async def probe(self) -> None:
        """Latence réelle et écart d'horloge avec Deriv."""
        started = time.perf_counter()
        response = await self._broker.request("time", {"time": 1})
        self.round_trip_ms = round((time.perf_counter() - started) * 1000, 1)
        self.clock_offset_seconds = round(self._clock() - float(response["time"]), 2)

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
            logger.warning("actif absent", extra={"event": "market.unknown", "symbol": symbol})
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
            logger.warning("flux rouvert", extra={"event": "market.silent", "symbol": symbol})
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
            logger.warning("tick écarté", extra={"event": "market.tick_invalid", "symbol": symbol})
            return
        if tick["epoch"] > now + MAX_FUTURE_SECONDS:
            self.ticks_dropped += 1
            logger.warning("tick futur", extra={"event": "market.tick_future", "symbol": symbol})
            return
        previous = self._last_epoch.get(symbol)
        if previous is not None and tick["epoch"] <= previous:
            self.ticks_dropped += 1
            return
        self._last_epoch[symbol] = tick["epoch"]
        self._last_received[symbol] = now
        self.ticks_received += 1
        gap = previous is not None and tick["epoch"] - previous > GAP_SECONDS
        if gap:
            self._last_gap[symbol] = tick["epoch"]
        tick["last_gap_epoch"] = self._last_gap.get(symbol)
        await self._store.put_tick(tick)
        if gap:
            self.gaps += 1
            logger.warning(
                "trou de données",
                extra={
                    "event": "market.gap",
                    "symbol": symbol,
                    "seconds": tick["epoch"] - (previous or 0),
                },
            )
            await self._store.publish(
                {"type": "gap", "symbol": symbol, "from": previous, "to": tick["epoch"]}
            )
            self._urgent.extend((symbol, g) for g in GRANULARITIES)

    async def refresh_next_candles(self) -> None:
        if not self._broker.connected:
            return
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
            logger.warning(
                "bougies écartées",
                extra={
                    "event": "market.candles_invalid",
                    "symbol": symbol,
                    "granularity": granularity,
                },
            )
            return
        await self._store.put_candles(symbol, granularity, candles)

    def health(self, now: float) -> Data:
        connected = self._broker.connected
        if connected:
            self._disconnected_since = None
        elif self._disconnected_since is None:
            self._disconnected_since = now
        errors = sum(self.errors.values())
        burst = errors - self._errors_reported
        self._errors_reported = errors
        return {
            "reported_at": now,
            "started_at": self.started_at,
            "connected": connected,
            "disconnected_since": self._disconnected_since,
            "reconnections": self._broker.reconnections,
            "ticks_received": self.ticks_received,
            "ticks_dropped": self.ticks_dropped,
            "gaps": self.gaps,
            "errors": dict(self.errors),
            "errors_since_last_report": burst,
            "round_trip_ms": self.round_trip_ms,
            "clock_offset_seconds": self.clock_offset_seconds,
            "subscribed": sorted(self._streams),
            "silent_symbols": sorted(
                s
                for s in self._open & self._streams.keys()
                if now - self._last_received.get(s, self._subscribed_at[s]) > STALE_SECONDS
            ),
        }

    async def report(self) -> None:
        """État publié même sans connexion : c'est là qu'il compte le plus."""
        now = self._clock()
        health = self.health(now)
        await self._store.put_health(health)
        current = active_alerts(health, now)
        for code in sorted(current - self._raised):
            logger.error("alerte", extra={"event": "alert.raised", "code": code})
            await self._store.push_alert({"code": code, "state": "raised", "at": now})
        for code in sorted(self._raised - current):
            logger.warning("fin d'alerte", extra={"event": "alert.resolved", "code": code})
            await self._store.push_alert({"code": code, "state": "resolved", "at": now})
        self._raised = current
