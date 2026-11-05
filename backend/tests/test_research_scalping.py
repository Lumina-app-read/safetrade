"""Recherche v3 : ticks, signaux, positions et coûts par produit, sans réseau."""

import math
import random
from pathlib import Path

import pytest

from app.backtest.research import scalping, ticks
from app.backtest.research.scalping import Position


def walk(count: int, seed: int = 2) -> list[float]:
    draw = random.Random(seed)  # noqa: S311
    price = [4600.0]
    for _ in range(count - 1):
        price.append(round(price[-1] + draw.gauss(0, 0.6), 2))
    return price


def test_reserved_months_are_never_loaded(tmp_path: Path) -> None:
    july = scalping._epoch(2026, 7, 31)
    rows = [f"{july + i},{4600 + i * 0.01}" for i in range(3 * 86400)]
    path = tmp_path / "1HZ75V.csv"
    assert ticks.write(path, rows, july, july + 3 * 86400) == 3 * 86400
    loaded = ticks.load(path, until=scalping.STUDY_END)
    assert loaded.epoch[-1] == scalping.STUDY_END - 1


def test_download_window_drops_ticks_outside(tmp_path: Path) -> None:
    path = tmp_path / "X.csv"
    rows = ["105,1", "100,1", "100,2", "200,9", "50,0"]
    assert ticks.write(path, rows, 100, 200) == 2
    assert list(ticks.load(path).epoch) == [100, 105]


def test_signals_never_use_future_ticks() -> None:
    price = walk(5000)
    makers = scalping.signal_makers(0.6, 0.4)
    for name, make in makers.items():
        full = [s for s in make(price) if s[0] < 3000]
        assert make(price[:3000]) == full, name


def test_rolling_extremes_exclude_the_current_tick() -> None:
    highs, lows = scalping._rolling_extremes([1.0, 3.0, 2.0, 5.0, 4.0], 2)
    assert highs[2:] == [3.0, 3.0, 5.0]
    assert lows[2:] == [1.0, 2.0, 2.0]


def test_one_position_at_a_time_after_the_delay() -> None:
    price = [float(i) for i in range(100)]
    signals = [(10, 1), (11, 1), (20, -1)]
    found = scalping.positions_of(price, signals, horizon=5, delay=1, start=0, end=100)
    assert [(p.entry, p.exit) for p in found] == [(11, 16), (21, 26)]
    assert found[0].move == pytest.approx(5 / 11)
    assert found[1].move < 0  # vente sur un prix qui monte


def test_rise_fall_ties_lose_and_payout_is_measured() -> None:
    assert scalping.rise_fall(Position(0, 1, 1, 0.0)) == -1.0
    assert scalping.rise_fall(Position(0, 1, 1, 1e-6)) == pytest.approx(0.883)
    assert pytest.approx(0.531, abs=0.001) == scalping.RISE_FALL_BREAK_EVEN


def test_multiplier_counts_commission_and_stop() -> None:
    price = [100.0, 100.1, 100.2]
    gain = scalping.multiplier(Position(0, 2, 1, 0.002), price)
    assert gain == pytest.approx(100 * 0.002 - 100 * scalping.MULTIPLIER_RATE)
    crash = [100.0, 99.0, 101.0]  # -1 % touche le stop de 50 % de la mise avant la remontée
    assert scalping.multiplier(Position(0, 2, 1, 0.01), crash) == pytest.approx(
        -0.5 - 100 * scalping.MULTIPLIER_RATE
    )


def test_binomial_p_and_losing_streaks() -> None:
    assert scalping.binomial_p(531, 1000, 0.531) == pytest.approx(0.5, abs=0.01)
    assert scalping.binomial_p(600, 1000, 0.531) < 0.001
    assert scalping.consecutive_losses([1, -1, -1, 0, 1, -1]) == 3


def test_random_walk_shows_no_predictability() -> None:
    measures = scalping.predictability(walk(60_000))
    assert all(abs(a) < 4 * measures["band"] for a in measures["acf"])
    # Sur 300 ticks, 200 points seulement : erreur type d'environ 0,1, tolérance de 3 erreurs.
    assert all(abs(v - 1) < 0.3 for v in measures["vr"].values())
    assert all(abs(v - 0.5) < 0.03 for v in measures["up_after_ups"].values())


def test_accumulator_expectancy_follows_survival() -> None:
    price = [100.0] * 200  # aucune variation : la barrière n'est jamais franchie
    spread = scalping.rolling_std(price, 60)
    result = scalping.accumulators(price, spread, 1.0, 0, len(price))
    holds = result["0.01"]["toujours"]
    assert holds[10]["survival"] == 1.0
    assert holds[10]["expectancy"] == pytest.approx(1.01**10 - 1, abs=1e-4)
    assert not math.isnan(result["0.05"]["knock_per_tick"]["toujours"])
