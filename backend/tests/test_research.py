"""Recherche de stratégies : cours écrits à la main, sans réseau."""

import random
from array import array
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from app.backtest.research import indicators as ind
from app.backtest.research import protocol
from app.backtest.research import run as research_run
from app.backtest.research.candles import Bars
from app.backtest.research.families import (
    FAMILIES,
    Config,
    Exit,
    all_configs,
    signals_of,
)
from app.backtest.research.indicators import resample
from app.backtest.research.simulate import STOP_SLIPPAGE_R, Trade, run, tradable

START = 1_800_000_000 - 1_800_000_000 % 3600
MULTIPLIERS = (100, 200, 300, 500, 800)


def bars_of(rows: Sequence[tuple[float, float, float, float]], start: int = START) -> Bars:
    bars = Bars(array("q"), array("d"), array("d"), array("d"), array("d"))
    for index, (o, h, l, c) in enumerate(rows):  # noqa: E741
        bars.epoch.append(start + index * 60)
        bars.open.append(o)
        bars.high.append(h)
        bars.low.append(l)
        bars.close.append(c)
    return bars


def flat(price: float, count: int) -> list[tuple[float, float, float, float]]:
    return [(price, price, price, price)] * count


def walk(count: int, seed: int = 3, step: float = 0.0006) -> Bars:
    draw = random.Random(seed)  # noqa: S311
    rows = []
    price = 1000.0
    for _ in range(count):
        close = price * (1 + draw.gauss(0, step))
        rows.append((price, max(price, close) * 1.0002, min(price, close) * 0.9998, close))
        price = close
    return bars_of(rows)


CONFIG = Config("cassure", 15, (("canal", 20), ("expansion", 1.0)), Exit(2.0, 3.0, 8))


def one_trade(
    path: Sequence[tuple[float, float, float, float]], config: Config = CONFIG, width: float = 1.0
) -> Trade:
    """Signal sur la première bougie de 15 minutes, entrée à la minute suivante."""
    bars = bars_of([*flat(1000.0, 15), *path])
    frame = resample(bars, 15)
    widths: list[float | None] = [width] * len(frame)
    return run(bars, frame, widths, [(0, 1)], config, MULTIPLIERS)[0]


def test_resample_builds_candles_and_acts_after_the_close() -> None:
    bars = bars_of([(1, 2, 0.5, 1.5)] * 15 + [(2, 3, 1.5, 2.5)] * 15)
    frame = resample(bars, 15)
    assert (frame.open[0], frame.high[0], frame.low[0], frame.close[0]) == (1, 2, 0.5, 1.5)
    assert frame.next_minute == [15, 30]


def test_indicators_are_causal() -> None:
    bars = walk(3000)
    frame = resample(bars, 15)
    cut = 120
    shorter = resample(
        Bars(
            bars.epoch[: cut * 15],
            bars.open[: cut * 15],
            bars.high[: cut * 15],
            bars.low[: cut * 15],
            bars.close[: cut * 15],
        ),
        15,
    )
    builders: list[Callable[[ind.Frame], ind.Series]] = [
        lambda f: ind.ema(f.close, 20),
        lambda f: ind.sma_std(f.close, 20)[1],
        lambda f: ind.atr(f, 14),
        lambda f: ind.rsi(f.close, 14),
        lambda f: ind.efficiency(f.close, 20),
    ]
    for build in builders:
        assert build(frame)[: cut - 1] == build(shorter)[: cut - 1]


def test_rsi_extremes() -> None:
    assert ind.rsi([float(i) for i in range(1, 40)], 14)[-1] == 100.0
    assert ind.rsi([float(40 - i) for i in range(40)], 14)[-1] == pytest.approx(0.0)
    assert len(ind.rsi([1.0] * 30, 14)) == 30


@pytest.mark.parametrize("family", list(FAMILIES))
def test_signals_never_depend_on_future_candles(family: str) -> None:
    bars = walk(14_000)
    frame = resample(bars, 15)
    config = next(c for c in all_configs() if c.family == family and c.minutes == 15)
    complete = signals_of(config, frame)
    cut = 700
    shorter = resample(
        Bars(
            bars.epoch[: cut * 15],
            bars.open[: cut * 15],
            bars.high[: cut * 15],
            bars.low[: cut * 15],
            bars.close[: cut * 15],
        ),
        15,
    )
    expected = [item for item in complete if item[0] < cut - 1]
    assert [item for item in signals_of(config, shorter) if item[0] < cut - 1] == expected


def test_stop_is_hit_at_its_level_with_slippage() -> None:
    trade = one_trade([(1000, 1000.5, 997, 998)])
    # ATR 1, stop à 2 ATR : 0,2 %. Sortie au niveau, moins le glissement mesuré.
    assert trade.reason == "stop"
    assert trade.gross_r == pytest.approx(-1 - STOP_SLIPPAGE_R)


def test_gap_exits_beyond_the_stop() -> None:
    trade = one_trade([(1000, 1000, 1000, 1000), (990, 992, 989, 991)])
    assert trade.reason == "stop"
    assert trade.gross_r == pytest.approx(-5 - STOP_SLIPPAGE_R)


def test_stop_comes_first_when_both_levels_are_touched() -> None:
    trade = one_trade([(1000, 1004, 997, 1002)])
    assert trade.reason == "stop"


def test_target_pays_its_level() -> None:
    trade = one_trade([(1000, 1003.5, 999.5, 1003)])
    assert trade.reason == "objectif"
    assert trade.gross_r == pytest.approx(1.5)


def test_time_stop_leaves_at_the_open() -> None:
    path = [(1000, 1000.5, 999.5, 1000.2)] * 120 + [(1001, 1001, 1001, 1001)] * 5
    trade = one_trade(path)
    assert trade.reason == "temps"


def test_trailing_stop_never_moves_back() -> None:
    config = Config("tendance", 15, (), Exit(2.0, trail=3.0))
    path = [(1000, 1010, 1000, 1010), (1010, 1010, 1006, 1008), (1008, 1008, 1006, 1006.5)]
    trade = one_trade(path, config)
    assert trade.reason == "stop"
    assert trade.gross_r == pytest.approx(3.5 - STOP_SLIPPAGE_R)


def test_commission_is_proportional_to_the_distance_of_the_stop() -> None:
    trade = one_trade([(1000, 1003.5, 999.5, 1003)])
    # Stop à 0,2 % : une commission de 0,02 % coûte 0,1 R.
    assert trade.net_r(0.0002) == pytest.approx(1.4)


def test_stop_must_fit_deriv_limits() -> None:
    assert tradable(0.002, MULTIPLIERS)
    assert not tradable(0.05, MULTIPLIERS)  # stop de 500 % de la mise à 100 fois
    assert not tradable(0.0001, MULTIPLIERS)  # trop serré, même à 800 fois


def test_one_position_at_a_time_and_nothing_invented() -> None:
    bars = bars_of(flat(1000.0, 15) + [(1000, 1000.5, 999.5, 1000)] * 400)
    frame = resample(bars, 15)
    widths: list[float | None] = [1.0] * len(frame)
    trades = run(bars, frame, widths, [(0, 1), (1, 1), (2, -1)], CONFIG, MULTIPLIERS)
    assert len(trades) == 1
    assert all(t.reason == "temps" for t in trades)
    short = bars_of(flat(1000.0, 15) + [(1000, 1000.5, 999.5, 1000)] * 10)
    assert run(short, resample(short, 15), [1.0] * 2, [(0, 1)], CONFIG, MULTIPLIERS) == []


def test_stale_signal_is_not_traded() -> None:
    bars = bars_of(flat(1000.0, 15))
    late = bars_of(flat(1000.0, 200), START + 100 * 3600)
    both = Bars(
        bars.epoch + late.epoch,
        bars.open + late.open,
        bars.high + late.high,
        bars.low + late.low,
        bars.close + late.close,
    )
    frame = resample(both, 15)
    assert run(both, frame, [1.0] * len(frame), [(0, 1)], CONFIG, MULTIPLIERS) == []


def test_random_direction_is_reproducible() -> None:
    bars = walk(6000)
    frame = resample(bars, 15)
    signals = [(i, 1) for i in range(30, len(frame), 10)]
    widths = ind.atr(frame, 14)
    first = run(bars, frame, widths, signals, CONFIG, MULTIPLIERS, draw=random.Random(5))  # noqa: S311
    second = run(bars, frame, widths, signals, CONFIG, MULTIPLIERS, draw=random.Random(5))  # noqa: S311
    assert first == second
    assert {t.direction for t in first} == {1, -1}


def test_entries_before_the_period_are_skipped() -> None:
    bars = walk(6000)
    frame = resample(bars, 15)
    signals = [(i, 1) for i in range(30, len(frame), 10)]
    since = bars.epoch[3000]
    widths = ind.atr(frame, 14)
    trades = run(bars, frame, widths, signals, CONFIG, MULTIPLIERS, since=since)
    assert trades
    assert all(t.opened_at >= since for t in trades)


def test_grid_is_the_same_as_the_protocol() -> None:
    configs = all_configs()
    assert {c.family for c in configs} == set(FAMILIES)
    assert {c.minutes for c in configs} == {15, 60}
    assert len({c.key for c in configs}) == len(configs)


# Règles du protocole : découpage, statistiques, sélection et verdict.


def test_split_uses_the_common_period_of_every_market() -> None:
    split = protocol.split_of({"a": (0, 1000), "b": (200, 1200), "c": (100, 1100)})
    assert (split.common_start, split.end) == (200, 1000)
    assert (split.train_end, split.valid_end) == (600, 800)
    assert [split.period(e) for e in (100, 599, 600, 799, 800)] == [
        "train",
        "train",
        "valid",
        "valid",
        "test",
    ]


def test_stats_measure_expectancy_drawdown_and_profit_factor() -> None:
    stat = protocol.stats_of([1.0, -1.0, 2.0, -1.0, -1.0])
    assert stat.n == 5
    assert stat.mean == pytest.approx(0.0)
    assert stat.win_rate == pytest.approx(0.4)
    assert stat.profit_factor == pytest.approx(1.0)
    assert stat.max_drawdown == pytest.approx(2.0)
    assert stat.ci_low < 0 < stat.ci_high
    assert protocol.stats_of([]).n == 0


def test_selection_takes_the_best_t_with_enough_positions() -> None:
    small = protocol.stats_of([1.0] * 50 + [-0.5] * 49)
    large = protocol.stats_of([0.2, -0.1] * 100)
    losing = protocol.stats_of([-0.1, 0.05] * 100)
    chosen = protocol.choose_on_train(
        {"small": (small, {}), "large": (large, {}), "losing": (losing, {})}
    )
    assert chosen == "large"  # « small » n'a que 99 positions
    assert protocol.choose_on_train({"losing": (losing, {})}) is None


def test_validation_needs_markets_to_agree() -> None:
    stat = protocol.stats_of([0.3, -0.1] * 40)
    split_markets = {"a": [0.5] * 10, "b": [-0.5] * 10, "c": [-0.2] * 10}
    agree = {"a": [0.5] * 10, "b": [0.1] * 10, "c": [-0.2] * 10}
    assert not protocol.passes_validation(stat, split_markets, 3)
    assert protocol.passes_validation(stat, agree, 3)
    assert not protocol.passes_validation(protocol.stats_of([0.3, -0.1] * 10), agree, 3)


def test_verdict_needs_every_condition() -> None:
    good = protocol.stats_of([0.5, -0.2] * 200)
    ok = protocol.verdict(good, 0.01, good, 3, 1.0, 1, 4)
    assert ok.passed
    assert not protocol.verdict(good, 0.2, good, 3, 1.0, 1, 4).passed  # pas mieux que le hasard
    assert not protocol.verdict(good, 0.01, good, 1, 1.0, 1, 4).passed  # une seule sous-période
    weak = protocol.stats_of([0.11, -0.1] * 50)
    assert not protocol.verdict(weak, 0.01, weak, 3, 1.0, 1, 20).significant  # Bonferroni


def test_random_baseline_and_maximum_cost() -> None:
    assert protocol.random_p_value(0.1, [0.0] * 199) == pytest.approx(1 / 200)
    assert protocol.random_p_value(-1.0, [0.0] * 199) == pytest.approx(1.0)
    trades = [Trade(0, 60, 1, 0.2, 100.0, "objectif"), Trade(0, 60, 1, -0.1, 100.0, "stop")]
    assert protocol.max_cost(trades) == pytest.approx(0.0005)


def test_test_stage_refuses_an_uncommitted_selection(tmp_path: Path) -> None:
    assert not research_run._committed(research_run.ROOT / "backend" / "nonexistent.json")
