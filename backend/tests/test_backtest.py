"""Banc d'essai : scénarios de cours écrits à la main, sans réseau."""

from itertools import pairwise
from pathlib import Path

import pytest

from app.backtest.engine import Params, Trade, candles_of, simulate
from app.backtest.fetch import last_epoch
from app.backtest.report import MIN_TRADES, grid, split, summarize, walk_forward
from app.backtest.run import load_ticks, render
from app.trading import strategy

BASE = Params(multiplier=100, commission=0.02, stop_minimum=0.10)
START = 1_000_020  # début de minute


def rising(minutes: int, step: float = 1.0) -> tuple[list[int], list[float]]:
    prices: list[float] = []
    for minute in range(minutes):
        prices.extend([1000.0 + minute * step] * 60)
    return [START + index for index in range(len(prices))], prices


def test_candles_follow_the_ticks() -> None:
    times = [START, START + 10, START + 59, START + 60]
    candles = candles_of(times, [10.0, 12.0, 9.0, 11.0])
    assert candles[0] == {"epoch": START, "open": 10.0, "high": 12.0, "low": 9.0, "close": 9.0}
    assert candles[1]["epoch"] == START + 60


def scenario() -> tuple[list[int], list[float], Params]:
    """Baisse lente puis forte hausse : croisement à la hausse, puis repli qui clôture."""
    prices: list[float] = []
    for minute in range(60):
        level = 1000.0 - minute * 0.2
        prices.extend([level] * 60)
    base = prices[-1]
    for minute in range(12):
        prices.extend([base + (minute + 1) * 2.0] * 60)
    prices.extend([base] * 120)
    return [START + index for index in range(len(prices))], prices, BASE


def signal_index(times: list[int], prices: list[float], params: Params) -> int:
    trades = simulate(times, prices, params)
    assert trades, "le scénario doit produire une entrée"
    return times.index(trades[0].opened_at)


def with_path(path: list[float], params: Params = BASE) -> Trade:
    """Remplace tout ce qui suit l'entrée par `path`, en variations relatives au cours d'entrée."""
    times, prices, _ = scenario()
    entry_at = signal_index(times, prices, params)
    entry = prices[entry_at]
    head = prices[: entry_at + 1]
    tail = [entry * (1 + move) for move in path]
    full = head + tail
    return simulate([START + index for index in range(len(full))], full, params)[0]


def test_stop_fires_at_the_tick_that_crosses_it() -> None:
    trade = with_path([-0.001, -0.004, -0.0047, -0.0052, -0.009])
    # Mise 1, multiplicateur 100, -0,52 % : -0,52, plus 0,02 de commission. Le stop part ici.
    assert (trade.reason, trade.net) == ("stop", -0.54)


def test_a_price_gap_gives_real_slippage_beyond_the_stop() -> None:
    trade = with_path([-0.001, -0.008, -0.009])
    assert (trade.reason, trade.net) == ("stop", -0.82)


def test_stop_out_caps_the_loss_at_the_stake() -> None:
    trade = with_path([-0.001, -0.05, -0.06])
    assert (trade.reason, trade.net) == ("stop_out", -1.0)


def test_commission_is_always_counted() -> None:
    trade = with_path([0.0, 0.0, -0.0052])
    assert trade.net == pytest.approx(-0.54)
    assert trade.peak == 0.0  # comme le moteur, le pic part de zéro


def test_ratchet_sells_at_the_next_tick() -> None:
    # Pic à +0,78 : activation à 1 R, soit 0,50. Niveau gardé 0,39 ; vente au tick suivant.
    trade = with_path([0.002, 0.008, 0.0038, 0.0030, 0.0])
    assert (trade.reason, trade.peak, trade.net) == ("ratchet", 0.78, 0.28)


def test_floor_set_in_gain_limits_a_later_loss() -> None:
    # En gain : plancher à 0,10 (minimum Deriv de ce scénario). Le retournement sort à -0,10.
    trade = with_path([0.001, -0.0009, -0.004])
    assert trade.reason == "floor"
    assert trade.net == pytest.approx(-0.11)


def test_position_open_at_the_end_of_data_is_not_invented() -> None:
    times, prices, params = scenario()
    entry_at = signal_index(times, prices, params)
    short = prices[: entry_at + 1] + [prices[entry_at]] * 3  # ni stop ni sortie atteints
    assert simulate([START + i for i in range(len(short))], short, params) == []


def test_future_ticks_never_change_past_decisions() -> None:
    times, prices, params = scenario()
    complete = simulate(times, prices, params)
    first = complete[0]
    cut = times.index(first.closed_at) + 2
    changed = prices[:cut] + [price * 3 for price in prices[cut:]]
    assert simulate(times, changed, params)[0] == first


def test_trade_needs_enough_candles() -> None:
    times, prices = rising(strategy.NEEDED_CANDLES - 2)
    assert simulate(times, prices, BASE) == []


def test_missing_candle_blocks_the_entry_like_the_engine() -> None:
    times, prices, params = scenario()
    entry_at = signal_index(times, prices, params)
    hole = times[entry_at] - 300
    kept = [(t, p) for t, p in zip(times, prices, strict=True) if not hole - 120 <= t < hole]
    without = simulate([t for t, _ in kept], [p for _, p in kept], params)
    assert all(trade.opened_at != times[entry_at] for trade in without)


def test_pause_after_consecutive_losses() -> None:
    times: list[int] = []
    prices: list[float] = []
    level = 1000.0
    # Va-et-vient rapide : chaque croisement perd, la pause doit espacer les entrées.
    for minute in range(600):
        level += 2.5 if (minute // 12) % 2 == 0 else -2.5
        prices.extend([level] * 60)
    times = [START + index for index in range(len(prices))]
    params = Params(multiplier=400, commission=0.02, stop_minimum=0.10, max_consecutive_losses=2)
    trades = simulate(times, prices, params)
    assert len(trades) >= 4
    run = 0
    for before, after in pairwise(trades):
        run = run + 1 if before.net < 0 else 0
        if run == 2:
            assert after.opened_at >= before.closed_at + params.pause_minutes * 60
            run = 0


def test_random_direction_is_reproducible_and_keeps_the_entries() -> None:
    times, prices, params = scenario()
    first = Params(**{**params.__dict__, "random_direction": True, "seed": 7})
    assert simulate(times, prices, first) == simulate(times, prices, first)


def test_summary_matches_a_hand_calculation() -> None:
    nets = [1.0, -0.5, 1.0, -0.5, -0.5]
    trades = [Trade(0, 1, "up", net, 0.0, "stop") for net in nets]
    result = summarize(trades)
    assert result.trades == 5
    assert result.win_rate == pytest.approx(0.4)
    assert result.net == pytest.approx(0.5)
    assert result.expectancy == pytest.approx(0.1)
    assert result.breakeven_win_rate == pytest.approx(0.5 / 1.5)
    assert result.profit_factor == pytest.approx(2 / 1.5)
    assert result.max_drawdown == pytest.approx(1.0)
    assert result.reasons == {"stop": 5}


def test_small_samples_never_get_a_verdict() -> None:
    trades = [Trade(0, 1, "up", 1.0, 1.0, "ratchet")] * (MIN_TRADES - 1)
    assert summarize(trades).verdict == "insufficient"


def test_verdict_needs_the_whole_interval_above_zero() -> None:
    steady = [Trade(0, 1, "up", net, 0.0, "x") for net in [0.2, 0.3] * MIN_TRADES]
    assert summarize(steady).verdict == "positive"
    noisy = [Trade(0, 1, "up", net, 0.0, "x") for net in [5.0, -4.9] * MIN_TRADES]
    assert summarize(noisy).verdict == "inconclusive"
    losing = [Trade(0, 1, "up", net, 0.0, "x") for net in [-0.2, -0.3] * MIN_TRADES]
    assert summarize(losing).verdict == "negative"


def test_settings_are_chosen_without_the_control_period() -> None:
    times, prices, params = scenario()
    cut = split(times)
    changed = prices[:cut] + [price * 2 for price in prices[cut:]]
    assert walk_forward(times, prices, params).chosen == walk_forward(times, changed, params).chosen


def test_control_period_is_the_latest_one() -> None:
    assert split(list(range(100))) == 70
    assert len(grid(BASE)) == 27


def test_interrupted_download_resumes_after_the_last_full_line(tmp_path: Path) -> None:
    path = tmp_path / "A.csv"
    assert last_epoch(path) is None
    path.write_text("100,1.5\n101,1.6\n102", encoding="ascii")
    assert last_epoch(path) == 101


def test_broken_lines_and_repeated_ticks_are_dropped(tmp_path: Path) -> None:
    path = tmp_path / "A.csv"
    path.write_text("100,1.5\n100,1.5\n101,1.6\n102", encoding="ascii")
    assert load_ticks(path) == ([100, 101], [1.5, 1.6])


def test_report_never_claims_profitability() -> None:
    times, prices, params = scenario()
    study = {
        "symbol": "TEST",
        "ticks": len(times),
        "first": times[0],
        "last": times[-1],
        "assumed": True,
        "result": walk_forward(times, prices, params),
    }
    text = render([study])
    assert "ne présente aucune stratégie comme rentable" in text
    assert "0,02 (hypothèse)" in text
    assert "Échantillon insuffisant" in text
    assert "Positif" not in text
