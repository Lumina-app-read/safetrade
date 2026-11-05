"""Recherche v2 : période réservée, causalité, événements et coûts, sans réseau."""

import itertools
import random
from array import array
from pathlib import Path

import pytest

from app.backtest.research import candles, conditions
from app.backtest.research.candles import Bars
from app.backtest.research.conditions import Event
from app.backtest.research.indicators import resample

START = conditions._epoch(2026, 7, 1)


def walk(count: int, start: int = START, seed: int = 4) -> Bars:
    draw = random.Random(seed)  # noqa: S311
    bars = Bars(array("q"), array("d"), array("d"), array("d"), array("d"))
    price = 1.1
    for i in range(count):
        close = price * (1 + draw.gauss(0, 0.0004))
        bars.epoch.append(start + i * 60)
        bars.open.append(price)
        bars.high.append(max(price, close) * 1.0001)
        bars.low.append(min(price, close) * 0.9999)
        bars.close.append(close)
        price = close
    return bars


def test_reserved_months_are_never_loaded(tmp_path: Path) -> None:
    # Juillet puis août : la lecture de l'étude s'arrête au 1er août 2026.
    bars = walk(60 * 24 * 40)
    columns = (bars.epoch, bars.open, bars.high, bars.low, bars.close)
    rows = [",".join(str(column[i]) for column in columns) for i in range(len(bars))]
    path = tmp_path / "X.csv"
    candles.write_rows(path, rows, end=bars.epoch[-1])
    loaded = candles.load(path, until=conditions.STUDY_END)
    assert loaded.epoch[-1] < conditions.STUDY_END
    assert bars.epoch[-1] >= conditions.STUDY_END
    assert all(valid <= conditions.STUDY_END for _, valid in conditions.FOLDS)


def test_signals_never_use_future_candles() -> None:
    bars = walk(15 * 900)
    frame = resample(bars, 15)
    complete = conditions._signals(frame)
    cut = 600
    n = cut * 15
    head = Bars(bars.epoch[:n], bars.open[:n], bars.high[:n], bars.low[:n], bars.close[:n])
    shorter = resample(head, 15)
    partial = conditions._signals(shorter)
    for name in conditions.SIGNALS:
        early = [s for s in complete[name] if s[0] < cut - 1]
        assert [s for s in partial[name] if s[0] < cut - 1] == early


def test_events_do_not_overlap_and_enter_after_the_close() -> None:
    bars = walk(15 * 400)
    frame = resample(bars, 15)
    signals = [(i, 1) for i in range(120, 300)]
    events = conditions.events_of(bars, frame, signals, horizon=4, rate=0.0002)
    epochs = [e.epoch for e in events]
    assert all(b - a >= 5 * 15 * 60 for a, b in itertools.pairwise(epochs))
    first = events[0]
    index = frame.epoch.index(first.epoch)
    entry = bars.open[frame.next_minute[index]]
    assert first.gross == pytest.approx((frame.close[index + 4] - entry) / entry)


def test_net_result_subtracts_the_measured_commission() -> None:
    picked = {"X": [(Event(0, 0.001, (0.5, 1.0, 0.1, 1)), 0.0003)]}
    assert conditions.net_values(picked) == [pytest.approx(7.0)]  # 10 pb moins 3 pb
    assert conditions.net_values(picked, cost=2.0) == [pytest.approx(4.0)]
    assert conditions.break_even(picked) == pytest.approx(10 / 3)


def test_regimes_come_from_training_thresholds_only() -> None:
    rows = [(i, (float(i), float(i), float(i), 0)) for i in range(9)]
    cuts = conditions.thresholds(rows, until=6)  # seules les 6 premières bougies comptent
    assert cuts[0] == (2.0, 4.0)
    assert conditions.regime_of((1.0, 0.0, 0.0, 2), cuts, "tendance") == 0
    assert conditions.regime_of((5.0, 0.0, 0.0, 2), cuts, "tendance") == 2
    assert conditions.regime_of((5.0, 0.0, 0.0, 2), cuts, "seance") == 2


def test_random_direction_needs_a_real_edge() -> None:
    draw = random.Random(1)  # noqa: S311
    noise = {"X": [(Event(i, draw.gauss(0, 0.001), (0, 0, 0, 0)), 0.0) for i in range(400)]}
    edge = {"X": [(Event(i, 0.001 + draw.gauss(0, 0.0005), (0, 0, 0, 0)), 0.0) for i in range(400)]}
    assert conditions.random_p(noise, draws=300) > 0.05
    assert conditions.random_p(edge, draws=300) < 0.01


def test_grid_matches_the_protocol() -> None:
    cells = conditions.all_cells()
    # 5 signaux, 2 unités, 2 horizons, 4 classes, 1 + 3 + 3 + 3 + 4 conditions
    assert len(cells) == 5 * 2 * 2 * 4 * 14
    assert len({c.key for c in cells}) == len(cells)
