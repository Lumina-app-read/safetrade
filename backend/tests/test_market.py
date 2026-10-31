"""Flux de marché (étape 2.5) : faux broker, aucun appel à Deriv."""

import asyncio
import json
import os
import uuid
from collections import Counter
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from redis.asyncio import Redis
from sqlalchemy import Engine, text
from sqlalchemy.orm import sessionmaker

from app.auth.mailer import MemoryMailer
from app.auth.rate_limit import MemoryFailureCounter
from app.broker.base import ApiRejectedError, ConnectionLostError, Message, MessageHandler
from app.config import Settings
from app.main import create_app
from app.market.feed import GAP_SECONDS, GRANULARITIES, MarketFeed, valid_candles
from app.market.lease import LEASE_KEY
from app.market.router import MAX_STREAMS_PER_USER, stream_events
from app.market.store import (
    FEED_DOWN_SECONDS,
    STALE_SECONDS,
    MarketStore,
    MemoryMarketStore,
    RedisMarketStore,
    asset_status,
)
from tests.conftest import requires_db

ORIGIN = "http://127.0.0.1:13000"
PASSWORD = "Correct-Horse-42"


def row(symbol: str, *, opened: int = 1, suspended: int = 0) -> dict[str, Any]:
    return {
        "underlying_symbol": symbol,
        "underlying_symbol_name": symbol,
        "market": "synthetic_index",
        "pip_size": 0.01,
        "exchange_is_open": opened,
        "is_trading_suspended": suspended,
    }


class FakeStream:
    def __init__(self, broker: "FakeBroker", symbol: str) -> None:
        self.broker = broker
        self.symbol = symbol

    async def cancel(self) -> None:
        self.broker.handlers.pop(self.symbol, None)


class FakeBroker:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.handlers: dict[str, MessageHandler] = {}
        self.subscriptions: list[str] = []
        self.history: list[Message] = []
        self.candles: Any = [{"epoch": 60, "open": 2.0, "high": 3.0, "low": 1.0, "close": 2.5}]
        self.fail_with: Exception | None = None
        self.connected = True
        self.reconnections = 0
        self.stopped = False

    async def start(self) -> None: ...

    async def stop(self) -> None:
        self.stopped = True

    async def request(self, call: str, payload: Message) -> Message:
        if self.fail_with:
            raise self.fail_with
        if call == "active_symbols":
            return {"active_symbols": self.rows}
        if call == "time":
            return {"time": 999}
        if call == "contracts_for":
            return {"contracts_for": {"available": []}}
        self.history.append(payload)
        return {"candles": self.candles}

    async def subscribe(self, call: str, payload: Message, handler: MessageHandler) -> FakeStream:
        symbol = payload["ticks"]
        if not next(r for r in self.rows if r["underlying_symbol"] == symbol)["exchange_is_open"]:
            raise ApiRejectedError("MarketIsClosed", "fermé")
        self.subscriptions.append(symbol)
        self.handlers[symbol] = handler
        return FakeStream(self, symbol)

    async def buy(self, proposal_id: str, max_price: float) -> Any:
        raise AssertionError("le flux de marché n'achète jamais")


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def tick(symbol: str, epoch: int, quote: float = 100.0) -> Message:
    return {"tick": {"symbol": symbol, "quote": quote, "epoch": epoch, "bid": 99.5, "ask": 100.5}}


def feed_with(
    rows: list[dict[str, Any]],
) -> tuple[MarketFeed, FakeBroker, MemoryMarketStore, Clock]:
    broker, store, clock = FakeBroker(rows), MemoryMarketStore(), Clock()
    symbols = [r["underlying_symbol"] for r in rows]
    return MarketFeed(broker, store, symbols, clock=clock, candle_pause=0), broker, store, clock


def test_five_assets_live_and_closed_market_not_subscribed() -> None:
    async def main() -> None:
        symbols = ["A", "B", "C", "D", "E"]
        rows = [*[row(s) for s in symbols], row("GOLD", opened=0)]
        feed, broker, store, _ = feed_with(rows)
        await feed.sync()
        assert sorted(broker.subscriptions) == symbols
        for symbol in symbols:
            await broker.handlers[symbol](tick(symbol, 10))
        assert set(await store.get_ticks(symbols)) == set(symbols)
        state = await store.get_assets()
        assert state is not None
        gold = next(a for a in state["assets"] if a["symbol"] == "GOLD")
        assert gold["exchange_is_open"] is False

    asyncio.run(main())


def test_market_opening_subscribes_and_closing_unsubscribes() -> None:
    async def main() -> None:
        rows = [row("GOLD", opened=0)]
        feed, broker, _, clock = feed_with(rows)
        await feed.sync()
        assert broker.subscriptions == []
        rows[0]["exchange_is_open"] = 1
        clock.now += 61
        await feed.sync()
        assert broker.subscriptions == ["GOLD"]
        rows[0]["exchange_is_open"] = 0
        clock.now += 61
        await feed.sync()
        assert broker.handlers == {}

    asyncio.run(main())


def test_unknown_symbol_is_left_out() -> None:
    async def main() -> None:
        broker, store = FakeBroker([row("A")]), MemoryMarketStore()
        await MarketFeed(broker, store, ["A", "NOPE"]).refresh_assets()
        state = await store.get_assets()
        assert state is not None
        assert [a["symbol"] for a in state["assets"]] == ["A"]

    asyncio.run(main())


def test_duplicate_old_and_malformed_ticks_are_dropped() -> None:
    async def main() -> None:
        feed, broker, store, _ = feed_with([row("A")])
        await feed.sync()
        handler = broker.handlers["A"]
        await handler(tick("A", 10, 100.0))
        await handler(tick("A", 10, 101.0))  # même seconde, déjà reçue avant la reprise
        await handler(tick("A", 9, 102.0))
        await handler(tick("B", 11, 103.0))  # mauvais actif
        await handler(tick("A", 12, -1.0))
        await handler({"tick": {"symbol": "A", "quote": "x", "epoch": 13}})
        assert (await store.get_ticks(["A"]))["A"]["quote"] == 100.0
        assert feed.ticks_dropped == 5

    asyncio.run(main())


def test_gap_is_signalled_and_candles_reread_first() -> None:
    async def main() -> None:
        feed, broker, store, _ = feed_with([row("A"), row("B")])
        await feed.sync()
        await broker.handlers["A"](tick("A", 10))
        events = store.listen()
        await anext(events)
        await broker.handlers["A"](tick("A", 11 + GAP_SECONDS))
        assert (await anext(events))["type"] == "tick"  # type: ignore[index]
        gap = await anext(events)
        assert gap == {"type": "gap", "symbol": "A", "from": 10, "to": 11 + GAP_SECONDS}
        await events.aclose()  # type: ignore[attr-defined]
        for _ in GRANULARITIES:
            await feed.refresh_next_candles()
        assert {p["ticks_history"] for p in broker.history} == {"A"}

    asyncio.run(main())


def test_silent_stream_is_reopened() -> None:
    async def main() -> None:
        feed, broker, _, clock = feed_with([row("A")])
        await feed.sync()
        await broker.handlers["A"](tick("A", 10))
        clock.now += STALE_SECONDS + 1
        await feed.sync()
        assert broker.subscriptions == ["A", "A"]
        await feed.sync()
        assert broker.subscriptions == ["A", "A"]

    asyncio.run(main())


def test_step_failure_does_not_stop_the_feed() -> None:
    async def main() -> None:
        feed, broker, _, _ = feed_with([row("A")])
        broker.fail_with = ConnectionLostError()
        calls = 0

        async def step() -> None:
            nonlocal calls
            calls += 1
            await feed.sync()

        task = asyncio.create_task(feed._forever(step, 0))
        while calls < 3:
            await asyncio.sleep(0)
        task.cancel()
        assert calls >= 3

    asyncio.run(main())


@pytest.mark.parametrize(
    "candles",
    [
        [],
        None,
        [{"epoch": 60}],
        [{"epoch": 60, "open": 2.0, "high": 1.5, "low": 1.0, "close": 2.0}],
        [
            {"epoch": 60, "open": 2.0, "high": 3.0, "low": 1.0, "close": 2.0},
            {"epoch": 60, "open": 2.0, "high": 3.0, "low": 1.0, "close": 2.0},
        ],
    ],
)
def test_incoherent_candles_are_not_stored(candles: Any) -> None:
    assert not valid_candles(candles)

    async def main() -> None:
        feed, broker, store, _ = feed_with([row("A")])
        broker.candles = candles
        await feed.refresh_next_candles()
        assert await store.get_candles("A", GRANULARITIES[0]) is None

    asyncio.run(main())


def test_candles_are_stored_for_every_granularity() -> None:
    async def main() -> None:
        feed, _, store, _ = feed_with([row("A")])
        for _ in GRANULARITIES:
            await feed.refresh_next_candles()
        for granularity in GRANULARITIES:
            assert await store.get_candles("A", granularity) is not None

    asyncio.run(main())


@pytest.mark.parametrize(
    ("asset", "age", "feed_age", "expected"),
    [
        ({"is_trading_suspended": False, "exchange_is_open": True}, 1, 1, "live"),
        ({"is_trading_suspended": False, "exchange_is_open": True}, STALE_SECONDS + 1, 1, "stale"),
        ({"is_trading_suspended": False, "exchange_is_open": True}, None, 1, "stale"),
        ({"is_trading_suspended": False, "exchange_is_open": False}, 1, 1, "closed"),
        ({"is_trading_suspended": True, "exchange_is_open": True}, 1, 1, "suspended"),
        (
            {"is_trading_suspended": False, "exchange_is_open": True},
            1,
            FEED_DOWN_SECONDS + 1,
            "unavailable",
        ),
    ],
)
def test_asset_status(
    asset: dict[str, Any], age: float | None, feed_age: float, expected: str
) -> None:
    now = 10_000.0
    last = None if age is None else {"epoch": now, "received_at": now - age}
    assert asset_status(asset, last, now - feed_age, now) == expected


def fill(store: MarketStore) -> None:
    async def main() -> None:
        await store.put_assets(
            [
                {
                    "symbol": "A",
                    "name": "Alpha",
                    "market": "synthetic_index",
                    "pip_size": 0.01,
                    "exchange_is_open": True,
                    "is_trading_suspended": False,
                }
            ]
        )

    asyncio.run(main())


def test_stream_sends_snapshot_then_only_watched_symbols() -> None:
    async def main() -> None:
        store = MemoryMarketStore()
        await store.put_assets([])
        chunks: list[str] = []

        async def read() -> None:
            async for chunk in stream_events(store, ["A"], 0.3):
                chunks.append(chunk)

        task = asyncio.create_task(read())
        while not chunks:
            await asyncio.sleep(0.01)
        await store.put_tick({"symbol": "B", "quote": 1.0, "epoch": 1, "received_at": 1.0})
        await store.put_tick({"symbol": "A", "quote": 2.0, "epoch": 2, "received_at": 2.0})
        await store.publish({"type": "gap", "symbol": "A", "from": 1, "to": 40})
        await asyncio.wait_for(task, 5)
        assert chunks[0].startswith("event: snapshot\n")
        assert [c.split("\n")[0] for c in chunks[1:]] == ["event: tick", "event: gap"]
        assert json.loads(chunks[1].split("data: ")[1])["symbol"] == "A"

    asyncio.run(main())


def test_redis_store_round_trip() -> None:
    url = os.environ.get("SAFETRADE_TEST_REDIS_URL")
    if not url:
        pytest.skip("SAFETRADE_TEST_REDIS_URL absent")

    async def main() -> None:
        client = Redis.from_url(url)
        await client.set(LEASE_KEY, "test")
        store = RedisMarketStore(client, "test")
        symbol = f"T{uuid.uuid4().hex}"
        await store.put_assets([{"symbol": symbol}])
        events = store.listen()
        assert await anext(events) is None
        await store.put_tick({"symbol": symbol, "quote": 1.5, "epoch": 3, "received_at": 3.0})
        # Le pub/sub ignore le numéro de base : les ticks du worker peuvent arriver ici.
        event = None
        while event is None or event["symbol"] != symbol:
            event = await anext(events)
        await events.aclose()  # type: ignore[attr-defined]
        assert (await store.get_ticks([symbol, "NONE"]))[symbol]["quote"] == 1.5
        await store.put_candles(symbol, 60, [{"epoch": 60}])
        stored = await store.get_candles(symbol, 60)
        assert stored is not None
        assert stored["candles"] == [{"epoch": 60}]
        await client.delete(LEASE_KEY, f"market:tick:{symbol}", f"market:candles:{symbol}:60")
        await client.aclose()

    asyncio.run(main())


def error_code(response: httpx.Response) -> str:
    return str(response.json()["error"])


class FullStreams(Counter[object]):
    def __missing__(self, key: object) -> int:
        return MAX_STREAMS_PER_USER


@pytest.fixture
def signed_in(migrated_engine: Engine) -> Iterator[Callable[[MarketStore | None], TestClient]]:
    clients: list[TestClient] = []

    def build(store: MarketStore | None) -> TestClient:
        mailer = MemoryMailer()
        app = create_app(
            Settings(
                environment="test",
                database_url=None,
                session_cookie_secure=False,
                market_symbols=["A", "B"],
                market_stream_seconds=0,
            ),
            session_factory=sessionmaker(migrated_engine, expire_on_commit=False),
            mailer=mailer,
            failures=MemoryFailureCounter(),
            market=store,
        )
        client = TestClient(app, base_url="http://127.0.0.1:18000", headers={"origin": ORIGIN})
        clients.append(client)
        email = f"market-{uuid.uuid4().hex[:8]}@example.com"
        client.post(
            "/auth/register",
            json={
                "email": email,
                "password": PASSWORD,
                "first_name": "Ada",
                "language": "fr",
                "accept_terms": True,
                "accept_risk": True,
            },
        )
        with migrated_engine.begin() as connection:
            connection.execute(
                text("UPDATE users SET email_verified_at = now() WHERE email = :e"), {"e": email}
            )
        assert (
            client.post("/auth/login", json={"email": email, "password": PASSWORD}).status_code
            == 200
        )
        return client

    yield build
    for client in clients:
        client.close()


@requires_db
def test_assets_and_candles_routes(signed_in: Callable[[MarketStore | None], TestClient]) -> None:
    store = MemoryMarketStore()
    fill(store)
    asyncio.run(
        store.put_candles(
            "A",
            60,
            [{"epoch": e, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0} for e in (60, 120)],
        )
    )
    client = signed_in(store)
    assets = client.get("/market/assets").json()["assets"]
    assert assets[0]["symbol"] == "A"
    assert assets[0]["status"] == "stale"
    response = client.get("/market/candles", params={"symbol": "A", "granularity": 60, "count": 1})
    assert [c["epoch"] for c in response.json()["candles"]] == [120]
    assert (
        error_code(client.get("/market/candles", params={"symbol": "ZZ"}))
        == "market.unknown_symbol"
    )
    invalid = client.get("/market/candles", params={"symbol": "A", "granularity": 7})
    assert error_code(invalid) == "market.invalid_granularity"
    pending = client.get("/market/candles", params={"symbol": "B"}).json()
    assert (pending["candles"], pending["refreshing"]) == ([], True)


@requires_db
def test_stream_route_and_limit(signed_in: Callable[[MarketStore | None], TestClient]) -> None:
    store = MemoryMarketStore()
    fill(store)
    client = signed_in(store)
    response = client.get("/market/stream", params={"symbols": ["A"]})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text.startswith("event: snapshot\n")
    assert client.get("/market/stream", params={"symbols": ["ZZ"]}).status_code == 404
    app: Any = client.app
    assert sum(app.state.market_streams.values()) == 0
    app.state.market_streams = FullStreams()
    refused = client.get("/market/stream")
    assert refused.status_code == 429
    assert error_code(refused) == "market.too_many_streams"


@requires_db
def test_market_unavailable_without_store(
    signed_in: Callable[[MarketStore | None], TestClient],
) -> None:
    client = signed_in(None)
    response = client.get("/market/assets")
    assert response.status_code == 503
    assert error_code(response) == "market.unavailable"
