"""Responsable unique, fraîcheur des données et surveillance (étape 2.5b)."""

import asyncio
import json
import logging
import os
import socket
import time
import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from redis.asyncio import Redis

from app.admin.router import market_monitoring
from app.config import Settings
from app.logs import JsonFormatter, configure_json_logs
from app.market.feed import ALERT_DISCONNECTED_SECONDS, active_alerts
from app.market.health import check, diagnose, presence_key
from app.market.lease import LEASE_KEY, LeadershipLostError, Lease, lead_while_holding
from app.market.quality import (
    GAP_COOLDOWN_SECONDS,
    MAX_FUTURE_SECONDS,
    MAX_TICK_AGE_SECONDS,
    MarketSnapshot,
    candles_refusal,
    closed_candles,
    entry_refusal,
)
from app.market.store import RedisMarketStore
from app.market.worker import serve
from tests.test_market import feed_with, row, tick

NOW = 100_000.0
GRANULARITY = 60


def candles(count: int = 5, last: float = NOW - 60) -> list[dict[str, Any]]:
    start = int(last // GRANULARITY) * GRANULARITY
    return [
        {"epoch": start - i * GRANULARITY, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}
        for i in reversed(range(count))
    ]


def snapshot(**changes: Any) -> MarketSnapshot:
    values: dict[str, Any] = {
        "status": "live",
        "tick": {"epoch": int(NOW) - 1, "received_at": NOW - 1, "last_gap_epoch": None},
        "candles": candles(),
        "granularity": GRANULARITY,
        "candles_updated_at": NOW - 5,
    }
    return MarketSnapshot(**{**values, **changes})


def test_healthy_data_is_accepted() -> None:
    assert entry_refusal(snapshot(), NOW, 3) is None


@pytest.mark.parametrize("status", ["stale", "closed", "suspended", "unavailable"])
def test_only_live_status_allows_an_entry(status: str) -> None:
    assert entry_refusal(snapshot(status=status), NOW, 3) == f"market.{status}"


@pytest.mark.parametrize(
    ("tick_data", "expected"),
    [
        (None, "market.no_tick"),
        (
            {"epoch": int(NOW + MAX_FUTURE_SECONDS) + 2, "received_at": NOW},
            "market.tick_from_future",
        ),
        (
            {"epoch": int(NOW - MAX_TICK_AGE_SECONDS) - 2, "received_at": NOW},
            "market.tick_stale",
        ),
        (
            {"epoch": int(NOW) - 1, "received_at": NOW - MAX_TICK_AGE_SECONDS - 1},
            "market.tick_stale",
        ),
    ],
)
def test_tick_timestamps(tick_data: dict[str, Any] | None, expected: str) -> None:
    assert entry_refusal(snapshot(tick=tick_data), NOW, 3) == expected


def test_recent_gap_blocks_entries_then_requires_repaired_candles() -> None:
    fresh = {"epoch": int(NOW) - 1, "received_at": NOW - 1}
    recent = {**fresh, "last_gap_epoch": NOW - 10}
    assert entry_refusal(snapshot(tick=recent), NOW, 3) == "market.recent_gap"
    gap_at = NOW - GAP_COOLDOWN_SECONDS - 1
    old = {**fresh, "last_gap_epoch": gap_at}
    not_repaired = snapshot(tick=old, candles_updated_at=gap_at - 1)
    assert entry_refusal(not_repaired, NOW, 3) == "market.gap_not_repaired"
    assert entry_refusal(snapshot(tick=old, candles_updated_at=gap_at + 1), NOW, 3) is None


def test_forming_candle_is_never_used() -> None:
    forming = int(NOW // GRANULARITY) * GRANULARITY
    rows = [{"epoch": forming - GRANULARITY}, {"epoch": forming}]
    assert closed_candles(rows, GRANULARITY, NOW) == [{"epoch": forming - GRANULARITY}]


def test_candle_checks() -> None:
    assert candles_refusal(candles(2), GRANULARITY, NOW, 3) == "market.candles_missing"
    old = candles(5, last=NOW - 10 * GRANULARITY)
    assert candles_refusal(old, GRANULARITY, NOW, 3) == "market.candles_stale"
    holed = candles(5)
    del holed[-2]
    assert candles_refusal(holed, GRANULARITY, NOW, 3) == "market.candles_gap"


def test_gap_is_stamped_on_following_ticks() -> None:
    async def main() -> None:
        feed, broker, store, _ = feed_with([row("A")])
        await feed.sync()
        await broker.handlers["A"](tick("A", 10))
        await broker.handlers["A"](tick("A", 100))
        await broker.handlers["A"](tick("A", 101))
        assert (await store.get_ticks(["A"]))["A"]["last_gap_epoch"] == 100
        assert feed.gaps == 1

    asyncio.run(main())


def test_tick_from_the_future_is_dropped() -> None:
    async def main() -> None:
        feed, broker, store, clock = feed_with([row("A")])
        await feed.sync()
        await broker.handlers["A"](tick("A", int(clock.now + MAX_FUTURE_SECONDS) + 2))
        assert await store.get_ticks(["A"]) == {}
        assert feed.ticks_dropped == 1

    asyncio.run(main())


def health(**changes: Any) -> dict[str, Any]:
    return {
        "disconnected_since": None,
        "silent_symbols": [],
        "errors_since_last_report": 0,
        **changes,
    }


def test_active_alerts() -> None:
    assert active_alerts(health(), NOW) == set()
    assert active_alerts(health(disconnected_since=NOW - 5), NOW) == set()
    down = health(disconnected_since=NOW - ALERT_DISCONNECTED_SECONDS)
    assert active_alerts(down, NOW) == {"market.feed_disconnected"}
    assert active_alerts(health(silent_symbols=["A"]), NOW) == {"market.symbols_silent"}
    assert active_alerts(health(errors_since_last_report=5), NOW) == {"market.deriv_errors"}


def test_prolonged_disconnection_raises_then_resolves_one_alert() -> None:
    async def main() -> None:
        feed, broker, store, clock = feed_with([row("A")])
        broker.connected = False
        await feed.report()
        clock.now += ALERT_DISCONNECTED_SECONDS
        await feed.report()
        await feed.report()
        broker.connected = True
        await feed.report()
        states = [(a["code"], a["state"]) for a in reversed(await store.get_alerts())]
        assert states == [
            ("market.feed_disconnected", "raised"),
            ("market.feed_disconnected", "resolved"),
        ]
        reported = await store.get_health()
        assert reported is not None
        assert reported["connected"] is True

    asyncio.run(main())


def test_probe_measures_latency_and_clock_offset() -> None:
    async def main() -> None:
        feed, _, _, clock = feed_with([row("A")])
        await feed.sync()
        assert feed.round_trip_ms is not None
        assert feed.clock_offset_seconds == round(clock.now - 999.0, 2)

    asyncio.run(main())


def test_json_logs_carry_fields_and_stay_parsable() -> None:
    record = logging.makeLogRecord(
        {"name": "x", "levelname": "ERROR", "msg": "alerte", "event": "alert.raised", "code": "c"}
    )
    entry = json.loads(JsonFormatter().format(record))
    assert entry["event"] == "alert.raised"
    assert entry["code"] == "c"
    assert entry["level"] == "ERROR"


class StubLease:
    def __init__(self, keeps: int) -> None:
        self.keeps = keeps
        self.released = False

    async def renew(self) -> bool:
        self.keeps -= 1
        return self.keeps > 0

    async def release(self) -> None:
        self.released = True


def test_lost_lease_stops_the_work_at_once() -> None:
    async def main() -> None:
        stopped = asyncio.Event()

        async def work() -> None:
            try:
                await asyncio.sleep(30)
            finally:
                stopped.set()

        lease: Any = StubLease(keeps=2)
        await asyncio.wait_for(lead_while_holding(lease, work, renew_seconds=0.01), 3)
        assert stopped.is_set()
        assert lease.released

    asyncio.run(main())


def test_work_failure_reaches_the_supervisor() -> None:
    async def main() -> None:
        async def work() -> None:
            raise LeadershipLostError

        lease: Any = StubLease(keeps=5)
        with pytest.raises(LeadershipLostError):
            await lead_while_holding(lease, work, renew_seconds=0.01)
        assert lease.released

    asyncio.run(main())


def test_cancelled_leader_releases_its_lease(redis_url: str) -> None:
    async def main() -> None:
        client = Redis.from_url(redis_url)
        await client.delete(LEASE_KEY)
        lease = Lease(client, "leaving")
        assert await lease.acquire()
        task = asyncio.create_task(lead_while_holding(lease, lambda: asyncio.sleep(30)))
        await asyncio.sleep(0.05)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        assert await client.get(LEASE_KEY) is None
        await client.aclose()

    asyncio.run(main())


def test_failure_of_one_loop_stops_the_whole_feed() -> None:
    async def main() -> None:
        feed, broker, _, _ = feed_with([row("A")])

        async def failing() -> None:
            raise LeadershipLostError

        feed.report = failing  # type: ignore[method-assign]
        with pytest.raises(LeadershipLostError):
            await asyncio.wait_for(feed.run(), 3)
        assert broker.stopped

    asyncio.run(main())


@pytest.fixture
def redis_url() -> str:
    url = os.environ.get("SAFETRADE_TEST_REDIS_URL")
    if not url:
        pytest.skip("SAFETRADE_TEST_REDIS_URL absent")
    return url


def test_two_workers_never_lead_together(redis_url: str) -> None:
    async def main() -> None:
        client = Redis.from_url(redis_url)
        await client.delete(LEASE_KEY)
        first, second = Lease(client, "first"), Lease(client, "second")
        assert await first.acquire()
        assert not await second.acquire()
        assert not await second.renew()
        await second.release()
        assert await client.get(LEASE_KEY) == b"first"
        await first.release()
        assert await second.acquire()
        await client.delete(LEASE_KEY)
        await client.aclose()

    asyncio.run(main())


def test_expired_leader_can_no_longer_publish(redis_url: str) -> None:
    async def main() -> None:
        client = Redis.from_url(redis_url)
        await client.delete(LEASE_KEY)
        symbol = f"T{uuid.uuid4().hex}"
        sample = {"symbol": symbol, "quote": 1.0, "epoch": 1, "received_at": 1.0}
        old = RedisMarketStore(client, "old")
        lease = Lease(client, "new")
        assert await lease.acquire()
        for write in (
            old.put_tick(sample),
            old.put_assets([]),
            old.publish({"type": "gap", "symbol": symbol}),
            old.put_health({}),
            old.push_alert({"code": "x"}),
        ):
            with pytest.raises(LeadershipLostError):
                await write
        assert await old.get_ticks([symbol]) == {}
        await RedisMarketStore(client, "new").put_tick(sample)
        assert symbol in await old.get_ticks([symbol])
        with pytest.raises(LeadershipLostError):
            await RedisMarketStore(client).put_tick(sample)  # lecture seule
        await client.delete(LEASE_KEY, f"market:tick:{symbol}")
        await client.aclose()

    asyncio.run(main())


FRESH = {"at": NOW - 1, "role": "leader", "since": NOW - 300}
REPORT = {"reported_at": NOW - 2, "connected": True}


@pytest.mark.parametrize(
    ("presence", "feed", "expected"),
    [
        (FRESH, REPORT, None),
        # Deriv coupé ou en reconnexion : le worker reste sain, l'alerte suit à part.
        (FRESH, {"reported_at": NOW - 2, "connected": False}, None),
        ({"at": NOW - 1, "role": "standby", "since": NOW - 300}, None, None),
        # Démarrage ou prise de relais : rapport précédent ancien, ou aucun.
        ({"at": NOW - 1, "role": "leader", "since": NOW - 3}, None, None),
        ({"at": NOW - 1, "role": "leader", "since": NOW - 3}, {"reported_at": NOW - 900}, None),
        (None, None, "worker.absent"),
        ({"at": NOW - 25, "role": "standby", "since": NOW - 300}, None, "worker.stalled"),
        (FRESH, None, "feed.stalled"),
        (FRESH, {"reported_at": NOW - 31}, "feed.stalled"),
    ],
)
def test_worker_diagnosis(
    presence: dict[str, Any] | None, feed: dict[str, Any] | None, expected: str | None
) -> None:
    assert diagnose(presence, feed, NOW) == expected


def test_health_fails_when_redis_is_unreachable() -> None:
    assert asyncio.run(check("redis://127.0.0.1:1/0", "host")) == "redis.unreachable"


def test_health_reads_real_presence_and_never_defaults_to_success(redis_url: str) -> None:
    async def main() -> None:
        client = Redis.from_url(redis_url)
        host = f"test-{uuid.uuid4().hex}"
        await client.delete("monitor:feed")
        assert await check(redis_url, host) == "worker.absent"
        now = time.time()
        presence = {"at": now, "role": "leader", "since": now - 300}
        await client.set(presence_key(host), json.dumps(presence), ex=30)
        assert await check(redis_url, host) == "feed.stalled"
        await client.set("monitor:feed", json.dumps({"reported_at": now}))
        assert await check(redis_url, host) is None
        await client.delete(presence_key(host), "monitor:feed")
        await client.aclose()

    asyncio.run(main())


def test_stopped_worker_releases_lease_before_ending(redis_url: str) -> None:
    """Chemin réel de l'arrêt : présence et collecte tournent ensemble."""

    async def main() -> None:
        client = Redis.from_url(redis_url)
        await client.delete(LEASE_KEY)
        lease = Lease(client, "stopping")
        task = asyncio.create_task(serve(client, lease, lambda: asyncio.sleep(30)))
        while await client.get(LEASE_KEY) is None:
            await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        assert await client.get(LEASE_KEY) is None
        await client.delete(presence_key(socket.gethostname()))
        await client.aclose()

    asyncio.run(main())


def test_monitoring_route_reports_feed_assets_and_alerts() -> None:
    async def main() -> None:
        feed, broker, store, _ = feed_with([row("A"), row("GOLD", opened=0)])
        await feed.sync()
        await broker.handlers["A"](tick("A", 10))
        await feed.report()
        await store.push_alert({"code": "market.feed_disconnected", "state": "raised", "at": 1.0})
        request: Any = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(market=store)))
        settings = Settings(environment="test", market_symbols=["A", "GOLD"])
        user: Any = None
        view: dict[str, Any] = await market_monitoring(request, settings, user)
        assert view["feed"]["ticks_received"] == 1
        assert [a["status"] for a in view["assets"]] == ["stale", "closed"]
        assert view["alerts"][0]["code"] == "market.feed_disconnected"

    asyncio.run(main())


def test_http_client_logs_never_carry_account_urls() -> None:
    previous = logging.getLogger().handlers[:]
    configure_json_logs()
    logging.getLogger().handlers[:] = previous
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
