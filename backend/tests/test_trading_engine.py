"""
Moteur sur vraie base PostgreSQL et faux compte Deriv : doublons, pannes, reprise, sorties.
Aucun appel à Deriv ; l'essai réel se fait sur compte démo, hors de ces tests.
"""

import asyncio
import itertools
import time
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from app.auth.mailer import MemoryMailer
from app.auth.rate_limit import MemoryFailureCounter
from app.broker.base import (
    ApiRejectedError,
    ConnectionLostError,
    Message,
    MessageHandler,
    OrderOutcomeUnknownError,
    Purchase,
)
from app.broker.deriv_trading import Buy, DerivTrading
from app.config import Settings
from app.db.models import (
    BotSession,
    BotState,
    DerivConnectionRecord,
    PositionStatus,
    Subscription,
    TradingDecision,
    TradingPosition,
    TradingSettings,
    User,
)
from app.main import create_app
from app.market.store import MemoryMarketStore
from app.trading import risk, strategy
from app.trading.bot import BotRunner
from app.trading.execution import Executor, Journal
from tests.conftest import requires_db

pytestmark = requires_db

ORIGIN = "http://127.0.0.1:13000"
PASSWORD = "Correct-Horse-42"
SYMBOL = "1HZ100V"


CONTRACT_IDS = itertools.count(1000, 1000)


class FakeStream:
    async def cancel(self) -> None: ...


class FakeBroker:
    """Compte Deriv en mémoire : achats, contrats, relevé. Pannes à la demande."""

    def __init__(self) -> None:
        self.connected = True
        self.reconnections = 0
        self.balance = 10000.0
        self.buys = 0
        self.contracts: dict[int, Message] = {}
        self.statement: list[dict[str, Any]] = []
        self.foreign: list[Message] = []
        self.updates: list[dict[str, Any]] = []
        self.sells: list[int] = []
        self.outcome = "ok"  # ok, unknown_lost, unknown_done, rejected
        self.sell_error: str | None = None
        self.update_error: str | None = None
        self.update_message = "refusé"
        self.proposal_extra: dict[str, Any] = {}
        self.next_id = next(CONTRACT_IDS)

    async def start(self) -> None: ...
    async def stop(self) -> None: ...

    def _record(self, stake: float = 1.0) -> int:
        self.next_id += 1
        self.statement.append(
            {
                "contract_id": self.next_id,
                "amount": -stake,
                "transaction_time": int(time.time()),
                "shortcode": f"MULTUP_{SYMBOL}_{stake:.2f}_100_1_2_0_0.25_N1_0",
            }
        )
        self.contracts[self.next_id] = {
            "contract_id": self.next_id,
            "buy_price": stake,
            "commission": 0.03,
            "profit": -0.03,
            "is_sold": 0,
            "is_valid_to_sell": 1,
            "limit_order": {"stop_loss": {"order_amount": -0.5}},
        }
        return self.next_id

    async def request(self, call: str, payload: Message) -> Message:
        if call == "proposal":
            return {
                "proposal": {
                    "id": f"p{self.buys}",
                    "ask_price": 1.0,
                    "commission": 0.03,
                    "validation_params": {"stop_loss": {"min": "0.04", "max": "1.00"}},
                    **self.proposal_extra,
                }
            }
        if call == "balance":
            return {"balance": {"balance": self.balance}}
        if call == "statement":
            return {"statement": {"transactions": self.statement}}
        if call == "portfolio":
            open_rows = [{"contract_id": c} for c, v in self.contracts.items() if not v["is_sold"]]
            return {"portfolio": {"contracts": open_rows + self.foreign}}
        if call == "proposal_open_contract":
            return {"proposal_open_contract": self.contracts[payload["contract_id"]]}
        if call == "contract_update":
            if self.update_error:
                raise ApiRejectedError(self.update_error, self.update_message)
            self.updates.append(payload["limit_order"])
            amount = -payload["limit_order"]["stop_loss"]
            self.contracts[payload["contract_id"]]["limit_order"] = {
                "stop_loss": {"order_amount": amount}
            }
            return {"contract_update": {}}
        if call == "sell":
            if self.sell_error:
                raise ApiRejectedError(self.sell_error, "refusé")
            contract_id = payload["sell"]
            self.sells.append(contract_id)
            self.close(contract_id, 1 + float(self.contracts[contract_id]["profit"]))
            return {"sell": {"sold_for": 1.0}}
        raise AssertionError(call)

    def close(self, contract_id: int, sell_price: float) -> None:
        self.contracts[contract_id].update(
            is_sold=1, sell_price=sell_price, sell_time=int(time.time()), is_valid_to_sell=0
        )

    async def subscribe(self, call: str, payload: Message, handler: MessageHandler) -> FakeStream:
        return FakeStream()

    async def buy(self, proposal_id: str, max_price: float) -> Purchase:
        self.buys += 1
        if self.outcome == "unknown_lost":
            raise OrderOutcomeUnknownError(proposal_id, time.time())
        if self.outcome == "unknown_done":
            self._record()
            raise OrderOutcomeUnknownError(proposal_id, time.time())
        if self.outcome == "rejected":
            raise ApiRejectedError("InvalidOfferings", "refusé")
        if self.outcome == "lost":
            raise ConnectionLostError
        contract_id = self._record()
        return Purchase(contract_id, 1.0, self.balance - 1, contract_id, "MULTUP")


def live_candles(now: float, count: int = 60, cross: bool = True) -> list[dict[str, Any]]:
    current = int(now // 60) * 60
    epochs = [current - 60 * (count - i) for i in range(count)]
    closes = [100 - i * 0.1 for i in range(count)]
    if cross:
        closes[-1] = 120.0
    return [
        {"epoch": e, "open": c, "high": c + 0.5, "low": c - 0.5, "close": c}
        for e, c in zip(epochs, closes, strict=True)
    ]


async def fill_market(store: MemoryMarketStore, cross: bool = True, live: bool = True) -> None:
    now = time.time()
    await store.put_assets(
        [
            {
                "symbol": SYMBOL,
                "name": "V100",
                "market": "synthetic_index",
                "pip_size": 0.01,
                "exchange_is_open": live,
                "is_trading_suspended": False,
            }
        ]
    )
    await store.put_tick({"symbol": SYMBOL, "quote": 100.0, "epoch": int(now), "received_at": now})
    await store.put_candles(SYMBOL, strategy.GRANULARITY, live_candles(now, cross=cross))


class World:
    def __init__(self, factory: sessionmaker[DbSession]) -> None:
        self.factory = factory
        self.broker = FakeBroker()
        self.market = MemoryMarketStore()
        self.guard_ok = True
        self.account = f"VRT{uuid.uuid4().hex[:10]}"
        self.user_id = uuid.uuid4()
        self.session_id = uuid.uuid4()
        with factory.begin() as db:
            db.add(
                User(
                    id=self.user_id,
                    email=f"{self.user_id}@example.com",
                    password_hash="x",
                    first_name="Bot",
                )
            )
            db.flush()
            now = datetime.now(UTC)
            db.add(
                Subscription(
                    user_id=self.user_id,
                    plan_code="trial",
                    starts_at=now,
                    ends_at=now + timedelta(days=3),
                )
            )
            db.add(
                TradingSettings(
                    user_id=self.user_id,
                    allowed_symbols=[SYMBOL],
                    timezone="UTC",
                    **risk.DEFAULTS,
                )
            )
            db.add(
                BotSession(
                    id=self.session_id,
                    user_id=self.user_id,
                    account_id=self.account,
                    account_kind="demo",
                    symbol=SYMBOL,
                )
            )

    def runner(self) -> BotRunner:
        journal = Journal(self.factory)
        trading = DerivTrading(self.broker, read_pause=0)

        async def guard() -> bool:
            return self.guard_ok

        return BotRunner(
            self.session_id, journal, trading, Executor(journal, trading, guard), self.market
        )

    def positions(self) -> list[TradingPosition]:
        with self.factory() as db:
            return list(
                db.scalars(
                    select(TradingPosition).where(TradingPosition.session_id == self.session_id)
                )
            )

    def session(self) -> BotSession:
        with self.factory() as db:
            return db.get_one(BotSession, self.session_id)

    def codes(self, kind: str) -> list[str | None]:
        with self.factory() as db:
            return list(
                db.scalars(
                    select(TradingDecision.code).where(
                        TradingDecision.session_id == self.session_id,
                        TradingDecision.kind == kind,
                    )
                )
            )

    def command(self, command: str) -> None:
        with self.factory.begin() as db:
            db.get_one(BotSession, self.session_id).command = command

    def update(self, **values: Any) -> None:
        with self.factory.begin() as db:
            session = db.get_one(BotSession, self.session_id)
            for key, value in values.items():
                setattr(session, key, value)

    def add_position(self, **values: Any) -> uuid.UUID:
        position_id = uuid.uuid4()
        base: dict[str, Any] = {
            "id": position_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "account_id": self.account,
            "symbol": SYMBOL,
            "direction": "up",
            "stake": Decimal(1),
            "multiplier": 100,
            "stop_loss": Decimal("0.5"),
            "peak_profit": Decimal(0),
        }
        with self.factory.begin() as db:
            db.add(TradingPosition(**{**base, **values}))
        return position_id


@pytest.fixture
def world(migrated_engine: Engine) -> World:
    return World(sessionmaker(migrated_engine, expire_on_commit=False))


def steps(world: World, count: int = 1, runner: BotRunner | None = None) -> BotRunner:
    active = runner or world.runner()

    async def main() -> None:
        await fill_market(world.market)
        for _ in range(count):
            await active.step()

    asyncio.run(main())
    return active


def test_signal_opens_one_position_with_mandatory_stop(world: World) -> None:
    steps(world, 3)
    positions = world.positions()
    assert world.broker.buys == 1
    assert len(positions) == 1
    assert positions[0].status == PositionStatus.OPEN
    assert positions[0].stop_loss == Decimal("0.50")
    assert world.session().state == BotState.POSITION_OPEN
    assert world.session().start_balance == Decimal("10000.00")


@pytest.mark.parametrize("live", [True, False])
def test_no_order_without_live_market(world: World, live: bool) -> None:
    runner = world.runner()

    async def main() -> None:
        await fill_market(world.market, live=live)
        if live:
            await world.market.put_tick(
                {"symbol": SYMBOL, "quote": 1.0, "epoch": 1, "received_at": time.time() - 99}
            )
        await runner.step()

    asyncio.run(main())
    assert world.broker.buys == 0
    assert world.codes("order_refused") == ["market.stale" if live else "market.closed"]


def test_nothing_before_reconciliation_when_it_fails(world: World) -> None:
    world.broker.connected = False
    steps(world, 2)
    assert world.broker.buys == 0
    assert world.session().state == BotState.STARTING


def test_lost_answer_never_buys_twice_and_adopts_the_contract(world: World) -> None:
    world.broker.outcome = "unknown_done"
    runner = steps(world, 2)
    assert world.positions()[0].status in (PositionStatus.OPEN, PositionStatus.UNKNOWN)
    world.broker.outcome = "ok"
    steps(world, 3, runner)
    positions = world.positions()
    assert world.broker.buys == 1
    assert [p.status for p in positions] == [PositionStatus.OPEN]
    assert positions[0].contract_id in world.broker.contracts


def test_unexecuted_order_is_voided_after_delay_only(world: World) -> None:
    world.broker.outcome = "unknown_lost"
    runner = steps(world, 2)
    assert world.positions()[0].status == PositionStatus.UNKNOWN
    with world.factory.begin() as db:
        row = db.scalars(
            select(TradingPosition).where(TradingPosition.session_id == world.session_id)
        ).one()
        row.sent_at = datetime.now(UTC) - timedelta(seconds=60)
    steps(world, 1, runner)
    assert world.positions()[0].status == PositionStatus.VOID
    assert world.positions()[0].close_reason == "reconcile.not_executed"


def test_pending_order_blocks_a_second_order_at_database_level(world: World) -> None:
    world.add_position(status=PositionStatus.UNKNOWN, sent_at=datetime.now(UTC))
    with pytest.raises(IntegrityError):
        world.add_position(status=PositionStatus.OPENING)


def test_crash_before_sending_is_voided_on_restart(world: World) -> None:
    world.add_position(status=PositionStatus.OPENING)
    steps(world, 1)
    reasons = {p.close_reason for p in world.positions()}
    assert "reconcile.never_sent" in reasons


def test_crash_after_sending_is_found_in_statement(world: World) -> None:
    contract_id = world.broker._record()
    world.add_position(status=PositionStatus.OPENING, sent_at=datetime.now(UTC))
    steps(world, 1)
    position = world.positions()[0]
    assert (position.status, position.contract_id) == (PositionStatus.OPEN, contract_id)
    assert world.broker.buys == 0


def test_contract_already_known_is_not_adopted_twice(world: World) -> None:
    contract_id = world.broker._record()
    world.add_position(status=PositionStatus.OPEN, contract_id=contract_id, buy_price=Decimal(1))
    world.add_position(
        status=PositionStatus.UNKNOWN, sent_at=datetime.now(UTC) - timedelta(seconds=60)
    )
    steps(world, 1)
    statuses = sorted(p.status for p in world.positions())
    assert statuses == ["open", "void"]


def test_position_closed_while_away_is_recorded_on_restart(world: World) -> None:
    contract_id = world.broker._record()
    world.broker.close(contract_id, 0.72)
    world.add_position(status=PositionStatus.OPEN, contract_id=contract_id, buy_price=Decimal(1))
    steps(world, 1)
    position = world.positions()[0]
    assert position.status == PositionStatus.CLOSED
    assert position.net_result == Decimal("-0.28")
    assert position.close_reason == "deriv"


def test_foreign_contract_is_traced_and_never_touched(world: World) -> None:
    world.broker.foreign.append({"contract_id": 77})
    steps(world, 1)
    assert world.broker.sells == []
    assert len(world.codes("reconcile_foreign")) == 1


def test_lost_lease_stops_the_order_before_sending(world: World) -> None:
    world.guard_ok = False
    steps(world, 1)
    assert world.broker.buys == 0
    assert world.positions()[0].close_reason == "order.lease_lost"


def test_refused_order_is_void_without_retry(world: World) -> None:
    world.broker.outcome = "rejected"
    steps(world, 3)
    assert world.broker.buys == 1
    assert world.positions()[0].status == PositionStatus.VOID


def test_stop_below_deriv_minimum_refuses_before_buying(world: World) -> None:
    world.broker.proposal_extra = {"validation_params": {"stop_loss": {"min": "0.70"}}}
    steps(world, 1)
    assert world.broker.buys == 0
    assert world.positions()[0].close_reason == "risk.stop_below_minimum"


def open_one(world: World) -> tuple[BotRunner, int]:
    runner = steps(world, 2)
    contract_id = world.positions()[0].contract_id
    assert contract_id is not None
    return runner, contract_id


def test_gain_moves_stop_to_floor_then_ratchet_sells(world: World) -> None:
    runner, contract_id = open_one(world)
    contract = world.broker.contracts[contract_id]
    contract["profit"] = 0.8
    steps(world, 1, runner)
    assert world.broker.updates == [{"stop_loss": 0.04}]
    contract["profit"] = 0.3
    steps(world, 1, runner)
    position = world.positions()[0]
    assert world.broker.sells == [contract_id]
    assert (position.status, position.close_reason) == (PositionStatus.CLOSED, "ratchet")
    assert position.net_result == Decimal("0.30")


def test_floor_uses_the_minimum_stated_by_deriv(world: World) -> None:
    runner, contract_id = open_one(world)
    world.broker.update_error = "LimitOrderAmountTooLow"
    world.broker.update_message = "Enter an amount equal to or higher than 0.31."
    world.broker.contracts[contract_id]["profit"] = 0.2
    steps(world, 1, runner)
    world.broker.update_error = None
    runner._tracked[contract_id].updated_at = 0
    steps(world, 1, runner)
    assert world.broker.updates == [{"stop_loss": 0.31}]


def test_floor_steps_up_when_the_stated_minimum_is_rounded(world: World) -> None:
    runner, contract_id = open_one(world)
    world.broker.update_error = "LimitOrderAmountTooLow"
    world.broker.update_message = "Enter an amount equal to or higher than 0.04."
    world.broker.contracts[contract_id]["profit"] = 0.2
    steps(world, 1, runner)
    world.broker.update_error = None
    runner._tracked[contract_id].updated_at = 0
    steps(world, 1, runner)
    assert world.broker.updates == [{"stop_loss": 0.05}]


def test_refused_floor_keeps_the_initial_stop(world: World) -> None:
    runner, contract_id = open_one(world)
    world.broker.update_error = "LimitOrderAmountTooLow"
    world.broker.contracts[contract_id]["profit"] = 0.2
    steps(world, 3, runner)
    assert world.codes("floor_refused") == ["LimitOrderAmountTooLow"]
    assert world.positions()[0].current_stop == Decimal("0.50")


def test_missing_stop_is_restored(world: World) -> None:
    runner, contract_id = open_one(world)
    world.broker.contracts[contract_id]["limit_order"] = {}
    steps(world, 1, runner)
    assert world.broker.updates == [{"stop_loss": 0.5}]


def test_unrestorable_stop_closes_the_position(world: World) -> None:
    runner, contract_id = open_one(world)
    world.broker.contracts[contract_id]["limit_order"] = {}
    world.broker.update_error = "Nope"
    steps(world, 1, runner)
    assert world.positions()[0].close_reason == "no_stop"


def test_stop_hit_at_deriv_is_recorded(world: World) -> None:
    runner, contract_id = open_one(world)
    world.broker.close(contract_id, 0.47)
    steps(world, 1, runner)
    position = world.positions()[0]
    assert position.net_result == Decimal("-0.53")
    assert position.close_reason == "deriv"


def test_sell_on_contract_just_closed_is_not_an_error(world: World) -> None:
    runner, contract_id = open_one(world)
    with world.factory.begin() as db:
        db.scalars(select(TradingPosition)).all()
    world.command("emergency")
    world.broker.sell_error = "BetExpired"
    steps(world, 1, runner)
    world.broker.close(contract_id, 0.9)
    steps(world, 2, runner)
    assert world.positions()[0].status == PositionStatus.CLOSED
    assert world.session().state == BotState.STOPPED


def test_entry_tick_wait_postpones_the_sale(world: World) -> None:
    runner, contract_id = open_one(world)
    world.broker.contracts[contract_id]["is_valid_to_sell"] = 0
    world.command("emergency")
    steps(world, 1, runner)
    assert world.broker.sells == []
    world.broker.contracts[contract_id]["is_valid_to_sell"] = 1
    runner._tracked[contract_id].seen_at = 0
    steps(world, 1, runner)
    assert world.broker.sells == [contract_id]


def test_emergency_closes_positions_and_ends_session(world: World) -> None:
    runner, contract_id = open_one(world)
    world.command("emergency")
    steps(world, 2, runner)
    assert world.broker.sells == [contract_id]
    session = world.session()
    assert (session.state, session.stop_reason) == (BotState.STOPPED, "emergency")
    assert session.ended_at is not None
    assert world.positions()[0].close_reason == "emergency"


def test_stop_keeps_managing_until_position_closes(world: World) -> None:
    runner, contract_id = open_one(world)
    world.command("stop")
    steps(world, 2, runner)
    assert world.session().state == BotState.STOPPING
    assert world.broker.sells == []
    world.broker.close(contract_id, 1.2)
    steps(world, 2, runner)
    assert world.session().state == BotState.STOPPED


def test_pause_blocks_entries_and_resume_allows_them(world: World) -> None:
    world.command("pause")
    runner = steps(world, 2)
    assert world.broker.buys == 0
    assert world.session().state == BotState.PAUSED
    world.command("resume")
    steps(world, 2, runner)
    assert world.broker.buys == 1


def test_manual_close(world: World) -> None:
    runner, contract_id = open_one(world)
    with world.factory.begin() as db:
        db.scalars(
            select(TradingPosition).where(TradingPosition.contract_id == contract_id)
        ).one().close_requested = True
    steps(world, 1, runner)
    assert world.positions()[0].close_reason == "client"


def losing_positions(world: World, results: list[str]) -> None:
    now = datetime.now(UTC)
    for index, result in enumerate(results):
        world.add_position(
            status=PositionStatus.CLOSED,
            net_result=Decimal(result),
            closed_at=now - timedelta(seconds=len(results) - index),
        )


def test_consecutive_losses_pause_then_resume_after_delay(world: World) -> None:
    losing_positions(world, ["-0.5", "-0.5", "-0.5"])
    runner = steps(world, 1)
    session = world.session()
    assert session.state == BotState.PAUSED
    assert session.paused_until is not None
    assert world.broker.buys == 0
    world.update(paused_until=datetime.now(UTC) - timedelta(seconds=1))
    steps(world, 2, runner)
    assert world.broker.buys == 1


def test_session_loss_limit_stops_new_positions(world: World) -> None:
    world.update(start_balance=Decimal(100))
    losing_positions(world, ["-1", "2", "-3"])
    steps(world, 2)
    session = world.session()
    assert session.state == BotState.LIMIT_REACHED
    assert session.stop_reason == "risk.session_loss_limit"
    assert world.broker.buys == 0


def test_session_target_stops_new_positions(world: World) -> None:
    world.update(start_balance=Decimal(100))
    losing_positions(world, ["3"])
    steps(world, 2)
    assert world.session().state == BotState.TARGET_REACHED
    assert world.broker.buys == 0


def test_prolonged_disconnection_is_an_error_then_reconciles(world: World) -> None:
    clock = {"now": 0.0}
    journal = Journal(world.factory)
    trading = DerivTrading(world.broker, read_pause=0)

    async def guard() -> bool:
        return True

    runner = BotRunner(
        world.session_id, journal, trading, Executor(journal, trading, guard), world.market,
        monotonic=lambda: clock["now"],
    )  # fmt: skip
    steps(world, 1, runner)
    world.broker.connected = False
    steps(world, 1, runner)
    clock["now"] += 61
    steps(world, 1, runner)
    assert world.session().state == BotState.ERROR
    world.broker.connected = True
    steps(world, 1, runner)
    assert world.session().state != BotState.ERROR
    assert len(world.codes("reconciled")) == 2


def test_real_session_never_buys(world: World) -> None:
    world.update(account_kind="real")
    steps(world, 2)
    assert world.broker.buys == 0
    assert "risk.real_account_disabled" in world.codes("order_refused")


def test_decisions_cannot_be_rewritten(world: World) -> None:
    steps(world, 1)
    with (
        world.factory.begin() as db,
        pytest.raises(DBAPIError),
    ):
        db.execute(text("DELETE FROM trading_decisions"))


def test_two_active_bots_on_one_account_are_refused(world: World) -> None:
    with pytest.raises(IntegrityError), world.factory.begin() as db:
        db.add(
            BotSession(
                user_id=world.user_id,
                account_id=world.account,
                account_kind="demo",
                symbol=SYMBOL,
            )
        )


@pytest.fixture
def api(
    migrated_engine: Engine,
) -> Iterator[tuple[TestClient, MemoryMarketStore, Callable[[], str]]]:
    factory = sessionmaker(migrated_engine, expire_on_commit=False)
    store = MemoryMarketStore()
    mailer = MemoryMailer()
    app = create_app(
        Settings(
            environment="test",
            session_cookie_secure=False,
            allowed_origins=[ORIGIN],
            market_symbols=[SYMBOL],
        ),
        session_factory=factory,
        mailer=mailer,
        failures=MemoryFailureCounter(),
        market=store,
    )
    client = TestClient(app, base_url="http://127.0.0.1:18000", headers={"origin": ORIGIN})
    email = f"bot-{uuid.uuid4().hex[:8]}@example.com"
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
        connection.execute(
            text(
                "INSERT INTO subscriptions (id, user_id, plan_code, starts_at, ends_at) "
                "SELECT gen_random_uuid(), id, 'trial', now(), now() + interval '3 days' "
                "FROM users WHERE email = :e"
            ),
            {"e": email},
        )
    assert (
        client.post("/auth/login", json={"email": email, "password": PASSWORD}).status_code == 200
    )

    def connect(kind: str = "demo") -> str:
        account = f"VRT{uuid.uuid4().hex[:10]}"
        with factory.begin() as db:
            user = db.scalars(select(User).where(User.email == email)).one()
            db.add(
                DerivConnectionRecord(
                    user_id=user.id,
                    auth_method="pat",
                    token_encrypted="x",
                    account_id=account,
                    account_kind=kind,
                    currency="USD",
                )
            )
        return account

    yield client, store, connect
    client.close()


def valid_settings(**changes: Any) -> dict[str, Any]:
    values = {k: str(v) for k, v in risk.DEFAULTS.items()}
    return {**values, "allowed_symbols": [SYMBOL], "timezone": "Africa/Kinshasa", **changes}


def test_settings_defaults_and_out_of_range_refused(api: Any) -> None:
    client, _, _ = api
    assert client.get("/trading/settings").json()["settings"]["stake"] == "1"
    refused = client.put("/trading/settings", json=valid_settings(stake="51"))
    assert (refused.status_code, refused.json()["error"]) == (422, "trading.invalid_settings")
    assert (
        client.put("/trading/settings", json=valid_settings(stop_loss_pct="0")).status_code == 422
    )
    assert (
        client.put("/trading/settings", json=valid_settings(timezone="Mars/Base")).status_code
        == 422
    )
    accepted = client.put("/trading/settings", json=valid_settings(stake="2"))
    assert Decimal(accepted.json()["settings"]["stake"]) == 2


def test_start_requires_connection_and_live_market(api: Any) -> None:
    client, store, connect = api
    body = {"symbol": SYMBOL}
    assert client.post("/trading/bot/start", json=body).json()["error"] == "trading.market_not_live"
    asyncio.run(fill_market(store))
    assert client.post("/trading/bot/start", json=body).json()["error"] == "deriv.not_connected"
    connect()
    started = client.post("/trading/bot/start", json=body)
    assert started.status_code == 201
    again = client.post("/trading/bot/start", json=body)
    assert (again.status_code, again.json()["error"]) == (409, "trading.bot_already_active")
    state = client.get("/trading/bot").json()
    assert state["session"]["state"] == "starting"
    assert client.post("/trading/bot/command/emergency").status_code == 202


def test_every_compatible_asset_is_allowed_by_default(api: Any) -> None:
    client, store, connect = api
    asyncio.run(fill_market(store))
    connect()
    assert client.get("/trading/settings").json()["settings"]["all_symbols"] is True
    assert client.post("/trading/bot/start", json={"symbol": SYMBOL}).status_code == 201


def test_client_can_still_restrict_the_list(api: Any) -> None:
    client, store, connect = api
    asyncio.run(fill_market(store))
    connect()
    assets = asyncio.run(store.get_assets())["assets"]
    asyncio.run(store.put_assets([*assets, {**assets[0], "symbol": "OTHER"}]))
    tick = asyncio.run(store.get_ticks([SYMBOL]))[SYMBOL]
    asyncio.run(store.put_tick({**tick, "symbol": "OTHER"}))
    body = valid_settings(all_symbols=False)
    assert client.put("/trading/settings", json=body).status_code == 200
    refused = client.post("/trading/bot/start", json={"symbol": "OTHER"})
    assert (refused.status_code, refused.json()["error"]) == (422, "trading.symbol_not_allowed")
    assert client.post("/trading/bot/start", json={"symbol": SYMBOL}).status_code == 201


def test_multiplier_shown_is_the_one_the_engine_will_use(api: Any) -> None:
    client, store, _ = api
    asyncio.run(fill_market(store))
    assets = asyncio.run(store.get_assets())["assets"]
    asyncio.run(store.put_assets([{**assets[0], "multiplier_range": [750, 2000]}]))
    view = client.get("/trading/multiplier", params={"symbol": SYMBOL}).json()
    assert (view["wanted"], view["used"]) == (100, 750)


def test_closed_market_refuses_to_start(api: Any) -> None:
    client, store, connect = api
    connect()
    asyncio.run(fill_market(store, live=False))
    response = client.post("/trading/bot/start", json={"symbol": SYMBOL})
    assert response.json()["error"] == "trading.market_not_live"


def test_real_account_cannot_start(api: Any) -> None:
    client, store, connect = api
    connect("real")
    asyncio.run(fill_market(store))
    response = client.post("/trading/bot/start", json={"symbol": SYMBOL})
    assert (response.status_code, response.json()["error"]) == (403, "deriv.real_disabled")


def test_command_without_bot_and_unknown_command(api: Any) -> None:
    client, _, _ = api
    assert client.post("/trading/bot/command/stop").json()["error"] == "trading.no_active_bot"
    assert client.post("/trading/bot/command/explode").status_code == 422


def test_client_cannot_close_someone_elses_position(api: Any, world: World) -> None:
    client, _, _ = api
    position_id = world.add_position(status=PositionStatus.OPEN)
    response = client.post(f"/trading/positions/{position_id}/close")
    assert (response.status_code, response.json()["error"]) == (404, "trading.position_not_found")


def test_history_lists_only_own_rows(api: Any, world: World) -> None:
    client, _, _ = api
    world.add_position(status=PositionStatus.CLOSED)
    assert client.get("/trading/positions").json()["positions"] == []
    assert client.get("/trading/decisions").json()["decisions"] == []


def test_heartbeat_tells_whether_the_engine_really_runs(world: World) -> None:
    steps(world, 1)
    session = world.session()
    assert session.heartbeat_at is not None
    assert session.deriv_connected is True


def test_spots_are_saved_for_the_chart(world: World) -> None:
    runner, contract_id = open_one(world)
    world.broker.contracts[contract_id].update(
        entry_spot="1250.25",
        limit_order={"stop_loss": {"order_amount": -0.5, "value": "1249.00"}},
    )
    steps(world, 1, runner)
    position = world.positions()[0]
    assert position.entry_spot == Decimal("1250.25")
    assert position.stop_spot == Decimal("1249")


def test_settings_error_names_the_fields(api: Any) -> None:
    client, _, _ = api
    response = client.put(
        "/trading/settings", json=valid_settings(stake="51", timezone="Mars/Base")
    )
    assert response.json()["fields"] == ["stake", "timezone"]
    ranges = client.get("/trading/settings").json()
    assert ranges["ranges"]["stake"] == {"min": "1", "max": "50"}
    assert "activation_r" in ranges["provisional"]


def test_summary_counts_only_real_closed_positions(api: Any, migrated_engine: Engine) -> None:
    client, _, _ = api
    empty = client.get("/trading/summary").json()
    assert (empty["trades"], empty["win_rate"], empty["curve"]) == (0, None, [])
    factory = sessionmaker(migrated_engine, expire_on_commit=False)
    with factory.begin() as db:
        user = db.scalars(
            select(User).where(User.email.like("bot-%")).order_by(User.created_at.desc())
        ).first()
        assert user is not None
        session = BotSession(
            user_id=user.id, account_id=f"V{uuid.uuid4().hex[:10]}",
            account_kind="demo", symbol=SYMBOL, ended_at=datetime.now(UTC),
            state=BotState.STOPPED,
        )  # fmt: skip
        db.add(session)
        db.flush()
        for net in ("-0.50", "0.80", "0.20"):
            db.add(
                TradingPosition(
                    session_id=session.id, user_id=user.id, account_id=session.account_id,
                    symbol=SYMBOL, direction="up", stake=Decimal(1), multiplier=100,
                    stop_loss=Decimal("0.5"), status=PositionStatus.CLOSED,
                    net_result=Decimal(net), closed_at=datetime.now(UTC),
                    peak_profit=Decimal(0),
                )
            )  # fmt: skip
    data = client.get("/trading/summary").json()
    assert (data["trades"], data["wins"], data["losses"]) == (3, 2, 1)
    assert data["total_net"] == "0.50"
    assert data["curve"][-1]["net"] == "0.50"
    assert client.get("/trading/bot").json()["last_session"]["state"] == "stopped"
    history = client.get("/trading/positions", params={"closed": True}).json()["positions"]
    assert {p["account_kind"] for p in history} == {"demo"}


def test_idle_signals_can_be_hidden(world: World, migrated_engine: Engine) -> None:
    steps(world, 1)
    with world.factory() as db:
        kinds = list(db.scalars(select(TradingDecision.kind)))
    assert "reconciled" in kinds


def test_deriv_cannot_be_disconnected_while_the_bot_runs(api: Any) -> None:
    client, store, connect = api
    connect()
    asyncio.run(fill_market(store))
    assert client.post("/trading/bot/start", json={"symbol": SYMBOL}).status_code == 201
    response = client.delete("/deriv/connection")
    assert (response.status_code, response.json()["error"]) == (409, "deriv.bot_active")


def test_expired_access_stops_entries_and_keeps_protecting_positions(world: World) -> None:
    runner, contract_id = open_one(world)
    with world.factory.begin() as db:
        rows = db.scalars(select(Subscription).where(Subscription.user_id == world.user_id))
        for row in rows:
            row.ends_at = datetime.now(UTC) - timedelta(seconds=1)
    steps(world, 2, runner)
    session = world.session()
    assert (session.state, session.stop_reason) == (BotState.STOPPING, "billing.expired")
    assert world.broker.sells == []
    assert world.positions()[0].status == PositionStatus.OPEN
    world.broker.close(contract_id, 0.9)
    steps(world, 2, runner)
    assert world.session().state == BotState.STOPPED
    assert world.broker.buys == 1


def test_expired_access_cannot_start_a_bot(api: Any, migrated_engine: Engine) -> None:
    client, store, connect = api
    connect()
    asyncio.run(fill_market(store))
    email = client.get("/auth/me").json()["user"]["email"]
    with migrated_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE subscriptions SET ends_at = now() - interval '1 minute' "
                "WHERE user_id = (SELECT id FROM users WHERE email = :e)"
            ),
            {"e": email},
        )
    response = client.post("/trading/bot/start", json={"symbol": SYMBOL})
    assert (response.status_code, response.json()["error"]) == (402, "billing.access_required")


def test_buy_row_shape() -> None:
    assert Buy(1, Decimal(1), 2, "x").contract_id == 1
