"""
Les six familles de stratégies et leurs réglages, fixés avant tout résultat.

Un signal à l'indice `i` n'utilise que des bougies closes jusqu'à `i`. Il ne porte aucun montant :
la mise, le stop et les limites restent l'affaire du simulateur et, en réel, du module de risque.
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import product

from app.backtest.research import indicators as ind
from app.backtest.research.indicators import Frame, Series

TIMEFRAMES = (15, 60)
UP, DOWN = 1, -1
ATR_PERIOD = 14

Signals = list[tuple[int, int]]  # (indice de bougie, sens)


@dataclass(frozen=True)
class Exit:
    stop: float  # en multiples d'ATR
    target: float | None = None
    hold: int | None = None  # en bougies de l'unité de temps
    trail: float | None = None


@dataclass(frozen=True)
class Config:
    family: str
    minutes: int
    options: tuple[tuple[str, float], ...]
    exit: Exit

    @property
    def key(self) -> str:
        options = ",".join(f"{name}={value}" for name, value in self.options)
        leave = self.exit
        return (
            f"{self.family}|{self.minutes}|{options}|s{leave.stop}|t{leave.target}"
            f"|h{leave.hold}|r{leave.trail}"
        )


def _trend(frame: Frame, fast: float, slow: float) -> Signals:
    quick = ind.ema(frame.close, int(fast))
    long = ind.ema(frame.close, int(slow))
    # Unité supérieure : une moyenne quatre fois plus longue, calculée sur les mêmes bougies.
    upper = ind.ema(frame.close, int(slow) * 4)
    found: Signals = []
    for i in range(1, len(frame)):
        a, b, c, d, top = quick[i - 1], long[i - 1], quick[i], long[i], upper[i]
        if a is None or b is None or c is None or d is None or top is None:
            continue
        if a <= b and c > d and frame.close[i] > top:
            found.append((i, UP))
        elif a >= b and c < d and frame.close[i] < top:
            found.append((i, DOWN))
    return found


def _momentum(frame: Frame, lookback: float, threshold: float) -> Signals:
    span = int(lookback)
    width = ind.atr(frame, ATR_PERIOD)
    level = ind.ema(frame.close, 100)
    scale = math.sqrt(span)
    found: Signals = []
    previous = 0.0
    for i in range(span, len(frame)):
        volatility, base = width[i], level[i]
        if volatility is None or base is None or volatility <= 0:
            continue
        move = (frame.close[i] - frame.close[i - span]) / (volatility * scale)
        if move > threshold >= previous and frame.close[i] > base:
            found.append((i, UP))
        elif move < -threshold <= previous and frame.close[i] < base:
            found.append((i, DOWN))
        previous = move
    return found


def _reversal(frame: Frame, deviation: float) -> Signals:
    mean, spread = ind.sma_std(frame.close, 20)
    strength = ind.rsi(frame.close, 14)
    found: Signals = []
    armed = True
    for i in range(len(frame)):
        m, s, r = mean[i], spread[i], strength[i]
        if m is None or s is None or r is None or s <= 0:
            continue
        score = (frame.close[i] - m) / s
        if abs(score) < 1:
            armed = True  # retour près de la moyenne : un nouvel excès redevient un signal
        if not armed:
            continue
        if score < -deviation and r < 30:
            found.append((i, UP))
            armed = False
        elif score > deviation and r > 70:
            found.append((i, DOWN))
            armed = False
    return found


def _breakout(frame: Frame, channel: float, expansion: float) -> Signals:
    span = int(channel)
    short = ind.atr(frame, ATR_PERIOD)
    long = ind.atr(frame, 100)
    found: Signals = []
    for i in range(span, len(frame)):
        a, b = short[i], long[i]
        if a is None or b is None or b <= 0 or a / b < expansion:
            continue
        if frame.close[i] > max(frame.high[i - span : i]):
            found.append((i, UP))
        elif frame.close[i] < min(frame.low[i - span : i]):
            found.append((i, DOWN))
    return found


def _volatility(frame: Frame, quantile: float) -> Signals:
    mean, spread = ind.sma_std(frame.close, 20)
    widths: Series = [
        None if m is None or s is None or m == 0 else 4 * s / m
        for m, s in zip(mean, spread, strict=True)
    ]
    found: Signals = []
    for i in range(220, len(frame)):
        m, s, width = mean[i], spread[i], widths[i - 1]
        if m is None or s is None or width is None:
            continue
        history = [w for w in widths[i - 201 : i - 1] if w is not None]
        if len(history) < 150:
            continue
        rank = sum(w <= width for w in history) / len(history)
        if rank > quantile:
            continue
        if frame.close[i] > m + 2 * s:
            found.append((i, UP))
        elif frame.close[i] < m - 2 * s:
            found.append((i, DOWN))
    return found


def _combined(frame: Frame, pullback: float, minimum: float) -> Signals:
    trend = ind.ema(frame.close, 200)
    strength = ind.rsi(frame.close, 14)
    straight = ind.efficiency(frame.close, 20)
    found: Signals = []
    for i in range(1, len(frame)):
        base, before, now, ratio = trend[i], strength[i - 1], strength[i], straight[i]
        if base is None or before is None or now is None or ratio is None or ratio < minimum:
            continue
        if frame.close[i] > base and before <= pullback < now:
            found.append((i, UP))
        elif frame.close[i] < base and before >= 100 - pullback > now:
            found.append((i, DOWN))
    return found


FAMILIES: dict[str, Callable[..., Signals]] = {
    "tendance": _trend,
    "momentum": _momentum,
    "retournement": _reversal,
    "cassure": _breakout,
    "volatilite": _volatility,
    "combinee": _combined,
}

TARGET_EXITS = tuple(
    Exit(stop, target, hold) for stop, target, hold in product((1.5, 2.5), (1.5, 3.0), (8, 24))
)
REVERSAL_EXITS = tuple(
    Exit(stop, target, hold) for stop, target, hold in product((1.5, 2.5), (1.0, 2.0), (8, 24))
)
TRAIL_EXITS = tuple(Exit(stop, trail=trail) for stop, trail in product((2.0, 3.0), (3.0, 5.0)))
BREAK_EXITS = (*TRAIL_EXITS, *(Exit(stop, 3.0, 24) for stop in (1.5, 2.5)))

GRID: tuple[tuple[str, tuple[str, ...], Sequence[tuple[float, ...]], Sequence[Exit]], ...] = (
    (
        "tendance",
        ("rapide", "lente"),
        ((10, 30), (20, 50), (50, 200)),
        TRAIL_EXITS,
    ),
    (
        "momentum",
        ("periode", "seuil"),
        tuple(product((4, 12, 24), (1.5, 2.5))),
        TARGET_EXITS,
    ),
    ("retournement", ("ecart",), ((2.0,), (2.5,), (3.0,)), REVERSAL_EXITS),
    (
        "cassure",
        ("canal", "expansion"),
        tuple(product((20, 55), (1.0, 1.3))),
        BREAK_EXITS,
    ),
    ("volatilite", ("quantile",), ((0.1,), (0.2,)), TARGET_EXITS),
    (
        "combinee",
        ("repli", "efficacite"),
        tuple(product((35, 45), (0.2, 0.35))),
        TARGET_EXITS,
    ),
)


def all_configs() -> list[Config]:
    return [
        Config(family, minutes, tuple(zip(names, values, strict=True)), leave)
        for family, names, options, exits in GRID
        for minutes in TIMEFRAMES
        for values in options
        for leave in exits
    ]


def signals_of(config: Config, frame: Frame) -> Signals:
    return FAMILIES[config.family](frame, *(value for _, value in config.options))
