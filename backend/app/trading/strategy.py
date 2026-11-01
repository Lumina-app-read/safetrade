"""
Stratégie version 1 : croisement de moyennes mobiles, filtré par la volatilité.

Déterministe et volontairement simple : elle sert à faire fonctionner le moteur en démo.
Le banc d'essai ne lui trouve aucun avantage sur le tirage au sort (docs/decisions/banc-essai.md).
"""

import itertools
from collections.abc import Sequence
from dataclasses import dataclass

from app.market.store import Data

FAST = 9
SLOW = 21
ATR_PERIOD = 14
# Une bougie moyenne doit valoir au moins 2 % de la mise, multiplicateur compris : marché trop
# plat sinon. Un seuil en pourcentage du cours bloquait Step Index en permanence (banc d'essai).
MIN_CANDLE_VALUE = 0.02
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


def evaluate(closed: Sequence[Data], multiplier: int) -> Signal:
    """`closed` : bougies closes, vérifiées par `entry_refusal`."""
    closes = [c["close"] for c in closed]
    fast, slow = ema(closes, FAST), ema(closes, SLOW)
    volatility = atr(closed, ATR_PERIOD)
    candle_value = volatility / closes[-1] * multiplier
    data = {
        "close": closes[-1],
        "ema_fast": round(fast[-1], 5),
        "ema_slow": round(slow[-1], 5),
        "atr": round(volatility, 5),
        "candle_value": round(candle_value, 4),
        "candle": closed[-1]["epoch"],
    }
    if candle_value < MIN_CANDLE_VALUE:
        return Signal(None, "strategy.flat_market", data)
    if fast[-2] <= slow[-2] and fast[-1] > slow[-1]:
        return Signal("up", "strategy.cross_up", data)
    if fast[-2] >= slow[-2] and fast[-1] < slow[-1]:
        return Signal("down", "strategy.cross_down", data)
    return Signal(None, "strategy.no_cross", data)
