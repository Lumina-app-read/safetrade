"""Catalogue des actifs, liste du client et lien partenaire. Deriv simulé, aucun ordre."""

import asyncio
import time
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import sessionmaker

from app.admin.router import clean_url
from app.auth.mailer import MemoryMailer
from app.auth.rate_limit import MemoryFailureCounter
from app.broker.base import ApiRejectedError, Message, RequestTimeoutError
from app.config import Settings
from app.db.models import AuditLog, UserRole
from app.errors import ApiError
from app.main import create_app
from app.market.feed import (
    CONTRACTS_RETRY_SECONDS,
    GRANULARITIES,
    MarketFeed,
    next_candles,
)
from app.market.store import MemoryMarketStore
from tests.conftest import requires_db
from tests.test_authz import KEY, ORIGIN, enable_mfa, signed_up
from tests.test_market import Clock, FakeBroker, tick


def row(
    symbol: str, market: str = "synthetic_index", submarket: str = "step_index"
) -> dict[str, Any]:
    return {
        "underlying_symbol": symbol,
        "underlying_symbol_name": f"{symbol} Index",
        "market": market,
        "submarket": submarket,
        "pip_size": 0.01,
        "exchange_is_open": 1,
        "is_trading_suspended": 0,
    }


ROWS = [
    row("BOOM500", submarket="crash_index"),
    row("JD10", submarket="jump_index"),
    row("RDBULL", submarket="random_daily"),
    row("frxEURUSD", "forex", "major_pairs"),
    row("frxXAUUSD", "commodities", "metals"),
]


class Contracts(FakeBroker):
    """Comme chez Deriv : pas de multiplicateurs sur Bull Market, liste démentie sur Jump 10."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        super().__init__(rows)
        self.asked: list[str] = []
        self.quoted: list[Message] = []

    async def request(self, call: str, payload: Message) -> Message:
        if self.fail_with:
            raise self.fail_with
        if call == "proposal":
            self.quoted.append(payload)
            if payload["underlying_symbol"] == "JD10":
                raise ApiRejectedError(
                    "ContractBuyValidationError",
                    "Multiplier is not in acceptable range. Accepts 400,1000,2000.",
                )
            return {"proposal": {}}
        if call != "contracts_for":
            return await super().request(call, payload)
        symbol = payload["contracts_for"]
        self.asked.append(symbol)
        kinds = ["CALL"] if symbol == "RDBULL" else ["MULTUP", "MULTDOWN"]
        offered = [{"contract_type": k, "multiplier_range": [20, 750]} for k in kinds]
        return {"contracts_for": {"available": offered}}


def feed(defaults: list[str]) -> tuple[MarketFeed, Contracts, MemoryMarketStore, Clock]:
    broker, store, clock = Contracts(ROWS), MemoryMarketStore(), Clock()
    return MarketFeed(broker, store, defaults, clock=clock, candle_pause=0), broker, store, clock


def test_catalog_has_every_synthetic_index_and_the_defaults() -> None:
    async def main() -> None:
        market, _, store, _ = feed(["frxXAUUSD"])
        await market.refresh_assets()
        state = await store.get_assets()
        assert state is not None
        symbols = [a["symbol"] for a in state["assets"]]
        assert symbols == ["BOOM500", "JD10", "RDBULL", "frxXAUUSD"]
        assert state["assets"][0]["submarket"] == "crash_index"

    asyncio.run(main())


def test_ticks_cover_the_whole_catalog() -> None:
    async def main() -> None:
        market, broker, _, _ = feed([])
        await market.sync()
        assert sorted(broker.subscriptions) == ["BOOM500", "JD10", "RDBULL"]

    asyncio.run(main())


def test_multipliers_come_from_deriv_one_symbol_per_cycle() -> None:
    async def main() -> None:
        market, broker, store, clock = feed([])
        for _ in range(3):
            await market.sync()
        assert broker.asked == ["BOOM500", "JD10", "RDBULL"]
        clock.now += 60
        await market.sync()
        state = await store.get_assets()
        assert state is not None
        found = {a["symbol"]: a["multipliers"] for a in state["assets"]}
        assert found == {"BOOM500": True, "JD10": True, "RDBULL": False}
        assert state["assets"][0]["multiplier_range"] == [20, 750]
        # Le devis l'emporte sur la liste annoncée.
        assert state["assets"][1]["multiplier_range"] == [400, 1000, 2000]
        assert state["assets"][2]["multiplier_range"] == []
        assert "buy" not in str(broker.quoted)
        assert all(q["proposal"] == 1 for q in broker.quoted)

    asyncio.run(main())


def test_failed_contract_read_is_retried_soon_without_blocking_the_others() -> None:
    async def main() -> None:
        market, broker, _, clock = feed([])
        await market.refresh_assets()
        broker.fail_with = RequestTimeoutError("coupure")
        with pytest.raises(RequestTimeoutError):
            await market.refresh_contracts(clock.now)
        broker.fail_with = None
        await market.refresh_contracts(clock.now)
        assert broker.asked == ["JD10"]  # l'actif suivant passe, l'échec attend son tour
        await market.refresh_contracts(clock.now)
        clock.now += CONTRACTS_RETRY_SECONDS
        await market.refresh_contracts(clock.now)
        assert broker.asked == ["JD10", "RDBULL", "BOOM500"]
        clock.now += 1
        await market.refresh_contracts(clock.now)
        assert broker.asked == ["JD10", "RDBULL", "BOOM500"]  # lu : pas avant six heures

    asyncio.run(main())


def test_multipliers_survive_a_restart() -> None:
    async def main() -> None:
        market, _, store, clock = feed([])
        for _ in range(3):
            await market.sync()
        clock.now += 60
        await market.sync()
        restarted = MarketFeed(Contracts(ROWS), store, [], clock=clock)
        await restarted.refresh_assets()
        state = await store.get_assets()
        assert state is not None
        assert {a["symbol"]: a["multipliers"] for a in state["assets"]}["RDBULL"] is False

    asyncio.run(main())


def test_next_candles_picks_the_latest_and_waits_when_all_is_fresh() -> None:
    now = 10_000.0
    fresh = {("A", g): now for g in GRANULARITIES}
    assert next_candles(["A"], fresh, now) is None
    late = {**fresh, ("A", 3600): now - 400, ("A", 60): now - 40}
    assert next_candles(["A"], late, now) == ("A", 3600)
    assert next_candles(["A", "B"], fresh, now) == ("B", 60)


def test_only_followed_symbols_read_candles() -> None:
    async def main() -> None:
        market, broker, store, clock = feed(["JD10"])
        await market.refresh_assets()
        for _ in GRANULARITIES:
            await market.refresh_next_candles()
        await market.refresh_next_candles()  # tout est à jour : aucun appel
        assert [p["ticks_history"] for p in broker.history] == ["JD10"] * 4

        await store.demand("BOOM500")
        clock.now = time.time()
        await market.refresh_next_candles()
        assert "BOOM500" in {p["ticks_history"] for p in broker.history}

    asyncio.run(main())


def test_gap_on_an_unfollowed_symbol_costs_no_candles() -> None:
    async def main() -> None:
        market, broker, _, _ = feed(["JD10"])
        await market.sync()
        await broker.handlers["BOOM500"](tick("BOOM500", 10))
        await broker.handlers["BOOM500"](tick("BOOM500", 500))
        await market.refresh_next_candles()
        assert {p["ticks_history"] for p in broker.history} == {"JD10"}

    asyncio.run(main())


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("  ", None),
        ("https://track.deriv.com/_abc/1/", "https://track.deriv.com/_abc/1/"),
        (" https://deriv.com/?ref=1 ", "https://deriv.com/?ref=1"),
    ],
)
def test_partner_link_is_cleaned(raw: str | None, expected: str | None) -> None:
    assert clean_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["http://deriv.com", "javascript:alert(1)", "deriv.com", "https://", "https://u:p@deriv.com"],
)
def test_partner_link_refuses_anything_but_plain_https(raw: str) -> None:
    with pytest.raises(ApiError) as refused:
        clean_url(raw)
    assert refused.value.code == "admin.invalid_url"


@pytest.fixture
def make_client(migrated_engine: Engine) -> Iterator[Callable[[], TestClient]]:
    store = MemoryMarketStore()
    asyncio.run(
        store.put_assets(
            [
                {
                    "symbol": symbol,
                    "name": symbol,
                    "market": "synthetic_index",
                    "submarket": "step_index",
                    "pip_size": 0.01,
                    "exchange_is_open": True,
                    "is_trading_suspended": False,
                    "multipliers": symbol != "RDBULL",
                }
                for symbol in ("A", "B", "JD10", "RDBULL")
            ]
        )
    )
    app = create_app(
        Settings(
            environment="test",
            session_cookie_secure=False,
            allowed_origins=[ORIGIN],
            encryption_key=KEY,
            market_symbols=["A", "B"],
        ),
        session_factory=sessionmaker(migrated_engine, expire_on_commit=False),
        mailer=MemoryMailer(),
        failures=MemoryFailureCounter(),
        market=store,
    )
    app.state.test_mailer = app.state.mailer
    clients: list[TestClient] = []

    def make() -> TestClient:
        client = TestClient(app, headers={"Origin": ORIGIN})
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.close()


@requires_db
def test_assets_list_the_whole_catalog(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    client = make_client()
    signed_up(client, migrated_engine)
    assets = client.get("/market/assets").json()["assets"]
    assert [a["symbol"] for a in assets] == ["A", "B", "JD10", "RDBULL"]
    assert assets[3]["multipliers"] is False


@requires_db
def test_watchlist_defaults_then_keeps_the_client_choice(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    client = make_client()
    signed_up(client, migrated_engine)
    assert client.get("/market/watchlist").json() == {"symbols": ["A", "B"]}
    saved = client.put("/market/watchlist", json={"symbols": ["JD10", "A", "JD10"]})
    assert saved.json() == {"symbols": ["JD10", "A"]}
    assert client.get("/market/watchlist").json() == {"symbols": ["JD10", "A"]}

    stranger = make_client()
    signed_up(stranger, migrated_engine)
    assert stranger.get("/market/watchlist").json() == {"symbols": ["A", "B"]}


@requires_db
@pytest.mark.parametrize(
    ("symbols", "status"),
    [(["NOPE"], 404), ([], 422), (["A"] * 61, 422)],
)
def test_watchlist_is_validated(
    make_client: Callable[[], TestClient],
    migrated_engine: Engine,
    symbols: list[str],
    status: int,
) -> None:
    client = make_client()
    signed_up(client, migrated_engine)
    assert client.put("/market/watchlist", json={"symbols": symbols}).status_code == status


@requires_db
def test_reading_candles_asks_the_feed_to_follow_the_symbol(
    make_client: Callable[[], TestClient], migrated_engine: Engine
) -> None:
    client = make_client()
    signed_up(client, migrated_engine)
    first = client.get("/market/candles", params={"symbol": "JD10"})
    assert first.status_code == 200
    assert first.json()["candles"] == []
    assert first.json()["refreshing"] is True
    app: Any = client.app
    assert "JD10" in asyncio.run(app.state.market.get_demand(0))
    assert client.get("/market/candles", params={"symbol": "NOPE"}).status_code == 404


@requires_db
def test_partner_link_is_public_and_set_by_an_administrator(
    make_client: Callable[[], TestClient], migrated_engine: Engine, factory: sessionmaker[Any]
) -> None:
    boss = make_client()
    signed_up(boss, migrated_engine, UserRole.SUPER_ADMIN)
    enable_mfa(boss)
    visitor = make_client()
    url = "https://track.deriv.com/_x/1/"
    assert boss.put("/admin/site", json={"deriv_signup_url": url}).status_code == 200
    assert visitor.get("/site/config").json() == {"deriv_signup_url": url}
    refused = boss.put("/admin/site", json={"deriv_signup_url": "http://evil.example"})
    assert (refused.status_code, refused.json()["error"]) == (422, "admin.invalid_url")
    assert visitor.get("/site/config").json() == {"deriv_signup_url": url}
    with factory() as db:
        assert db.scalars(select(AuditLog).where(AuditLog.action == "admin.site_settings")).first()
    assert boss.put("/admin/site", json={"deriv_signup_url": ""}).status_code == 200
    assert visitor.get("/site/config").json() == {"deriv_signup_url": None}


@pytest.fixture
def factory(migrated_engine: Engine) -> sessionmaker[Any]:
    return sessionmaker(migrated_engine, expire_on_commit=False)


@requires_db
@pytest.mark.parametrize("role", [UserRole.FINANCE, UserRole.SUPPORT])
def test_partner_link_needs_the_settings_permission(
    make_client: Callable[[], TestClient], migrated_engine: Engine, role: UserRole
) -> None:
    client = make_client()
    signed_up(client, migrated_engine, role)
    enable_mfa(client)
    assert client.put("/admin/site", json={"deriv_signup_url": None}).status_code == 403
