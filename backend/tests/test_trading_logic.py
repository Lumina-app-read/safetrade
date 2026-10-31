"""Module de risque, sorties et stratégie : fonctions pures, un test par limite."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from app.broker.deriv_trading import Buy, DerivTrading, matches
from app.trading import exits, risk, strategy

D = Decimal
NOW = datetime(2026, 10, 31, 12, tzinfo=UTC)


def params(**changes: Any) -> Any:
    return SimpleNamespace(**{**risk.DEFAULTS, **changes})


def check(**changes: Any) -> risk.OrderCheck:
    values: dict[str, Any] = {
        "params": params(),
        "stake": D("1"),
        "stop_loss": D("0.5"),
        "balance": D("1000"),
        "start_balance": D("1000"),
        "open_exposure": D("0"),
        "open_positions": 0,
        "pending_orders": 0,
        "session_net": D("0"),
        "day_net": D("0"),
        "day_start_balance": D("1000"),
        "consecutive_losses": 0,
        "paused_until": None,
        "now": NOW,
        "market_refusal": None,
        "account_kind": "demo",
        "real_enabled": False,
        "symbol_allowed": True,
        "connected": True,
    }
    return risk.OrderCheck(**{**values, **changes})


def test_healthy_order_is_accepted() -> None:
    assert risk.order_refusal(check()) is None


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"account_kind": "real"}, "risk.real_account_disabled"),
        ({"connected": False}, "risk.not_connected"),
        ({"symbol_allowed": False}, "risk.symbol_not_allowed"),
        ({"market_refusal": "market.stale"}, "market.stale"),
        ({"pending_orders": 1}, "risk.order_pending"),
        ({"paused_until": NOW + timedelta(minutes=1)}, "risk.paused"),
        ({"consecutive_losses": 3}, "risk.consecutive_losses"),
        ({"session_net": D("-20")}, "risk.session_loss_limit"),
        ({"day_net": D("-50")}, "risk.daily_loss_limit"),
        ({"session_net": D("20"), "day_net": D("20")}, "risk.session_target"),
        ({"day_net": D("50")}, "risk.daily_target"),
        ({"open_positions": 1}, "risk.max_positions"),
        ({"stop_loss": None}, "risk.stop_loss_required"),
        ({"stop_loss": D("0")}, "risk.stop_loss_required"),
        ({"stop_loss": D("1.5")}, "risk.stop_loss_above_stake"),
        ({"stake": D("2")}, "risk.stake_changed"),
        ({"balance": D("0.5"), "start_balance": D("1000")}, "risk.insufficient_balance"),
        ({"balance": D("4")}, "risk.capital_exposure"),
        ({"open_exposure": D("200"), "params": params(max_positions=3)}, "risk.capital_exposure"),
        ({"session_net": D("-19.8")}, "risk.loss_room"),
        ({"day_net": D("-49.8")}, "risk.loss_room"),
    ],
)
def test_each_limit_refuses_the_order(changes: dict[str, Any], expected: str) -> None:
    assert risk.order_refusal(check(**changes)) == expected


def test_slippage_counts_in_the_loss_room() -> None:
    assert risk.worst_case_loss(D("0.5")) == D("0.58")
    # Le stop de 0,50 tient dans la marge restante, pas son glissement possible.
    assert risk.order_refusal(check(session_net=D("-19.45"))) == "risk.loss_room"
    assert risk.order_refusal(check(session_net=D("-19.40"))) is None


def test_stake_above_absolute_range_is_refused() -> None:
    order = check(stake=D("60"), params=params(stake=D("60")), balance=D("100000"))
    assert risk.order_refusal(order) == "risk.stake_out_of_range"


def test_real_account_needs_switch_and_has_lower_stake_cap() -> None:
    order = check(
        account_kind="real", real_enabled=True, stake=D("11"), params=params(stake=D("11"))
    )
    assert risk.order_refusal(order) == "risk.stake_out_of_range"


def test_expired_pause_no_longer_refuses() -> None:
    assert risk.order_refusal(check(paused_until=NOW - timedelta(seconds=1))) is None


def complete(**changes: Any) -> dict[str, Any]:
    return {**risk.DEFAULTS, **changes}


def test_defaults_are_in_range() -> None:
    assert risk.out_of_range(complete()) == []


@pytest.mark.parametrize("field", list(risk.RANGES))
def test_each_field_has_enforced_bounds(field: str) -> None:
    low, high = risk.RANGES[field]
    assert risk.out_of_range(complete(**{field: low - D("0.01")})) == [field]
    assert risk.out_of_range(complete(**{field: high + D("0.01")})) == [field]


def test_missing_field_is_refused() -> None:
    values = complete()
    del values["stop_loss_pct"]
    assert risk.out_of_range(values) == ["stop_loss_pct"]


def test_real_stake_cap() -> None:
    assert risk.out_of_range(complete(stake=D("11")), real=True) == ["stake"]
    assert risk.out_of_range(complete(stake=D("11"))) == []


def test_stop_amount_rounds_to_cents() -> None:
    assert risk.stop_amount(params(stake=D("1.33"), stop_loss_pct=D("33"))) == D("0.44")


@pytest.mark.parametrize(
    ("proposal", "expected"),
    [
        ({"ask_price": 1.0, "commission": 0.1}, None),
        ({"ask_price": 1.0}, "risk.proposal_incomplete"),
        ({"commission": 0.1}, "risk.proposal_incomplete"),
        ({"ask_price": 1.2, "commission": 0.1}, "risk.price_above_stake"),
        (
            {
                "ask_price": 1,
                "commission": 0.1,
                "validation_params": {"stop_loss": {"min": "0.60"}},
            },
            "risk.stop_below_minimum",
        ),
        (
            {
                "ask_price": 1,
                "commission": 0.1,
                "validation_params": {"stop_loss": {"max": "0.40"}},
            },
            "risk.stop_above_maximum",
        ),
    ],
)
def test_proposal_checks(proposal: dict[str, Any], expected: str | None) -> None:
    assert risk.proposal_refusal(proposal, D("1"), D("0.5")) == expected


EXIT = exits.ExitParams(activation_r=D("1"), locked_fraction=D("0.5"))
BASE = exits.PositionView(
    profit=D("-0.1"), peak_profit=D("0"), commission=D("0.1"), risk=D("0.5"), current_stop=D("0.5")
)


def test_loss_is_left_to_the_stop_at_deriv() -> None:
    assert exits.decide(BASE, EXIT).kind == "hold"


def test_gain_tightens_the_stop_to_the_floor() -> None:
    action = exits.decide(replace(BASE, profit=D("0.05")), EXIT)
    assert (action.kind, action.stop_loss) == ("tighten", D("0.11"))


def test_stop_is_never_widened() -> None:
    view = replace(BASE, profit=D("0.05"), current_stop=D("0.11"))
    assert exits.decide(view, EXIT).kind == "hold"
    view = replace(BASE, profit=D("0.05"), current_stop=D("0.05"))
    assert exits.decide(view, EXIT).kind == "hold"


def test_no_exit_before_activation() -> None:
    view = replace(BASE, profit=D("0.1"), peak_profit=D("0.4"), current_stop=D("0.11"))
    assert exits.decide(view, EXIT).kind == "hold"


def test_activation_covers_fees_even_with_small_risk() -> None:
    view = replace(BASE, commission=D("1"), risk=D("0.5"))
    assert exits.activation_level(view, EXIT) == D("2.01")


def test_ratchet_sells_when_gain_gives_back_locked_share() -> None:
    held = replace(BASE, profit=D("0.6"), peak_profit=D("1"), current_stop=D("0.11"))
    assert exits.decide(held, EXIT).kind == "hold"
    given_back = replace(held, profit=D("0.5"))
    action = exits.decide(given_back, EXIT)
    assert (action.kind, action.reason) == ("sell", "ratchet")


def test_ratchet_also_sells_a_position_turned_negative() -> None:
    view = replace(BASE, profit=D("-0.02"), peak_profit=D("1"))
    assert exits.decide(view, EXIT).kind == "sell"


def candles_from(closes: list[float]) -> list[dict[str, Any]]:
    return [
        {"epoch": 60 * i, "open": c, "high": c + 0.5, "low": c - 0.5, "close": c}
        for i, c in enumerate(closes)
    ]


def test_cross_up_and_down() -> None:
    falling = [100 - i * 0.1 for i in range(36)]
    assert strategy.evaluate(candles_from([*falling, 110.0])).direction == "up"
    rising = [100 + i * 0.1 for i in range(36)]
    assert strategy.evaluate(candles_from([*rising, 90.0])).direction == "down"


def test_no_cross_waits() -> None:
    rising = [100 + i * 0.1 for i in range(37)]
    signal = strategy.evaluate(candles_from(rising))
    assert (signal.direction, signal.reason) == (None, "strategy.no_cross")


def test_flat_market_waits() -> None:
    rows = [
        {"epoch": 60 * i, "open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0}
        for i in range(37)
    ]
    assert strategy.evaluate(rows).reason == "strategy.flat_market"


def test_needed_candles_are_enough_for_the_indicators() -> None:
    assert strategy.NEEDED_CANDLES > strategy.SLOW + strategy.ATR_PERIOD


def test_stop_cannot_be_removed() -> None:
    import asyncio

    trading = DerivTrading(None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="stop loss"):
        asyncio.run(trading.update_stop(1, None))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="stop loss"):
        asyncio.run(trading.update_stop(1, D("0")))


def test_shortcode_match_handles_symbols_with_underscore() -> None:
    buy = Buy(1, D("1"), 100, "MULTUP_R_100_1.00_100_1793435127_4947091199_0_0.25_N1_0")
    assert matches(buy, "R_100", "up", D("1"), 100)
    assert not matches(buy, "R_100", "down", D("1"), 100)
    assert not matches(buy, "R_100", "up", D("2"), 100)
    assert not matches(buy, "R_100", "up", D("1"), 200)
