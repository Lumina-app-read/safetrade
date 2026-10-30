"""Client Deriv sur faux serveur et quotas (étape 2.2). Aucun appel à Deriv."""

import asyncio
import os
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from redis.asyncio import Redis

from app.broker.base import (
    AccountKind,
    ApiRejectedError,
    Broker,
    ConnectionLostError,
    Message,
    OrderOutcomeUnknownError,
    RealAccountDisabledError,
    RequestTimeoutError,
)
from app.broker.deriv import DerivConnection, ensure_account_allowed
from app.broker.quotas import (
    ENTRY_MINUTE_LIMIT,
    WINDOWS,
    Backoff,
    MemoryQuotaStore,
    Priority,
    Quota,
    QuotaManager,
    RedisQuotaStore,
    Window,
    priority_for,
    quota_for,
    windows_for,
)
from tests.fake_deriv import FakeDeriv

Scenario = Callable[[DerivConnection, FakeDeriv], Awaitable[None]]


def fast_backoff() -> Backoff:
    return Backoff(base=0.01, cap=0.05)


def run(scenario: Scenario, **options: Any) -> None:
    """Exécute un scénario contre un faux serveur, sans dépendance de test asynchrone."""

    async def main() -> None:
        async with FakeDeriv() as server:
            urls = options.pop("urls", None)

            async def provide() -> str:
                if urls is not None:
                    urls.append(server.url)
                return server.url

            options.setdefault("request_timeout", 2.0)
            conn = DerivConnection(
                provide,
                QuotaManager(MemoryQuotaStore()),
                scope="acct",
                backoff=fast_backoff(),
                **options,
            )
            await conn.start()
            await conn.wait_connected()
            try:
                await asyncio.wait_for(scenario(conn, server), 10)
            finally:
                await conn.stop()

    asyncio.run(main())


async def until(predicate: Callable[[], bool], timeout: float = 3.0) -> None:
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.005)


def test_connection_satisfies_broker_interface() -> None:
    async def scenario(conn: DerivConnection, _: FakeDeriv) -> None:
        broker: Broker = conn
        assert (await broker.request("x", {"x": 1}))["ok"] == 1

    run(scenario)


def test_concurrent_responses_match_their_requests() -> None:
    async def scenario(conn: DerivConnection, _: FakeDeriv) -> None:
        results = await asyncio.gather(*(conn.request("slow", {"slow": n}) for n in (3, 1, 2)))
        assert [r["slow"] for r in results] == [3, 1, 2]

    run(scenario)


def test_api_error_is_raised_with_its_code() -> None:
    async def scenario(conn: DerivConnection, _: FakeDeriv) -> None:
        with pytest.raises(ApiRejectedError) as exc:
            await conn.request("fail", {"fail": 1})
        assert exc.value.code == "Boom" and exc.value.details == {"field": "amount"}

    run(scenario)


def test_request_timeout() -> None:
    async def scenario(conn: DerivConnection, _: FakeDeriv) -> None:
        with pytest.raises(RequestTimeoutError):
            await conn.request("ignore", {"ignore": 1})

    run(scenario, request_timeout=0.05)


def test_reconnects_with_a_new_otp_url_and_restores_subscriptions() -> None:
    urls: list[str] = []

    async def scenario(conn: DerivConnection, server: FakeDeriv) -> None:
        quotes: list[float] = []

        async def on_tick(message: Message) -> None:
            quotes.append(message["tick"]["quote"])

        await conn.subscribe("ticks", {"ticks": "1HZ75V"}, on_tick)
        await until(lambda: quotes == [100.0])

        await server.drop_all()
        await until(lambda: conn.reconnections == 1 and server.calls["ticks"] == 2)
        await until(lambda: len(quotes) == 2)
        await server.push_tick(101.5)
        await until(lambda: quotes[-1] == 101.5)

        assert server.opened == 2
        assert len(urls) == 2  # chaque connexion a demandé sa propre adresse OTP

    run(scenario, urls=urls)


def test_repeated_failures_keep_reconnecting() -> None:
    async def scenario(conn: DerivConnection, server: FakeDeriv) -> None:
        for expected in (1, 2, 3):
            await server.drop_all()
            await until(lambda: conn.reconnections == expected)  # noqa: B023
        assert (await conn.request("x", {"x": 1}))["ok"] == 1

    run(scenario)


def test_silent_connection_is_detected_and_replaced() -> None:
    async def scenario(conn: DerivConnection, server: FakeDeriv) -> None:
        server.mute = True
        await until(lambda: conn.reconnections >= 1)
        server.mute = False

    run(scenario, ping_seconds=0.02)


def test_pending_request_fails_when_connection_drops() -> None:
    async def scenario(conn: DerivConnection, server: FakeDeriv) -> None:
        pending = asyncio.create_task(conn.request("ignore", {"ignore": 1}))
        await until(lambda: "ignore" in str(server.received))
        await server.drop_all()
        with pytest.raises(ConnectionLostError):
            await pending

    run(scenario)


def test_subscription_refusal_reaches_the_caller() -> None:
    async def scenario(conn: DerivConnection, server: FakeDeriv) -> None:
        async def ignore(_: Message) -> None:
            return None

        with pytest.raises(ApiRejectedError):
            await conn.subscribe("ticks", {"ticks": "BAD"}, ignore)
        await server.drop_all()
        await until(lambda: conn.reconnections == 1)
        assert server.calls["ticks"] == 1  # l'abonnement refusé n'est pas repris

    run(scenario)


def test_handler_error_does_not_break_the_stream() -> None:
    async def scenario(conn: DerivConnection, server: FakeDeriv) -> None:
        seen: list[float] = []

        async def fragile(message: Message) -> None:
            seen.append(message["tick"]["quote"])
            raise ValueError("erreur de traitement")

        await conn.subscribe("ticks", {"ticks": "1HZ75V"}, fragile)
        await server.push_tick(101)
        await until(lambda: 101 in seen)
        assert conn.reconnections == 0

    run(scenario)


def test_cancelled_subscription_is_not_restored() -> None:
    async def scenario(conn: DerivConnection, server: FakeDeriv) -> None:
        async def ignore(_: Message) -> None:
            return None

        stream = await conn.subscribe("ticks", {"ticks": "1HZ75V"}, ignore)
        await stream.cancel()
        assert server.calls["forget"] == 1
        await server.drop_all()
        await until(lambda: conn.reconnections == 1)
        assert server.calls["ticks"] == 1

    run(scenario)


def test_buy_sends_only_the_proposal_id() -> None:
    async def scenario(conn: DerivConnection, server: FakeDeriv) -> None:
        purchase = await conn.buy("prop-1", 1.0)
        assert purchase.contract_id == 42
        sent = next(m for m in server.received if "buy" in m)
        assert {k: v for k, v in sent.items() if k != "req_id"} == {"buy": "prop-1", "price": 1.0}

    run(scenario)


def test_lost_buy_response_is_unknown_and_never_resent() -> None:
    async def scenario(conn: DerivConnection, server: FakeDeriv) -> None:
        server.swallow_buy = True
        with pytest.raises(OrderOutcomeUnknownError) as exc:
            await conn.buy("prop-1", 1.0)
        assert exc.value.proposal_id == "prop-1"
        await server.drop_all()
        await until(lambda: conn.reconnections == 1)
        assert server.calls["buy"] == 1

    run(scenario, request_timeout=0.05)


def test_connection_cut_during_buy_is_unknown_and_never_resent() -> None:
    async def scenario(conn: DerivConnection, server: FakeDeriv) -> None:
        server.drop_on_buy = True
        with pytest.raises(OrderOutcomeUnknownError):
            await conn.buy("prop-1", 1.0)
        await until(lambda: conn.reconnections == 1)
        await asyncio.sleep(0.05)
        assert server.calls["buy"] == 1

    run(scenario)


def test_buy_without_connection_was_never_sent() -> None:
    async def main() -> None:
        async def provide() -> str:
            raise OSError("réseau coupé")

        conn = DerivConnection(provide, QuotaManager(MemoryQuotaStore()), scope="a")
        with pytest.raises(ConnectionLostError):
            await conn.buy("prop-1", 1.0)

    asyncio.run(main())


def test_real_account_is_refused_while_disabled() -> None:
    with pytest.raises(RealAccountDisabledError):
        ensure_account_allowed(AccountKind.REAL, real_account_enabled=False)
    ensure_account_allowed(AccountKind.DEMO, real_account_enabled=False)


def test_call_groups_follow_deriv_limits() -> None:
    for call in ("proposal", "proposal_open_contract", "buy", "sell"):
        assert quota_for(call) is Quota.WS_TRADING
    assert quota_for("statement") is Quota.WS_ACCOUNT
    assert quota_for("portfolio") is Quota.WS_REPORTS
    assert quota_for("ticks_history") is Quota.WS_OTHER
    assert quota_for("ping") is None


def test_limits_stay_below_official_values() -> None:
    official = {
        Quota.WS_TRADING: (360, 14400),
        Quota.WS_ACCOUNT: (100, 2000),
        Quota.WS_REPORTS: (30, 1500),
        Quota.WS_OTHER: (220, 14400),
        Quota.REST_USER: (80,),
        Quota.REST_IP: (300, 1000),
    }
    for quota, limits in official.items():
        assert all(w.limit < o for w, o in zip(WINDOWS[quota], limits, strict=True))


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_sliding_window_grants_blocks_and_recovers() -> None:
    async def main() -> None:
        clock = Clock()
        store = MemoryQuotaStore(clock)
        window = (Window(60, 2),)
        assert await store.acquire("k", window) == 0
        clock.now += 10
        assert await store.acquire("k", window) == 0
        assert await store.acquire("k", window) == pytest.approx(50)
        clock.now += 50.1
        assert await store.acquire("k", window) == 0

    asyncio.run(main())


def test_every_window_applies_at_once() -> None:
    async def main() -> None:
        clock = Clock()
        store = MemoryQuotaStore(clock)
        windows = (Window(60, 100), Window(600, 2))
        await store.acquire("k", windows)
        await store.acquire("k", windows)
        clock.now += 120
        assert await store.acquire("k", windows) == pytest.approx(480)

    asyncio.run(main())


def test_quota_is_shared_between_bots_on_the_same_scope() -> None:
    async def main() -> None:
        store = MemoryQuotaStore()
        windows = (Window(60, 3),)
        results = [await store.acquire("rest_ip:server", windows) for _ in range(4)]
        assert results[:3] == [0, 0, 0] and results[3] > 0
        assert await store.acquire("rest_ip:other", windows) == 0

    asyncio.run(main())


def test_exits_keep_budget_when_entries_are_capped() -> None:
    assert priority_for("sell") is Priority.PROTECTIVE
    assert priority_for("buy") is Priority.NORMAL

    async def main() -> None:
        store = MemoryQuotaStore(Clock())
        entry = windows_for(Quota.WS_TRADING, Priority.NORMAL)
        protective = windows_for(Quota.WS_TRADING, Priority.PROTECTIVE)
        for _ in range(ENTRY_MINUTE_LIMIT):
            assert await store.acquire("t", entry) == 0
        assert await store.acquire("t", entry) > 0
        assert await store.acquire("t", protective) == 0

    asyncio.run(main())


def test_mass_reconnection_is_spread_by_the_shared_quota() -> None:
    """Le quota REST de l'adresse IP étale les reconnexions de tous les bots."""

    async def main() -> None:
        clock = Clock()
        store = MemoryQuotaStore(clock)
        windows = WINDOWS[Quota.REST_IP]
        granted = 0
        for _ in range(300):
            if await store.acquire("rest_ip:server", windows) == 0:
                granted += 1
        assert granted == 240  # les 60 autres attendent la minute suivante

    asyncio.run(main())


def test_backoff_grows_is_capped_and_never_zero() -> None:
    backoff = Backoff(base=1, cap=8)
    delays = [backoff.next_delay() for _ in range(8)]
    ceilings = [1, 2, 4, 8, 8, 8, 8, 8]
    assert all(c / 2 <= d <= c for d, c in zip(delays, ceilings, strict=True))
    backoff.reset()
    assert backoff.next_delay() <= 1


def test_backoff_spreads_identical_clients() -> None:
    assert len({round(Backoff(base=8).next_delay(), 3) for _ in range(20)}) > 5


@pytest.mark.skipif(
    "SAFETRADE_TEST_REDIS_URL" not in os.environ, reason="SAFETRADE_TEST_REDIS_URL non défini"
)
def test_redis_store_is_atomic_and_shared() -> None:
    async def main() -> None:
        client = Redis.from_url(os.environ["SAFETRADE_TEST_REDIS_URL"])
        key = f"test:{os.urandom(4).hex()}"
        try:
            first, second = RedisQuotaStore(client), RedisQuotaStore(client)
            windows = (Window(60, 5), Window(600, 50))
            results = await asyncio.gather(*(s.acquire(key, windows) for s in [first, second] * 10))
            assert sum(r == 0 for r in results) == 5
            assert all(0 < r <= 60 for r in results if r)
        finally:
            await client.delete(f"quota:{key}")
            await client.aclose()

    asyncio.run(main())
