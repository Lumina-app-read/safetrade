"""
Stratégie version 1 : croisement de moyennes mobiles, filtré par la volatilité.

Déterministe et volontairement simple : elle sert à faire fonctionner le moteur en démo.
Elle n'est pas présentée comme rentable (CLAUDE.md, interdit 8). Le banc d'essai vient après.
"""

import itertools
from collections.abc import Sequence
from dataclasses import dataclass

from app.market.store import Data

FAST = 9
SLOW = 21
ATR_PERIOD = 14
# Variation moyenne minimale, en fraction du cours : marché trop plat sinon.
MIN_ATR_RATIO = 0.0002
NEEDED_CANDLES = SLOW + ATR_PERIOD + 2
GRANULARITY = 60


@dataclass(frozen=True)
class Signal:
    direction: str | None  # up, down, None pour attendre
    reason: str
    data: Data


def ema(values: Sequence[float], period: int) -> list[float]:
    factor = 2 / (period + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append(value * factor + result[-1] * (1 - factor))
    return result


def atr(candles: Sequence[Data], period: int) -> float:
    ranges = []
    for previous, candle in itertools.pairwise(candles):
        close = previous["close"]
        ranges.append(
            max(
                candle["high"] - candle["low"],
                abs(candle["high"] - close),
                abs(candle["low"] - close),
            )
        )
    recent = ranges[-period:]
    return float(sum(recent) / len(recent))


def evaluate(closed: Sequence[Data]) -> Signal:
    """`closed` : bougies closes, vérifiées par `entry_refusal`."""
    closes = [c["close"] for c in closed]
    fast, slow = ema(closes, FAST), ema(closes, SLOW)
    volatility = atr(closed, ATR_PERIOD)
    data = {
        "close": closes[-1],
        "ema_fast": round(fast[-1], 5),
        "ema_slow": round(slow[-1], 5),
        "atr": round(volatility, 5),
        "candle": closed[-1]["epoch"],
    }
    if volatility / closes[-1] < MIN_ATR_RATIO:
        return Signal(None, "strategy.flat_market", data)
    if fast[-2] <= slow[-2] and fast[-1] > slow[-1]:
        return Signal("up", "strategy.cross_up", data)
    if fast[-2] >= slow[-2] and fast[-1] < slow[-1]:
        return Signal("down", "strategy.cross_down", data)
    return Signal(None, "strategy.no_cross", data)
