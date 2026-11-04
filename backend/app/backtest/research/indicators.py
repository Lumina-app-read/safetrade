"""
Indicateurs : la valeur d'indice `i` n'utilise jamais une bougie postérieure à `i`.

Tant qu'un indicateur n'a pas assez d'historique, il vaut `None`.
"""

import math
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass

from app.backtest.research.candles import Bars

MINUTE = 60

Series = list[float | None]


@dataclass(frozen=True)
class Frame:
    """Bougies d'une unité de temps, et bougie d'une minute où l'on peut agir sur chacune."""

    minutes: int
    epoch: list[int]
    open: list[float]
    high: list[float]
    low: list[float]
    close: list[float]
    # Indice, dans les bougies d'une minute, de la première bougie après la clôture.
    next_minute: list[int]

    def __len__(self) -> int:
        return len(self.epoch)


def resample(bars: Bars, minutes: int) -> Frame:
    span = minutes * MINUTE
    frame = Frame(minutes, [], [], [], [], [], [])
    current = -1
    for index in range(len(bars)):
        bucket = bars.epoch[index] - bars.epoch[index] % span
        if bucket != current:
            current = bucket
            if frame.epoch:
                frame.next_minute.append(index)
            frame.epoch.append(bucket)
            frame.open.append(bars.open[index])
            frame.high.append(bars.high[index])
            frame.low.append(bars.low[index])
            frame.close.append(bars.close[index])
        else:
            frame.high[-1] = max(frame.high[-1], bars.high[index])
            frame.low[-1] = min(frame.low[-1], bars.low[index])
            frame.close[-1] = bars.close[index]
    if frame.epoch:
        frame.next_minute.append(len(bars))  # dernière bougie : rien après elle
    return frame


def ema(values: Sequence[float], period: int) -> Series:
    factor = 2 / (period + 1)
    result: Series = []
    average = 0.0
    for index, value in enumerate(values):
        average = value if index == 0 else value * factor + average * (1 - factor)
        result.append(average if index + 1 >= period else None)
    return result


def sma_std(values: Sequence[float], period: int) -> tuple[Series, Series]:
    means: Series = []
    deviations: Series = []
    total = squares = 0.0
    window: deque[float] = deque()
    for value in values:
        window.append(value)
        total += value
        squares += value * value
        if len(window) > period:
            old = window.popleft()
            total -= old
            squares -= old * old
        if len(window) < period:
            means.append(None)
            deviations.append(None)
            continue
        mean = total / period
        means.append(mean)
        deviations.append(math.sqrt(max(squares / period - mean * mean, 0.0)))
    return means, deviations


def atr(frame: Frame, period: int) -> Series:
    ranges: list[float] = []
    for index in range(len(frame)):
        high, low = frame.high[index], frame.low[index]
        if index == 0:
            ranges.append(high - low)
            continue
        close = frame.close[index - 1]
        ranges.append(max(high - low, abs(high - close), abs(low - close)))
    return ema(ranges, period)


def rsi(values: Sequence[float], period: int) -> Series:
    """RSI de Wilder : la valeur d'indice `period` est la première définie."""
    result: Series = [None] * min(period, len(values))
    gains = losses = 0.0
    for index in range(1, len(values)):
        change = values[index] - values[index - 1]
        gain, loss = max(change, 0.0), max(-change, 0.0)
        if index <= period:
            gains += gain / period
            losses += loss / period
            if index < period:
                continue
        else:
            gains = (gains * (period - 1) + gain) / period
            losses = (losses * (period - 1) + loss) / period
        result.append(100.0 if losses == 0 else 100 - 100 / (1 + gains / losses))
    return result


def efficiency(values: Sequence[float], period: int) -> Series:
    """Rapport de Kaufman : 1 pour une ligne droite, proche de 0 pour un marché sans direction."""
    result: Series = []
    for index in range(len(values)):
        if index < period:
            result.append(None)
            continue
        path = sum(abs(values[k] - values[k - 1]) for k in range(index - period + 1, index + 1))
        result.append(abs(values[index] - values[index - period]) / path if path else 0.0)
    return result
